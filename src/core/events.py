import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from src.schemas.KdsNotificationSchema import OrderItemReadyEvent

logger = logging.getLogger("fastcooking.events")

TEvent = TypeVar("TEvent")
AsyncEventHandler = Callable[[Any], Awaitable[Any]]


class DomainEventBus:
    """
    Barramento de Eventos de Domínio (In-Memory Pub/Sub Assíncrono).
    Garante desacoplamento total entre os Serviços de Domínio (Sprint 2) e os
    Gateways de Notificação em Tempo Real (WebSockets), isolando falhas de listeners.
    """

    def __init__(self) -> None:
        self._subscribers: dict[type[Any], list[AsyncEventHandler]] = defaultdict(list)

    def subscribe(
        self,
        event_type: type[TEvent],
        handler: Callable[[TEvent], Awaitable[Any]],
    ) -> None:
        """Registra um listener assíncrono de forma idempotente para um tipo de evento."""
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.debug(
                "Listener '%s' registrado para o evento '%s'.",
                getattr(handler, "__qualname__", str(handler)),
                event_type.__name__,
            )

    def unsubscribe(
        self,
        event_type: type[TEvent],
        handler: Callable[[TEvent], Awaitable[Any]],
    ) -> None:
        """Remove um listener previamente registrado."""
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Any) -> list[Any]:
        """
        Publica um Evento de Domínio de forma concorrente e não-bloqueante para todos os
        listeners inscritos, capturando e logando qualquer exceção de maneira isolada.
        """
        event_type = type(event)
        handlers = list(self._subscribers.get(event_type, ()))
        if not handlers:
            logger.debug(
                "Nenhum listener registrado para o evento '%s'.",
                event_type.__name__,
            )
            return []

        started_at = time.perf_counter()
        results = await asyncio.gather(
            *(self._invoke_handler(handler, event) for handler in handlers),
            return_exceptions=True,
        )
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0

        logger.info(
            "[EVENT_BUS] Evento=%s eventId=%s despachado para %d listener(s) em %.2fms",
            event_type.__name__,
            getattr(event, "event_id", "N/A"),
            len(handlers),
            elapsed_ms,
        )
        return results

    @staticmethod
    async def _invoke_handler(handler: AsyncEventHandler, event: Any) -> Any:
        try:
            return await handler(event)
        except Exception:
            logger.exception(
                "[EVENT_BUS_ERROR] Falha isolada no listener '%s' ao processar '%s'",
                getattr(handler, "__qualname__", str(handler)),
                type(event).__name__,
            )
            return None


domain_event_bus = DomainEventBus()

__all__ = [
    "DomainEventBus",
    "OrderItemReadyEvent",
    "domain_event_bus",
]

