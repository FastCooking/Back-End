from dataclasses import dataclass
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.ItemPedido import ItemPedido
from src.models.Pedido import Pedido


@dataclass(frozen=True)
class RF08ValidationResult:
    """Objeto de valor que encapsula a avaliação da regra de Zero Pendências (RF08)."""
    possui_pendencias: bool
    elegivel_assumir_entrega: bool
    itens_pendentes_count: int
    itens_prontos_count: int
    itens_ativos_count: int
    motivo_bloqueio: Optional[str] = None


class RF08Service:
    """
    Serviço de domínio responsável por aplicar a regra de negócio RF08 ('Zero Pendências')
    em qualquer operação de mutação da comanda (adição, remoção, cancelamento ou preparo).
    """

    STATUS_PENDENTES_PREPARO = ("Pendente", "Em preparo")

    @classmethod
    def reavaliar_comanda(cls, db: Session, pedido: Pedido) -> RF08ValidationResult:
        """
        Reavalia a comanda verificando se há itens em preparo, pendentes ou sobremesas retidas.
        Garante consistência antes do commit da transação.
        """
        itens = (
            db.query(ItemPedido)
            .filter(ItemPedido.idPedido == pedido.idPedido)
            .all()
        )

        itens_ativos = [it for it in itens if it.status != "Cancelado"]

        if not itens_ativos:
            return RF08ValidationResult(
                possui_pendencias=False,
                elegivel_assumir_entrega=False,
                itens_pendentes_count=0,
                itens_prontos_count=0,
                itens_ativos_count=0,
                motivo_bloqueio="A comanda não possui itens ativos.",
            )

        # Itens que ainda precisam de ação na cozinha
        itens_pendentes = [
            it
            for it in itens_ativos
            if it.status in cls.STATUS_PENDENTES_PREPARO or not it.liberadoParaPreparo
        ]
        itens_prontos = [it for it in itens_ativos if it.status == "Pronto"]

        possui_pendencias = len(itens_pendentes) > 0

        # Para assumir entrega, não pode haver pendências E deve haver itens prontos para serem entregues
        elegivel_assumir = (not possui_pendencias) and (len(itens_prontos) > 0)

        # Atualiza o status do Pedido se necessário mantendo consistência
        if pedido.status not in ("Fechado", "Cancelado"):
            if possui_pendencias and pedido.status in ("ProntoParaEntrega", "EmEntrega"):
                pedido.status = "Aberto"
            elif elegivel_assumir and pedido.status == "Aberto":
                pedido.status = "ProntoParaEntrega"

        motivo = None
        if possui_pendencias:
            motivo = (
                f"Existem {len(itens_pendentes)} item(ns) pendente(s) de preparo "
                "ou sobremesa(s) aguardando liberação."
            )
        elif len(itens_prontos) == 0 and all(it.status == "Entregue" for it in itens_ativos):
            motivo = "Todos os itens já foram entregues."

        db.flush()

        return RF08ValidationResult(
            possui_pendencias=possui_pendencias,
            elegivel_assumir_entrega=elegivel_assumir,
            itens_pendentes_count=len(itens_pendentes),
            itens_prontos_count=len(itens_prontos),
            itens_ativos_count=len(itens_ativos),
            motivo_bloqueio=motivo,
        )

    @classmethod
    def exigir_zero_pendencias(cls, db: Session, pedido: Pedido) -> RF08ValidationResult:
        """
        Guard-clause para a rota de 'Assumir Entrega'.
        Lança HTTP 409 Conflict se houver itens pendentes na comanda.
        """
        resultado = cls.reavaliar_comanda(db, pedido)
        if not resultado.elegivel_assumir_entrega:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Violação RF08 (Zero Pendências): {resultado.motivo_bloqueio}",
            )
        return resultado

