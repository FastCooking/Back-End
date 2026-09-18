from pydantic import BaseModel, Field, field_validator


class EstoqueCreateDTO(BaseModel):
    nome: str = Field(..., min_length=1, max_length=150)
    quantidadeEmEstoque: float = Field(..., ge=0)
    quantidadeMinima: float = Field(..., ge=0)
    idRestaurante: int = Field(default=1, gt=0)
    unidadeMedida: str = Field(default="UN", min_length=1, max_length=20)
    pathImage: str | None = None

    @field_validator("nome")
    @classmethod
    def validate_nome(cls, value: str) -> str:
        nome = value.strip()
        if not nome:
            raise ValueError("nome não pode ser vazio")
        return nome


class EstoqueUpdateDTO(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    quantidadeEmEstoque: float | None = Field(default=None, ge=0)
    quantidadeMinima: float | None = Field(default=None, ge=0)
    idRestaurante: int | None = Field(default=None, gt=0)
    unidadeMedida: str | None = Field(default=None, min_length=1, max_length=20)
    pathImage: str | None = None

    @field_validator("nome")
    @classmethod
    def validate_nome(cls, value: str | None) -> str | None:
        if value is None:
            return value
        nome = value.strip()
        if not nome:
            raise ValueError("nome não pode ser vazio")
        return nome


class EstoqueResponseDTO(BaseModel):
    idEstoque: int
    nome: str
    quantidadeEmEstoque: float
    quantidadeMinima: float
    idRestaurante: int = 1
    unidadeMedida: str = "UN"
    pathImage: str | None = None

    model_config = {"from_attributes": True}
