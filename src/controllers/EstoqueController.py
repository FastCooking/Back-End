from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.schemas.EstoqueSchema import EstoqueCreateDTO, EstoqueResponseDTO
from src.services.EstoqueService import EstoqueService

router = APIRouter(prefix="/insumos", tags=["insumos"])


@router.post("", response_model=EstoqueResponseDTO, status_code=status.HTTP_201_CREATED)
def criar_insumo(payload: EstoqueCreateDTO, db: Session = Depends(get_db)):
    try:
        service = EstoqueService(db)
        return service.criar_insumo(payload)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(exc)}",
        ) from exc


@router.get("/{idEstoque}", response_model=EstoqueResponseDTO)
def buscar_insumo_por_id(idEstoque: int, db: Session = Depends(get_db)):
    try:
        service = EstoqueService(db)
        return service.buscar_por_id(idEstoque)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(exc)}",
        ) from exc


@router.get("", response_model=list[EstoqueResponseDTO])
def listar_insumos(db: Session = Depends(get_db)):
    try:
        service = EstoqueService(db)
        return service.listar_insumos()
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(exc)}",
        ) from exc
