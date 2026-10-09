from datetime import datetime

from pydantic import BaseModel, Field


class ItemPayloadSchema(BaseModel):
    item_id: int = Field(..., description="ID do produto no cardápio")
    quantidade: int = Field(..., ge=1)
    observacoes: str | None = None

class PedidoCriarSchema(BaseModel):
    sessao_id: str = Field(..., description="Identificador único da sessão/mesa")
    idRestaurante: int = Field(...)
    idMesa: int | None = None
    idGarcom: int | None = None
    itens: list[ItemPayloadSchema] = Field(..., min_items=1)

class ItemResponseSchema(BaseModel):
    idItemPedido: int
    idCardapio: int
    quantidade: int
    precoUnitario: float
    status: str
    observacao: str | None
    categoria: str | None
    prioridade: int

    class Config:
        from_attributes = True

class PedidoResponseSchema(BaseModel):
    idPedido: int
    sessao_id: str | None
    status: str
    dataAbertura: datetime
    itens: list[ItemResponseSchema] = []

    class Config:
        from_attributes = True
