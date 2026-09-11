from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.schemas.RestauranteSchema import (
    RestauranteCreate,
    RestauranteResponse,
    RestauranteStatusUpdate,
    RestauranteUpdate,
)
from src.services.RestauranteService import RestauranteService

router = APIRouter(prefix="/restaurantes", tags=["Restaurantes"])


@router.post(
    "",
    response_model=RestauranteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo restaurante",
    description="Cadastra um novo restaurante no sistema com validações de CNPJ, CEP, Telefone e E-mail único.",
)
def criar_restaurante(
    dados: RestauranteCreate,
    db: Session = Depends(get_db),
) -> RestauranteResponse:
    service = RestauranteService(db)
    return service.create(dados)


@router.get(
    "",
    response_model=list[RestauranteResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar restaurantes",
    description="Retorna a lista de restaurantes cadastrados com suporte a busca, filtros e paginação.",
)
def listar_restaurantes(
    status_filtro: bool | None = Query(
        default=None, alias="status", description="Filtrar por status ativo/inativo"
    ),
    busca: str | None = Query(
        default=None, description="Buscar por nome, CNPJ ou e-mail"
    ),
    skip: int = Query(default=0, ge=0, description="Registros a ignorar (offset)"),
    limit: int = Query(
        default=100, ge=1, le=500, description="Quantidade máxima de registros"
    ),
    db: Session = Depends(get_db),
) -> list[RestauranteResponse]:
    service = RestauranteService(db)
    return service.list_all(
        status_filtro=status_filtro,
        busca=busca,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{idRestaurante}",
    response_model=RestauranteResponse,
    status_code=status.HTTP_200_OK,
    summary="Obter restaurante por ID",
    description="Retorna os dados cadastrais de um restaurante específico.",
)
def obter_restaurante_por_id(
    idRestaurante: int,
    db: Session = Depends(get_db),
) -> RestauranteResponse:
    service = RestauranteService(db)
    return service.get_by_id(idRestaurante)


@router.put(
    "/{idRestaurante}",
    response_model=RestauranteResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar restaurante",
    description="Atualiza os dados de um restaurante existente com validações.",
)
def atualizar_restaurante(
    idRestaurante: int,
    dados: RestauranteUpdate,
    db: Session = Depends(get_db),
) -> RestauranteResponse:
    service = RestauranteService(db)
    return service.update(idRestaurante, dados)


@router.patch(
    "/{idRestaurante}",
    response_model=RestauranteResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar parcialmente restaurante",
    description="Atualiza campos específicos de um restaurante.",
)
def atualizar_parcial_restaurante(
    idRestaurante: int,
    dados: RestauranteUpdate,
    db: Session = Depends(get_db),
) -> RestauranteResponse:
    service = RestauranteService(db)
    return service.update(idRestaurante, dados)


@router.patch(
    "/{idRestaurante}/status",
    response_model=RestauranteResponse,
    status_code=status.HTTP_200_OK,
    summary="Alterar status do restaurante",
    description="Ativa ou desativa um restaurante no sistema.",
)
def alterar_status_restaurante(
    idRestaurante: int,
    dados: RestauranteStatusUpdate,
    db: Session = Depends(get_db),
) -> RestauranteResponse:
    service = RestauranteService(db)
    return service.change_status(idRestaurante, dados.status)


@router.delete(
    "/{idRestaurante}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar restaurante",
    description="Desativa o restaurante no banco de dados.",
)
def deletar_restaurante(
    idRestaurante: int,
    db: Session = Depends(get_db),
):
    service = RestauranteService(db)
    service.delete(idRestaurante)
