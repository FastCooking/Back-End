import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

SEND_TIMEOUT_SECONDS = 0.4


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


@dataclass(eq=False)
class TrackingSubscription:
    websocket: WebSocket
    order_id: str


class RealtimeHub:
    """In-process WebSocket fan-out for authorized restaurant staff and customer order tracking."""

    def __init__(self) -> None:
        self._subscriptions: set[Subscription] = set()
        self._tracking_subscriptions: set[TrackingSubscription] = set()
        self._lock = asyncio.Lock()
        self._queue_version = 0

    @property
    def queue_version(self) -> int:
        return self._queue_version

    async def connect_and_sync(
        self,
        websocket: WebSocket,
        restaurant_id: UUID | str | int,
        user_id: UUID | str | int,
        role: str,
        snapshot_factory,
    ) -> None:
        """Register and send a snapshot atomically relative to broadcasts."""
        subscription = Subscription(
            websocket, restaurant_id, user_id, role
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
                    timeout=SEND_TIMEOUT_SECONDS,
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
                    timeout=SEND_TIMEOUT_SECONDS,
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
                    timeout=SEND_TIMEOUT_SECONDS,
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
                elif subscription.role == "Garcom":
                    # RF06: If item is ready (Pronto), notify ALL waiters of the restaurant.
                    # Otherwise, notify the assigned waiter.
                    if item_data.get("status") == "Pronto" or not assigned_waiter_id:
                        recipient = True
                    else:
                        recipient = assigned_waiter_id == subscription.user_id
                else:
                    recipient = False

                if recipient:
                    deliveries.append(
                        self._send_events(subscription, events)
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
                        self._send_tracking_event(t_sub, tracking_event)
                    )

            if tracking_deliveries:
                failed_tracking = await asyncio.gather(*tracking_deliveries)
                self._tracking_subscriptions.difference_update(
                    sub for sub in failed_tracking if sub is not None
                )

    @staticmethod
    async def _send_events(
        subscription: Subscription,
        events: list[dict],
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
                    timeout=SEND_TIMEOUT_SECONDS,
                )

        except (
            OSError,
            RuntimeError,
            TimeoutError,
            WebSocketDisconnect,
        ):
            return subscription

        return None

    @staticmethod
    async def _send_tracking_event(
        subscription: TrackingSubscription,
        event: dict,
    ) -> TrackingSubscription | None:
        try:
            await asyncio.wait_for(
                subscription.websocket.send_json(event),
                timeout=SEND_TIMEOUT_SECONDS,
            )
        except (
            OSError,
            RuntimeError,
            TimeoutError,
            WebSocketDisconnect,
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