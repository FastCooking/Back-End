from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ItemPayloadSchema(BaseModel):
    item_id: int = Field(..., description="ID do produto no cardápio")
    quantidade: int = Field(..., ge=1)
    observacoes: Optional[str] = None

class PedidoCriarSchema(BaseModel):
    sessao_id: str = Field(..., description="Identificador único da sessão/mesa")
    idRestaurante: int = Field(...)
    idMesa: Optional[int] = None
    idGarcom: Optional[int] = None
    itens: List[ItemPayloadSchema] = Field(..., min_items=1)

class ItemResponseSchema(BaseModel):
    idItemPedido: int
    idCardapio: int
    quantidade: int
    precoUnitario: float
    status: str
    observacao: Optional[str]
    categoria: Optional[str]
    prioridade: int

    class Config:
        from_attributes = True

class PedidoResponseSchema(BaseModel):
    idPedido: int
    sessao_id: Optional[str]
    status: str
    dataAbertura: datetime
    itens: List[ItemResponseSchema] = []

    class Config:
        from_attributes = True
