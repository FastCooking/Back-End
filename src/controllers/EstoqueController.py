import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core.security import get_user_from_token
from src.database.connection import get_db
from src.models.Usuario import Usuario
from src.schemas.EstoqueSchema import (
    EstoqueCreateDTO,
    EstoqueResponseDTO,
    EstoqueUpdateDTO,
)
from src.services.EstoqueService import EstoqueService

router = APIRouter(prefix="/insumos", tags=["insumos"])

security_optional = HTTPBearer(auto_error=False)


def get_optional_user(
    credenciais: HTTPAuthorizationCredentials | None = Depends(security_optional),
    db: Session = Depends(get_db),
) -> Usuario | None:
    if credenciais is None:
        return None
    try:
        return get_user_from_token(credenciais.credentials, db)
    except Exception:
        return None


@router.post("", response_model=EstoqueResponseDTO, status_code=status.HTTP_201_CREATED)
def criar_insumo(
    payload: EstoqueCreateDTO,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(get_optional_user),
):
    try:
        service = EstoqueService(db)
        if not payload.idRestaurante and usuario and usuario.idRestaurante:
            payload.idRestaurante = usuario.idRestaurante
        return service.criar_insumo(payload)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {exc!s}",
        ) from exc


@router.get("/{idEstoque}", response_model=EstoqueResponseDTO)
def buscar_insumo_por_id(
    idEstoque: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(get_optional_user),
):
    try:
        service = EstoqueService(db)
        return service.buscar_por_id(idEstoque)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {exc!s}",
        ) from exc


@router.get("", response_model=list[EstoqueResponseDTO])
def listar_insumos(
    idRestaurante: uuid.UUID | None = Query(default=None, description="Filtrar por Restaurante"),
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(get_optional_user),
):
    try:
        service = EstoqueService(db)
        filtro_restaurante = idRestaurante or (usuario.idRestaurante if usuario else None)
        return service.listar_insumos(idRestaurante=filtro_restaurante)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {exc!s}",
        ) from exc


@router.put("/{idEstoque}", response_model=EstoqueResponseDTO)
def atualizar_insumo(
    idEstoque: uuid.UUID,
    payload: EstoqueUpdateDTO,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(get_optional_user),
):
    try:
        service = EstoqueService(db)
        return service.atualizar_insumo(idEstoque, payload)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {exc!s}",
        ) from exc


@router.delete("/{idEstoque}")
def excluir_insumo(
    idEstoque: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(get_optional_user),
):
    try:
        service = EstoqueService(db)
        return service.deletar_insumo(idEstoque)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {exc!s}",
        ) from exc
