from pydantic import BaseModel, Field, field_validator


class FichaTecnicaItemDTO(BaseModel):
    idEstoque: int = Field(..., gt=0)
    quantidadeNecessaria: float = Field(..., gt=0)


class FichaTecnicaCreateDTO(BaseModel):
    idCardapio: int = Field(..., gt=0)
    insumos: list[FichaTecnicaItemDTO] = Field(..., min_length=1)

    @field_validator("insumos")
    @classmethod
    def validate_unique_ingredients(
        cls, value: list[FichaTecnicaItemDTO]
    ) -> list[FichaTecnicaItemDTO]:
        seen: set[int] = set()
        for item in value:
            if item.idEstoque in seen:
                raise ValueError(
                    "um mesmo insumo não pode ser associado duas vezes à mesma ficha técnica"
                )
            seen.add(item.idEstoque)
        return value


class FichaTecnicaItemResponseDTO(BaseModel):
    idEstoque: int
    quantidadeNecessaria: float

    model_config = {"from_attributes": True}


class CardapioFichaTecnicaItemDTO(BaseModel):
    idEstoque: int
    nome: str
    quantidadeNecessaria: float
    unidadeMedida: str = "UN"

    model_config = {"from_attributes": True}


class CardapioResumoDTO(BaseModel):
    idCardapio: int
    idRestaurante: int
    nome: str
    preco: float
    categoria: str
    status: bool

    model_config = {"from_attributes": True}


class FichaTecnicaResponseDTO(BaseModel):
    idFichaTecnica: int
    idCardapio: int
    insumos: list[FichaTecnicaItemResponseDTO]

    model_config = {"from_attributes": True}


class FichaTecnicaCompletaResponseDTO(BaseModel):
    cardapio: CardapioResumoDTO
    insumos: list[CardapioFichaTecnicaItemDTO]

    model_config = {"from_attributes": True}
