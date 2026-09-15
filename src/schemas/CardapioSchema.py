from pydantic import BaseModel, ConfigDict, Field


class CardapioCreate(BaseModel):
    idRestaurante: int | None = Field(default=1, gt=0)
    nome: str = Field(..., min_length=1, max_length=150)
    preco: float = Field(..., gt=0)
    categoria: str = Field(..., min_length=1, max_length=50)
    pathImage: str | None = None
    descricao: str | None = None


class CardapioUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    preco: float | None = Field(default=None, gt=0)
    categoria: str | None = Field(default=None, min_length=1, max_length=50)
    pathImage: str | None = None
    descricao: str | None = None


class CardapioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    idCardapio: int
    idRestaurante: int
    nome: str
    preco: float
    categoria: str
    pathImage: str | None = None
    descricao: str | None = None
    status: bool