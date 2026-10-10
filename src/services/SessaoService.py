from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException

from src.models.Mesa import Mesa
from src.models.Sessao import Sessao


class SessaoService:

    @staticmethod
    def abrir_mesa(db: Session, idMesa):
        mesa = Mesa.get_by_id(db, idMesa)

        if not mesa:
            raise HTTPException(
                status_code=404,
                detail="Mesa não encontrada",
            )

        sessao_ativa = (
            db.query(Sessao)
            .filter(
                Sessao.idMesa == mesa.idMesa,
                Sessao.status == "Ativa",
            )
            .first()
        )

        if sessao_ativa:
            return sessao_ativa

        try:
            sessao = Sessao(idMesa=mesa.idMesa, status="Ativa")
            mesa.status = "Indisponivel"

            db.add(sessao)
            db.commit()
            db.refresh(sessao)

            return sessao

        except IntegrityError:
            db.rollback()

            sessao_ativa = (
                db.query(Sessao)
                .filter(
                    Sessao.idMesa == idMesa,
                    Sessao.status == "Ativa",
                )
                .first()
            )

            if sessao_ativa:
                return sessao_ativa

            raise HTTPException(
                status_code=409,
                detail="Não foi possível abrir a sessão da mesa",
            )