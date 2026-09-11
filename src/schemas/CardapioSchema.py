from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


CategoriaCardapio = Literal[
    "bebida",
    "entrada",
    "prato principal",
    "sobremesa"
]


class CardapioCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=150)
    preco: Decimal = Field(..., gt=0)
    categoria: CategoriaCardapio


class CardapioUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    preco: Decimal | None = Field(default=None, gt=0)
    categoria: CategoriaCardapio | None = None


class CardapioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    idCardapio: int
    idRestaurante: int
    nome: str
    preco: Decimal
    categoria: str
    status: bool