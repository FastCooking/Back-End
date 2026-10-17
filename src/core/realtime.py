import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from src.core.events import domain_event_bus
from src.schemas.DeliverySchema import DeliveryClaimedEvent
from src.schemas.KdsNotificationSchema import OrderItemReadyEvent, ShiftStatus

logger = logging.getLogger("fastcooking.realtime")

SEND_TIMEOUT_SECONDS = 0.4
ALLOWED_WAITER_ROLES = frozenset({"Garcom", "WAITER"})

STATUS_MAP_FRONTEND = {
    "Pendente": "PENDING",
    "Em preparo": "IN_PREPARATION",
    "Pronto": "READY",
    "Entregue": "DELIVERED",
    "Cancelado": "CANCELLED",
}


@dataclass(eq=False)
class Subscription:
    websocket: WebSocket
    restaurant_id: UUID | str | int
    user_id: UUID | str | int
    role: str
    sequence: int = 0
    shift_status: str = ShiftStatus.ON_SHIFT.value


@dataclass(eq=False)
class WaiterRoomSubscription:
    websocket: WebSocket
    restaurant_id: str
    user_id: str
    role: str
    shift_status: str = ShiftStatus.ON_SHIFT.value
    room: str = ""
    sequence: int = 0
    connected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_heartbeat_at: float = field(default_factory=time.monotonic)


@dataclass(eq=False)
class TrackingSubscription:
    websocket: WebSocket
    order_id: str


