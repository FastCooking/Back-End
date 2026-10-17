import uuid

from pydantic import BaseModel, Field


class MesaCreate(BaseModel):
    idRestaurante: uuid.UUID
    numero: int = Field(..., ge=1, description="Número da mesa")
    status: str = Field(default="Disponivel", description="Status da mesa ('Disponivel' ou 'Indisponivel')")


class MesaUpdate(BaseModel):
    numero: int | None = Field(default=None, ge=1)
    status: str | None = Field(default=None)


class MesaResponse(BaseModel):
    idMesa: uuid.UUID
    idRestaurante: uuid.UUID
    numero: int
    status: str

    model_config = {"from_attributes": True}
