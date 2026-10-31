import uuid

from pydantic import BaseModel, ConfigDict, Field


class CardapioCreate(BaseModel):
    idRestaurante: uuid.UUID | None = Field(default=None)
    nome: str = Field(..., min_length=1, max_length=150)
    preco: float = Field(..., gt=0)
    categoria: str = Field(..., min_length=1, max_length=50)
    tempoPreparo: int = Field(default=15, gt=0, description="Tempo estimado de preparo em minutos")
    pathImage: str | None = None
    descricao: str | None = None


class CardapioUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    preco: float | None = Field(default=None, gt=0)
    categoria: str | None = Field(default=None, min_length=1, max_length=50)
    tempoPreparo: int | None = Field(default=None, gt=0, description="Tempo estimado de preparo em minutos")
    pathImage: str | None = None
    descricao: str | None = None


class CardapioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    idCardapio: uuid.UUID
    idRestaurante: uuid.UUID
    nome: str
    preco: float
    categoria: str
    tempoPreparo: int = 15
    pathImage: str | None = None
    descricao: str | None = None
    status: bool