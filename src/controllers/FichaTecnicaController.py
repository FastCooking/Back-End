from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.schemas.FichaTecnicaSchema import (
    FichaTecnicaCompletaResponseDTO,
    FichaTecnicaCreateDTO,
    FichaTecnicaResponseDTO,
)
from src.services.FichaTecnicaService import FichaTecnicaService

router = APIRouter(prefix="/fichas-tecnica", tags=["fichas-tecnica"])


@router.post(
    "",
    response_model=FichaTecnicaResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
def criar_ficha_tecnica(payload: FichaTecnicaCreateDTO, db: Session = Depends(get_db)):
    try:
        service = FichaTecnicaService(db)
        existe = bool(service.repository.get_by_cardapio(payload.idCardapio))
        response = service.criar_ficha_tecnica(payload)
        status_code = status.HTTP_200_OK if existe else status.HTTP_201_CREATED
        return JSONResponse(
            status_code=status_code,
            content=response.model_dump(mode="json"),
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(exc)}",
        ) from exc


@router.put(
    "/cardapio/{idCardapio}",
    response_model=FichaTecnicaResponseDTO,
    status_code=status.HTTP_200_OK,
)
def atualizar_ficha_tecnica_por_cardapio(
    idCardapio: int,
    payload: FichaTecnicaCreateDTO,
    db: Session = Depends(get_db),
):
    if payload.idCardapio != idCardapio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O idCardapio do corpo deve coincidir com o da rota.",
        )

    try:
        service = FichaTecnicaService(db)
        return service.criar_ficha_tecnica(payload)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(exc)}",
        ) from exc


@router.get("/{idFichaTecnica}", response_model=FichaTecnicaResponseDTO)
def buscar_ficha_tecnica(idFichaTecnica: int, db: Session = Depends(get_db)):
    try:
        service = FichaTecnicaService(db)
        return service.buscar_por_id(idFichaTecnica)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(exc)}",
        ) from exc


@router.get("/cardapio/{idCardapio}", response_model=list[FichaTecnicaResponseDTO])
def listar_fichas_por_cardapio(idCardapio: int, db: Session = Depends(get_db)):
    try:
        service = FichaTecnicaService(db)
        return service.listar_por_cardapio(idCardapio)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(exc)}",
        ) from exc


@router.get(
    "/cardapio/{idCardapio}/completa",
    response_model=FichaTecnicaCompletaResponseDTO,
)
def buscar_ficha_tecnica_completa(idCardapio: int, db: Session = Depends(get_db)):
    try:
        service = FichaTecnicaService(db)
        return service.buscar_ficha_completa_por_cardapio(idCardapio)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(exc)}",
        ) from exc
