import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DeliveryState(StrEnum):
    """Estados canônicos do ciclo de vida de entrega de um item pronto."""

    READY = "READY"
    WAITING_DELIVERY_PICKUP = "WAITING_DELIVERY_PICKUP"
    IN_DELIVERY = "IN_DELIVERY"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_DELIVERY = "PENDING_DELIVERY"
    DELIVERED = "DELIVERED"


ACTIVE_DELIVERY_STATES = frozenset(
    {
        DeliveryState.IN_DELIVERY.value,
        DeliveryState.IN_PROGRESS.value,
        DeliveryState.PENDING_DELIVERY.value,
    }
)


class ClaimDeliveryRequestSchema(BaseModel):
    """Payload de entrada para POST /api/deliveries/claim."""

    model_config = ConfigDict(populate_by_name=True)

    itemId: uuid.UUID = Field(
        ...,
        validation_alias="itemId",
        description="UUID do ItemPedido com status 'Pronto' a ser assumido pelo garçom",
    )


class QueuedDeliveryItemSchema(BaseModel):
    """Representa um item na fila FIFO (WAITING_DELIVERY_PICKUP) aguardando garçom livre."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    deliveryId: str = Field(..., description="UUID do registro de Entrega")
    itemId: str = Field(..., description="UUID do ItemPedido")
    orderId: str = Field(..., description="UUID do Pedido/Comanda")
    restaurantId: str = Field(..., description="UUID do Restaurante")
    tableNumber: int | str = Field(..., description="Número da mesa de destino")
    itemName: str = Field(..., description="Nome do prato/item no cardápio")
    quantity: int = Field(..., gt=0, description="Quantidade do item")
    notes: str = Field(default="", description="Observações do item")
    status: str = Field(
        default=DeliveryState.WAITING_DELIVERY_PICKUP.value,
        description="Status na fila de espera (WAITING_DELIVERY_PICKUP)",
    )
    createdAt: str = Field(
        ..., description="Timestamp ISO 8601 de entrada na fila (FIFO)"
    )


class DeliveryClaimedResponseSchema(BaseModel):
    """Resposta HTTP de sucesso ao assumir a entrega de um item pronto."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    deliveryId: str
    itemId: str
    orderId: str
    restaurantId: str
    tableNumber: int | str
    itemName: str
    quantity: int
    status: str = Field(default=DeliveryState.IN_DELIVERY.value)
    itemStatus: str = Field(default="Pronto")
    claimedByWaiterId: str
    claimedAt: str


class DeliveryCompletedResponseSchema(BaseModel):
    """Resposta HTTP ao concluir uma entrega e acionar o despacho reativo da fila FIFO."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    deliveryId: str
    itemId: str
    orderId: str
    restaurantId: str
    tableNumber: int | str
    status: str = Field(default=DeliveryState.DELIVERED.value)
    itemStatus: str = Field(default="Entregue")
    completedByWaiterId: str
    deliveredAt: str
    nextQueuedItem: QueuedDeliveryItemSchema | None = Field(
        default=None,
        description="Próximo item mais antigo da fila FIFO ofertado após liberação do garçom",
    )


class DeliveryClaimedWsPayloadSchema(BaseModel):
    """
    Contrato estrito do evento WebSocket 'delivery:claimed' disparado para room:waiters:active
    para remoção imediata do card nas telas dos demais garçons.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    type: Literal["delivery:claimed"] = Field(default="delivery:claimed")
    event: Literal["delivery:claimed"] = Field(default="delivery:claimed")
    eventId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    itemId: str = Field(..., description="UUID do ItemPedido assumido")
    deliveryId: str = Field(..., description="UUID da Entrega")
    orderId: str = Field(..., description="UUID do Pedido")
    restaurantId: str = Field(..., description="UUID do Restaurante")
    tableNumber: int | str = Field(..., description="Número da mesa")
    claimedByWaiterId: str = Field(..., description="UUID do garçom que assumiu o item")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Timestamp ISO 8601 UTC da confirmação transacional do claim",
    )


@dataclass(frozen=True, slots=True)
class DeliveryClaimedEvent:
    """
    Evento de Domínio imutável emitido imediatamente após o commit transacional do claim.
    """

    restaurant_id: uuid.UUID | str
    order_id: uuid.UUID | str
    delivery_id: uuid.UUID | str
    item_id: uuid.UUID | str
    table_number: int | str
    claimed_by_waiter_id: uuid.UUID | str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_payload(self) -> DeliveryClaimedWsPayloadSchema:
        return DeliveryClaimedWsPayloadSchema(
            eventId=self.event_id,
            itemId=str(self.item_id),
            deliveryId=str(self.delivery_id),
            orderId=str(self.order_id),
            restaurantId=str(self.restaurant_id),
            tableNumber=self.table_number,
            claimedByWaiterId=str(self.claimed_by_waiter_id),
            timestamp=self.timestamp,
        )
