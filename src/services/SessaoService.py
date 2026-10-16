from datetime import UTC, datetime, timedelta
import uuid

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Sessao import Sessao


class SessaoService:

    @staticmethod
    def verificar_expiracao(sessao: Sessao, db: Session, limite_minutos: int = 10) -> bool:
        """Retorna True se a sessão estiver inativa há mais de limite_minutos."""
        agora = datetime.now()
        data_referencia = sessao.dataAbertura

        # Verifica se há pedido associado à mesa com itens recentes
        pedido_ativo = Pedido.get_active_for_table(db, sessao.idMesa)
        if pedido_ativo:
            itens = (
                db.query(ItemPedido)
                .filter(ItemPedido.idPedido == pedido_ativo.idPedido)
                .order_by(ItemPedido.dataCriacao.desc())
                .first()
            )
            if itens and itens.dataCriacao:
                data_referencia = itens.dataCriacao
            elif pedido_ativo.dataAbertura:
                data_referencia = pedido_ativo.dataAbertura

        if data_referencia is None:
            return False

        if hasattr(data_referencia, "tzinfo") and data_referencia.tzinfo is not None:
            agora = datetime.now(UTC)

        diferenca = agora - data_referencia
        return diferenca > timedelta(minutes=limite_minutos)

    @staticmethod
    def expirar_sessoes_inativas(db: Session, limite_minutos: int = 10) -> list[Sessao]:
        """Expira automaticamente sessões inativas há mais de limite_minutos."""
        sessoes_ativas = db.query(Sessao).filter(Sessao.status == "Ativa").all()
        expiradas = []

        for sessao in sessoes_ativas:
            if SessaoService.verificar_expiracao(sessao, db, limite_minutos):
                sessao.status = "Expirada"
                sessao.dataEncerramento = func.now()

                pedido_ativo = Pedido.get_active_for_table(db, sessao.idMesa)
                if pedido_ativo is None or pedido_ativo.status in ("Fechado", "Cancelado"):
                    mesa = Mesa.get_by_id(db, sessao.idMesa)
                    if mesa and mesa.status != "Disponivel":
                        mesa.status = "Disponivel"

                expiradas.append(sessao)

        if expiradas:
            db.commit()

        return expiradas

    @staticmethod
    def abrir_mesa(db: Session, idMesa: uuid.UUID | str) -> Sessao:
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
            if SessaoService.verificar_expiracao(sessao_ativa, db, limite_minutos=10):
                sessao_ativa.status = "Expirada"
                sessao_ativa.dataEncerramento = func.now()
                db.commit()
            else:
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