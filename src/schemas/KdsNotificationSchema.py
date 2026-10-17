from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ShiftStatus(StrEnum):
    ON_SHIFT = "ON_SHIFT"
    OFF_SHIFT = "OFF_SHIFT"


class ReadyOrderItemSchema(BaseModel):
    """Representa um item pronto dentro do contrato do evento kds:item_ready."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str = Field(..., description="UUID do ItemPedido pronto")
    name: str = Field(..., min_length=1, description="Nome do prato/item no cardápio")
    quantity: int = Field(..., gt=0, description="Quantidade pronta para retirada")


class KdsItemReadyPayloadSchema(BaseModel):
    """
    Contrato estrito do payload WebSocket para o evento 'kds:item_ready'.
    Garante idempotência (eventId), rastreabilidade temporal (ISO 8601) e
    tratamento padronizado de observações nulas como string vazia.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    type: Literal["kds:item_ready"] = Field(
        default="kds:item_ready",
        description="Identificador do tipo de evento no protocolo WebSocket",
    )
    event: Literal["kds:item_ready"] = Field(
        default="kds:item_ready",
        description="Nome canônico do evento para roteamento no cliente",
    )
    eventId: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID v4 exclusivo para deduplicação/idempotência no app do garçom",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Data/hora da emissão em formato ISO 8601 UTC",
    )
    restaurantId: str = Field(
        ...,
        description="UUID do restaurante (isolamento multi-tenant)",
    )
    orderId: str = Field(
        ...,
        description="UUID do pedido/comanda",
    )
    tableNumber: int | str = Field(
        ...,
        description="Número ou identificador da mesa para entrega",
    )
    items: list[ReadyOrderItemSchema] = Field(
        ...,
        min_length=1,
        description="Lista de itens prontos para retirada imediata na cozinha",
    )
    notes: str = Field(
        default="",
        description="Observações do item/pedido (nulos padronizados para string vazia)",
    )

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str:
        if value is None:
            return ""
        return str(value).strip()


@dataclass(frozen=True, slots=True)
class OrderItemReadyEvent:
    """
    Evento de Domínio imutável disparado quando um item atinge o status 'Pronto' no KDS.
    Desacopla a regra de negócio da Sprint 2 (PedidoService) da camada de transporte WebSocket.
    """

    restaurant_id: uuid.UUID | str
    order_id: uuid.UUID | str
    table_number: int | str
    item_id: uuid.UUID | str
    item_name: str
    quantity: int
    notes: str | None = ""
    assigned_waiter_id: uuid.UUID | str | None = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_payload(self) -> KdsItemReadyPayloadSchema:
        """Converte o Evento de Domínio para o contrato validado do WebSocket."""
        return KdsItemReadyPayloadSchema(
            eventId=self.event_id,
            timestamp=self.occurred_at,
            restaurantId=str(self.restaurant_id),
            orderId=str(self.order_id),
            tableNumber=self.table_number,
            items=[
                ReadyOrderItemSchema(
                    id=str(self.item_id),
                    name=self.item_name or "Item do Cardápio",
                    quantity=self.quantity,
                )
            ],
            notes=self.notes or "",
        )

