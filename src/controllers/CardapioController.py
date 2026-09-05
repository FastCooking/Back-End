from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.models.Cardapio import Cardapio

router = APIRouter(prefix="/cardapio", tags=["cardapio"])


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_cardapio(payload: dict, db: Session = Depends(get_db)):
    try:
        item = Cardapio.create(
            db=db,
            idRestaurante=int(payload.get("idRestaurante", 1)),
            nome=str(payload["nome"]),
            preco=float(payload["preco"]),
            categoria=str(payload["categoria"]),
            pathImage=payload.get("pathImage"),
            descricao=payload.get("descricao"),
        )
        return {
            "idCardapio": item.idCardapio,
            "idRestaurante": item.idRestaurante,
            "nome": item.nome,
            "preco": float(item.preco),
            "categoria": item.categoria,
            "pathImage": item.pathImage,
            "descricao": item.descricao,
            "status": item.status,
        }
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campo obrigatório ausente: {exc.args[0]}",
        ) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(exc)}",
        ) from exc


@router.get("/{idCardapio}")
def buscar_cardapio_por_id(idCardapio: int, db: Session = Depends(get_db)):
    item = db.query(Cardapio).filter(Cardapio.idCardapio == idCardapio).first()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item de cardápio não encontrado.",
        )

    return {
        "idCardapio": item.idCardapio,
        "idRestaurante": item.idRestaurante,
        "nome": item.nome,
        "preco": float(item.preco),
        "categoria": item.categoria,
        "pathImage": item.pathImage,
        "descricao": item.descricao,
        "status": item.status,
    }
