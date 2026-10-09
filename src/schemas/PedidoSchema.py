from typing import Literal

from pydantic import BaseModel, Field


class PedidoItemCreate(BaseModel):
    idCardapio: int = Field(gt=0)
    quantidade: int = Field(default=1, gt=0)
    observacao: str | None = None


class PedidoCreate(BaseModel):
    idMesa: int = Field(gt=0)
    itens: list[PedidoItemCreate] = Field(min_length=1)


class ItemPedidoStatusUpdate(BaseModel):
    status: Literal["Pendente", "Em preparo", "Pronto", "Entregue"]