class RealtimeHub:
    """
    In-process WebSocket Gateway & Room Manager para a equipe do restaurante (KDS e Pool de Garçons)
    e acompanhamento em tempo real do cliente.
    """

    def __init__(self, send_timeout: float = SEND_TIMEOUT_SECONDS) -> None:
        self._subscriptions: set[Subscription] = set()
        self._waiter_rooms: dict[str, set[WaiterRoomSubscription]] = defaultdict(set)
        self._tracking_subscriptions: set[TrackingSubscription] = set()
        self._lock = asyncio.Lock()
        self._queue_version = 0
        self.send_timeout = send_timeout

    @property
    def queue_version(self) -> int:
        return self._queue_version

    @staticmethod
    def waiter_room_name(restaurant_id: UUID | str | int) -> str:
        return f"room:waiters:active:{restaurant_id}"

    def get_active_waiter_connections(
        self, restaurant_id: UUID | str | int
    ) -> list[WaiterRoomSubscription]:
        room_key = self.waiter_room_name(restaurant_id)
        return [
            sub
            for sub in self._waiter_rooms.get(room_key, set())
            if sub.shift_status == ShiftStatus.ON_SHIFT.value
            and sub.role in ALLOWED_WAITER_ROLES
        ]

    async def join_waiters_room(
        self,
        websocket: WebSocket,
        restaurant_id: UUID | str | int,
        user_id: UUID | str | int,
        role: str,
        shift_status: str = ShiftStatus.ON_SHIFT.value,
    ) -> WaiterRoomSubscription:
        """
        Valida o papel (WAITER/Garcom) e o status em serviço (ON_SHIFT), adicionando o socket
        à sala dedicada `room:waiters:active:<restaurant_id>`.
        """
        normalized_shift = (shift_status or "").strip().upper()
        if role not in ALLOWED_WAITER_ROLES:
            logger.warning(
                "[WS_AUTH_REJECTED] Usuário %s com role '%s' tentou entrar na sala de garçons.",
                user_id,
                role,
            )
            raise PermissionError("Apenas usuários com perfil Garçom (WAITER) podem ingressar nesta sala.")

        if normalized_shift != ShiftStatus.ON_SHIFT.value:
            logger.warning(
                "[WS_SHIFT_REJECTED] Garçom %s fora de serviço (shift_status='%s') bloqueado.",
                user_id,
                shift_status,
            )
            raise PermissionError("Garçom fora de turno (OFF_SHIFT) não pode ingressar na sala ativa.")

        room_key = self.waiter_room_name(restaurant_id)
        subscription = WaiterRoomSubscription(
            websocket=websocket,
            restaurant_id=str(restaurant_id),
            user_id=str(user_id),
            role=role,
            shift_status=ShiftStatus.ON_SHIFT.value,
            room=room_key,
        )

        async with self._lock:
            self._waiter_rooms[room_key].add(subscription)
            subscription.sequence += 1

            try:
                await asyncio.wait_for(
                    websocket.send_json(
                        {
                            "type": "room.joined",
                            "room": "room:waiters:active",
                            "tenantRoom": room_key,
                            "restaurantId": str(restaurant_id),
                            "userId": str(user_id),
                            "shiftStatus": ShiftStatus.ON_SHIFT.value,
                            "sequence": subscription.sequence,
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    ),
                    timeout=self.send_timeout,
                )
            except Exception:
                self._waiter_rooms[room_key].discard(subscription)
                raise

        logger.info(
            "[WS_ROOM_JOIN] Garçom=%s conectado à sala '%s'",
            user_id,
            room_key,
        )
        return subscription

    async def leave_waiters_room(
        self,
        websocket: WebSocket,
        reason: str = "disconnected",
    ) -> None:
        """Remove imediatamente o socket de todas as salas de garçons ativos."""
        async with self._lock:
            for room_key, members in list(self._waiter_rooms.items()):
                to_remove = [sub for sub in members if sub.websocket is websocket]
                for sub in to_remove:
                    members.discard(sub)
                    logger.info(
                        "[WS_ROOM_LEAVE] Garçom=%s removido da sala '%s' (motivo=%s)",
                        sub.user_id,
                        room_key,
                        reason,
                    )
                if not members:
                    self._waiter_rooms.pop(room_key, None)

    async def update_waiter_shift(
        self,
        websocket: WebSocket,
        new_shift_status: str,
    ) -> bool:
        """
        Atualiza o status de turno do garçom em tempo real.
        Caso mude para OFF_SHIFT, remove-o imediatamente da sala de recebimento.
        """
        normalized = (new_shift_status or "").strip().upper()
        if normalized != ShiftStatus.ON_SHIFT.value:
            await self.leave_waiters_room(websocket, reason="shift_ended")
            return False

        async with self._lock:
            for members in self._waiter_rooms.values():
                for sub in members:
                    if sub.websocket is websocket:
                        sub.shift_status = ShiftStatus.ON_SHIFT.value
                        sub.last_heartbeat_at = time.monotonic()
                        return True
        return False

    async def record_heartbeat(self, websocket: WebSocket) -> None:
        """Atualiza o timestamp monotônico do último ping recebido da conexão."""
        now = time.monotonic()
        async with self._lock:
            for members in self._waiter_rooms.values():
                for sub in members:
                    if sub.websocket is websocket:
                        sub.last_heartbeat_at = now
                        return

    async def broadcast_item_ready(self, event: OrderItemReadyEvent) -> dict:
        """
        Listener de domínio para OrderItemReadyEvent.
        Realiza broadcast assíncrono não-bloqueante para todos os garçons autenticados
        e em serviço (ON_SHIFT) na sala do restaurante (`room:waiters:active:<idRestaurante>`).
        """
        started_at = time.perf_counter()
        payload = event.to_payload().model_dump(mode="json")
        room_key = self.waiter_room_name(event.restaurant_id)

        async with self._lock:
            active_subscribers = [
                sub
                for sub in tuple(self._waiter_rooms.get(room_key, ()))
                if sub.shift_status == ShiftStatus.ON_SHIFT.value
                and sub.role in ALLOWED_WAITER_ROLES
            ]

        if not active_subscribers:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            logger.info(
                "[KDS_READY_BROADCAST] eventId=%s sala=%s sem garçons ativos (%.2fms)",
                payload["eventId"],
                room_key,
                elapsed_ms,
            )
            return {
                "eventId": payload["eventId"],
                "room": room_key,
                "deliveredCount": 0,
                "failedCount": 0,
                "elapsedMs": round(elapsed_ms, 3),
            }

        delivery_tasks = [
            self._send_waiter_ready_payload(sub, payload)
            for sub in active_subscribers
        ]
        failed_subscriptions = await asyncio.gather(*delivery_tasks)

        dead_subs = [sub for sub in failed_subscriptions if sub is not None]
        if dead_subs:
            async with self._lock:
                room_members = self._waiter_rooms.get(room_key)
                if room_members is not None:
                    room_members.difference_update(dead_subs)
                    if not room_members:
                        self._waiter_rooms.pop(room_key, None)

        delivered_count = len(active_subscribers) - len(dead_subs)
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0

        logger.info(
            "[KDS_READY_BROADCAST] eventId=%s mesa=%s entregues=%d falhas_isoladas=%d latencia=%.2fms",
            payload["eventId"],
            payload["tableNumber"],
            delivered_count,
            len(dead_subs),
            elapsed_ms,
        )

        return {
            "eventId": payload["eventId"],
            "room": room_key,
            "deliveredCount": delivered_count,
            "failedCount": len(dead_subs),
            "elapsedMs": round(elapsed_ms, 3),
        }

    async def broadcast_delivery_claimed(self, event: DeliveryClaimedEvent) -> dict:
        """
        Listener de domínio para DeliveryClaimedEvent.
        Emite o evento 'delivery:claimed' para a sala room:waiters:active:<idRestaurante>,
        garantindo que os demais garçons removam imediatamente o card/botão de ação da UI.
        """
        started_at = time.perf_counter()
        payload = event.to_payload().model_dump(mode="json")
        room_key = self.waiter_room_name(event.restaurant_id)

        async with self._lock:
            active_subscribers = [
                sub
                for sub in tuple(self._waiter_rooms.get(room_key, ()))
                if sub.shift_status == ShiftStatus.ON_SHIFT.value
                and sub.role in ALLOWED_WAITER_ROLES
            ]

        if not active_subscribers:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            logger.info(
                "[DELIVERY_CLAIMED_BROADCAST] eventId=%s item=%s sala=%s sem garçons conectados (%.2fms)",
                payload["eventId"],
                payload["itemId"],
                room_key,
                elapsed_ms,
            )
            return {
                "eventId": payload["eventId"],
                "room": room_key,
                "deliveredCount": 0,
                "failedCount": 0,
                "elapsedMs": round(elapsed_ms, 3),
            }

        delivery_tasks = [
            self._send_waiter_ready_payload(sub, payload)
            for sub in active_subscribers
        ]
        failed_subscriptions = await asyncio.gather(*delivery_tasks)

        dead_subs = [sub for sub in failed_subscriptions if sub is not None]
        if dead_subs:
            async with self._lock:
                room_members = self._waiter_rooms.get(room_key)
                if room_members is not None:
                    room_members.difference_update(dead_subs)
                    if not room_members:
                        self._waiter_rooms.pop(room_key, None)

        delivered_count = len(active_subscribers) - len(dead_subs)
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0

        logger.info(
            "[DELIVERY_CLAIMED_BROADCAST] eventId=%s item=%s garcom=%s entregues=%d latencia=%.2fms",
            payload["eventId"],
            payload["itemId"],
            payload["claimedByWaiterId"],
            delivered_count,
            elapsed_ms,
        )

        return {
            "eventId": payload["eventId"],
            "room": room_key,
            "deliveredCount": delivered_count,
            "failedCount": len(dead_subs),
            "elapsedMs": round(elapsed_ms, 3),
        }

    async def _send_waiter_ready_payload(
        self,
        subscription: WaiterRoomSubscription,
        payload: dict,
    ) -> WaiterRoomSubscription | None:
        """
        Envia o frame JSON para um único socket com timeout estrito.
        Qualquer falha ou lentidão (backpressure/half-open) retorna a assinatura para remoção.
        """
        try:
            subscription.sequence += 1
            await asyncio.wait_for(
                subscription.websocket.send_json(payload),
                timeout=self.send_timeout,
            )
            return None
        except (
            TimeoutError,
            WebSocketDisconnect,
            OSError,
            RuntimeError,
            Exception,  # noqa: BLE001
        ) as exc:
            logger.warning(
                "[WS_DEAD_SOCKET_EVICTED] Garçom=%s sala=%s descartado por falha/timeout no envio: %s",
                subscription.user_id,
                subscription.room,
                type(exc).__name__,
            )
            return subscription

    async def connect_and_sync(
        self,
        websocket: WebSocket,
        restaurant_id: UUID | str | int,
        user_id: UUID | str | int,
        role: str,
        snapshot_factory,
        shift_status: str = ShiftStatus.ON_SHIFT.value,
    ) -> None:
        """Register and send a snapshot atomically relative to broadcasts."""
        subscription = Subscription(
            websocket,
            restaurant_id,
            user_id,
            role,
            shift_status=shift_status,
        )

        async with self._lock:
            snapshot = snapshot_factory()
            self._subscriptions.add(subscription)
            subscription.sequence += 1

            if isinstance(snapshot, dict):
                snapshot["queueVersion"] = self._queue_version

            try:
                await asyncio.wait_for(
                    websocket.send_json(
                        self._event(
                            "queue.snapshot",
                            restaurant_id,
                            self._queue_version,
                            sequence=subscription.sequence,
                            data=snapshot,
                        )
                    ),
                    timeout=self.send_timeout,
                )
            except Exception:
                self._subscriptions.discard(subscription)
                raise

    async def refresh_queue(
        self,
        websocket: WebSocket,
        snapshot_factory,
    ) -> bool:
        """Send a fresh queue snapshot to one connected subscriber."""
        async with self._lock:
            subscription = next(
                (
                    item
                    for item in self._subscriptions
                    if item.websocket is websocket
                ),
                None,
            )

            if subscription is None:
                return False

            try:
                snapshot = snapshot_factory()

                if isinstance(snapshot, dict):
                    snapshot["queueVersion"] = self._queue_version

                subscription.sequence += 1

                await asyncio.wait_for(
                    websocket.send_json(
                        self._event(
                            "queue.snapshot",
                            subscription.restaurant_id,
                            self._queue_version,
                            sequence=subscription.sequence,
                            data=snapshot,
                        )
                    ),
                    timeout=self.send_timeout,
                )

                return True

            except (
                OSError,
                RuntimeError,
                TimeoutError,
                WebSocketDisconnect,
            ):
                self._subscriptions.discard(subscription)
                return False

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._subscriptions = {
                subscription
                for subscription in self._subscriptions
                if subscription.websocket is not websocket
            }
        await self.leave_waiters_room(websocket, reason="disconnected")

    async def connect_tracking(
        self,
        websocket: WebSocket,
        order_id: UUID | str,
        snapshot_factory,
    ) -> None:
        """Register a tracking subscription and deliver initial snapshot."""
        subscription = TrackingSubscription(websocket, str(order_id))
        async with self._lock:
            self._tracking_subscriptions.add(subscription)

        snapshot = snapshot_factory()
        if snapshot:
            try:
                await asyncio.wait_for(
                    websocket.send_json(snapshot),
                    timeout=self.send_timeout,
                )
            except Exception:
                await self.disconnect_tracking(websocket)
                raise

    async def disconnect_tracking(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._tracking_subscriptions = {
                subscription
                for subscription in self._tracking_subscriptions
                if subscription.websocket is not websocket
            }

    async def publish_item_event(
        self,
        event_type: str,
        restaurant_id: UUID | str | int,
        item_data: dict,
        assigned_waiter_id: UUID | str | int | None,
    ) -> None:
        """Publish a mutation followed by a queue invalidation event."""
        async with self._lock:
            self._queue_version += 1
            queue_version = self._queue_version

            events = [
                self._event(
                    event_type,
                    restaurant_id,
                    queue_version,
                    item=item_data,
                ),
                self._event(
                    "queue.updated",
                    restaurant_id,
                    queue_version,
                    reason=event_type,
                    refreshRequired=True,
                ),
            ]

            deliveries = []

            for subscription in tuple(self._subscriptions):
                if subscription.restaurant_id != restaurant_id:
                    continue

                if subscription.role == "Cozinheiro":
                    recipient = True
                elif subscription.role in ALLOWED_WAITER_ROLES:
                    if subscription.shift_status != ShiftStatus.ON_SHIFT.value:
                        recipient = False
                    elif item_data.get("status") == "Pronto" or not assigned_waiter_id:
                        # RF06: If item is ready (Pronto), notify ALL active waiters of the restaurant.
                        recipient = True
                    else:
                        recipient = assigned_waiter_id == subscription.user_id
                else:
                    recipient = False

                if recipient:
                    deliveries.append(
                        self._send_events(subscription, events, timeout=self.send_timeout)
                    )

            failed = await asyncio.gather(*deliveries)

            self._subscriptions.difference_update(
                subscription
                for subscription in failed
                if subscription is not None
            )

            # Dispatch to customer tracking subscribers
            order_id_str = str(item_data.get("idPedido", ""))
            tracking_deliveries = []
            for t_sub in tuple(self._tracking_subscriptions):
                if t_sub.order_id == order_id_str:
                    item_status_frontend = STATUS_MAP_FRONTEND.get(
                        item_data.get("status", ""), item_data.get("status", "")
                    )
                    tracking_event = {
                        "type": "ITEM_UPDATE",
                        "item": {
                            "id": str(item_data.get("idItemPedido", "")),
                            "status": item_status_frontend,
                        },
                    }
                    tracking_deliveries.append(
                        self._send_tracking_event(
                            t_sub, tracking_event, timeout=self.send_timeout
                        )
                    )

            if tracking_deliveries:
                failed_tracking = await asyncio.gather(*tracking_deliveries)
                self._tracking_subscriptions.difference_update(
                    sub for sub in failed_tracking if sub is not None
                )

    async def publish_waiter_call(
        self,
        restaurant_id: UUID | str | int,
        mesa_data: dict,
        atendido: bool = False,
    ) -> None:
        """Transmite um chamado de garçom ou atendimento em tempo real para os garçons conectados."""
        async with self._lock:
            event_type = "mesa.garcom_atendido" if atendido else "mesa.garcom_chamado"
            event = self._event(
                event_type,
                restaurant_id,
                self._queue_version,
                mesa=mesa_data,
            )
            deliveries = []
            for subscription in tuple(self._subscriptions):
                if (
                    str(subscription.restaurant_id) == str(restaurant_id)
                    and subscription.role in ("Garcom", "Gerente", "Adm")
                ):
                    deliveries.append(
                        self._send_events(subscription, [event], timeout=self.send_timeout)
                    )

            if deliveries:
                failed = await asyncio.gather(*deliveries)
                self._subscriptions.difference_update(
                    sub for sub in failed if sub is not None
                )

    async def publish_event(
        self,
        restaurant_id: UUID | str | int,
        event_payload: dict,
    ) -> None:
        """Publica um evento genérico para os assinantes do restaurante."""
        async with self._lock:
            event = self._event(
                event_payload.get("type", "system.event"),
                restaurant_id,
                self._queue_version,
                **{k: v for k, v in event_payload.items() if k != "type"},
            )
            deliveries = [
                self._send_events(sub, [event], timeout=self.send_timeout)
                for sub in tuple(self._subscriptions)
                if str(sub.restaurant_id) == str(restaurant_id)
            ]
            if deliveries:
                failed = await asyncio.gather(*deliveries)
                self._subscriptions.difference_update(
                    sub for sub in failed if sub is not None
                )

    @staticmethod
    async def _send_events(
        subscription: Subscription,
        events: list[dict],
        timeout: float = SEND_TIMEOUT_SECONDS,
    ) -> Subscription | None:
        try:
            for event in events:
                subscription.sequence += 1

                await asyncio.wait_for(
                    subscription.websocket.send_json(
                        {
                            **event,
                            "sequence": subscription.sequence,
                        }
                    ),
                    timeout=timeout,
                )

        except (
            OSError,
            RuntimeError,
            TimeoutError,
            WebSocketDisconnect,
            Exception,  # noqa: BLE001
        ):
            return subscription

        return None

    @staticmethod
    async def _send_tracking_event(
        subscription: TrackingSubscription,
        event: dict,
        timeout: float = SEND_TIMEOUT_SECONDS,
    ) -> TrackingSubscription | None:
        try:
            await asyncio.wait_for(
                subscription.websocket.send_json(event),
                timeout=timeout,
            )
        except (
            OSError,
            RuntimeError,
            TimeoutError,
            WebSocketDisconnect,
            Exception,  # noqa: BLE001
        ):
            return subscription

        return None

    def _event(
        self,
        event_type: str,
        restaurant_id: UUID | str | int,
        queue_version: int,
        **data,
    ) -> dict:
        return {
            "type": event_type,
            "eventId": str(uuid4()),
            "queueVersion": queue_version,
            "occurredAt": datetime.now(UTC).isoformat(),
            "restaurantId": str(restaurant_id),
            **data,
        }


realtime_hub = RealtimeHub()
domain_event_bus.subscribe(OrderItemReadyEvent, realtime_hub.broadcast_item_ready)
domain_event_bus.subscribe(DeliveryClaimedEvent, realtime_hub.broadcast_delivery_claimed)