import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

SEND_TIMEOUT_SECONDS = 0.4


@dataclass(eq=False)
class Subscription:
    websocket: WebSocket
    restaurant_id: UUID | str | int
    user_id: UUID | str | int
    role: str
    sequence: int = 0


class RealtimeHub:
    """In-process WebSocket fan-out for authorized restaurant staff."""

    def __init__(self) -> None:
        self._subscriptions: set[Subscription] = set()
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
        subscription = Subscription(websocket, restaurant_id, user_id, role)
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

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._subscriptions = {
                subscription
                for subscription in self._subscriptions
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
                )
            ]
            events.append(
                self._event(
                    "queue.updated",
                    restaurant_id,
                    queue_version,
                    reason=event_type,
                    refreshRequired=True,
                )
            )

            deliveries = []
            for subscription in tuple(self._subscriptions):
                if subscription.restaurant_id != restaurant_id:
                    continue
                if subscription.role == "Cozinheiro":
                    recipient = True
                else:
                    recipient = (
                        subscription.role == "Garcom"
                        and assigned_waiter_id == subscription.user_id
                    )
                if not recipient:
                    continue
                deliveries.append(self._send_events(subscription, events))

            failed = await asyncio.gather(*deliveries)
            self._subscriptions.difference_update(
                subscription for subscription in failed if subscription is not None
            )

    @staticmethod
    async def _send_events(
        subscription: Subscription, events: list[dict]
    ) -> Subscription | None:
        try:
            for event in events:
                subscription.sequence += 1
                await asyncio.wait_for(
                    subscription.websocket.send_json(
                        {**event, "sequence": subscription.sequence}
                    ),
                    timeout=SEND_TIMEOUT_SECONDS,
                )
        except (OSError, RuntimeError, TimeoutError, WebSocketDisconnect):
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
