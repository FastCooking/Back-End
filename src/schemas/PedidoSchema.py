import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PedidoItemCreate(BaseModel):
    idCardapio: uuid.UUID
    quantidade: int = Field(default=1, gt=0)
    observacao: str | None = None


class PedidoCreate(BaseModel):
    idMesa: uuid.UUID
    sessao_id: str | None = None
    itens: list[PedidoItemCreate] = Field(min_length=1)


class AdicionarItensMesaRequest(BaseModel):
    sessao_id: str | None = None
    itens: list[PedidoItemCreate] = Field(min_length=1)


class RemoverItemRequest(BaseModel):
    motivo: str = Field(..., min_length=1)

    @field_validator("motivo")
    @classmethod
    def validar_motivo(cls, motivo: str) -> str:
        return motivo.strip()


class ConfirmacaoCancelamentoCliente(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ItemPedidoStatusUpdate(BaseModel):
    status: Literal["Pendente", "Em preparo", "Pronto", "Entregue"]


class ItemPayloadSchema(BaseModel):
    item_id: uuid.UUID = Field(..., description="ID do produto no cardápio")
    quantidade: int = Field(..., ge=1)
    observacoes: str | None = None


class PedidoCriarSchema(BaseModel):
    sessao_id: str = Field(..., description="Identificador único da sessão/mesa")
    idRestaurante: uuid.UUID
    idMesa: uuid.UUID
    idGarcom: uuid.UUID | None = None
    itens: list[ItemPayloadSchema] = Field(min_length=1)


class ItemResponseSchema(BaseModel):
    idItemPedido: uuid.UUID
    idCardapio: uuid.UUID
    quantidade: int
    precoUnitario: float
    status: str
    observacao: str | None
    categoria: str | None = None
    prioridade: int = 1
    origem: str = "CLIENTE"

    model_config = ConfigDict(from_attributes=True)


class PedidoResponseSchema(BaseModel):
    idPedido: uuid.UUID
    sessao_id: str | None
    status: str
    dataAbertura: datetime
    itens: list[ItemResponseSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ItemPedidoQuantidadeUpdate(BaseModel):
    quantidade: int = Field(..., ge=0, description="Nova quantidade do item (0 cancela o item)")
    motivo: str | None = None

    @field_validator("motivo")
    @classmethod
    def validar_motivo(cls, motivo: str | None) -> str | None:
        return motivo.strip() if motivo is not None else None
