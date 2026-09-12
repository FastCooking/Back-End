from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.core.security import exigir_funcao
from src.database.connection import get_db
from src.models.Usuario import Usuario
from src.schemas.CardapioSchema import (
    CardapioCreate,
    CardapioResponse,
    CardapioUpdate,
)
from src.services.CardapioService import CardapioService

router = APIRouter(
    prefix="/cardapio",
    tags=["Cardápio"]
)


@router.post(
    "",
    response_model=CardapioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar item do cardápio"
)
def criar_item(
    dados: CardapioCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Gerente"))
):
    service = CardapioService(db)

    return service.criar(
        dados=dados,
        usuario=usuario
    )


@router.get(
    "",
    response_model=list[CardapioResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar itens do cardápio"
)
def listar_itens(
    idRestaurante: int = Query(...),
    db: Session = Depends(get_db)
):
    service = CardapioService(db)

    return service.listar(
        idRestaurante=idRestaurante
    )


@router.get(
    "/{idCardapio}",
    response_model=CardapioResponse,
    status_code=status.HTTP_200_OK,
    summary="Buscar item do cardápio"
)
def buscar_item(
    idCardapio: int,
    db: Session = Depends(get_db)
):
    service = CardapioService(db)

    return service.buscar_por_id(idCardapio)


@router.put(
    "/{idCardapio}",
    response_model=CardapioResponse,
    status_code=status.HTTP_200_OK,
    summary="Editar item do cardápio"
)
def editar_item(
    idCardapio: int,
    dados: CardapioUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Gerente"))
):
    service = CardapioService(db)

    return service.editar(
        idCardapio=idCardapio,
        dados=dados,
        usuario=usuario
    )


@router.delete(
    "/{idCardapio}",
    status_code=status.HTTP_200_OK,
    summary="Desativar item do cardápio"
)
def excluir_item(
    idCardapio: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Gerente"))
):
    service = CardapioService(db)

    service.excluir(
        idCardapio=idCardapio,
        usuario=usuario
    )

    return {
        "message": "Item do cardápio desativado com sucesso."
    }