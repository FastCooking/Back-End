import uuid
from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.core.realtime import realtime_hub
from src.models.Cardapio import Cardapio
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Usuario import Usuario
from src.schemas.PedidoSchema import PedidoCreate, PedidoItemCreate

STATUS_ITEM = ("Pendente", "Em preparo", "Pronto", "Entregue")


class PedidoService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, dados: PedidoCreate, usuario: Usuario) -> dict:
        mesa = (
            self.db.query(Mesa)
            .filter(
                Mesa.idMesa == dados.idMesa,
                Mesa.idRestaurante == usuario.idRestaurante,
            )
            .first()
        )
        if mesa is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mesa não encontrada neste restaurante.",
            )

        cardapios = self._validate_menu_items(dados.itens, usuario.idRestaurante)
        try:
            pedido = Pedido.create(
                db=self.db,
                idRestaurante=usuario.idRestaurante,
                idMesa=mesa.idMesa,
                idGarcom=usuario.idUsuario,
                sessao_id=dados.sessao_id,
                commit=False,
            )
            itens = [
                ItemPedido.create(
                    db=self.db,
                    idPedido=pedido.idPedido,
                    idCardapio=cardapio.idCardapio,
                    quantidade=item.quantidade,
                    precoUnitario=float(cardapio.preco),
                    observacao=item.observacao,
                    categoria=cardapio.categoria,
                    commit=False,
                )
                for item, cardapio in zip(dados.itens, cardapios, strict=True)
            ]
            self.db.commit()
            self.db.refresh(pedido)
            for item in itens:
                self.db.refresh(item)
        except Exception:
            self.db.rollback()
            raise

        return {
            "pedido": self._pedido_data(pedido),
            "itens": [self._item_data(item) for item in itens],
            "events": [
                self._event_data("item.created", pedido, item) for item in itens
            ],
        }

    def add_items(
        self, idPedido: uuid.UUID, itens: list[PedidoItemCreate], usuario: Usuario
    ) -> dict:
        pedido = self._get_assigned_order(idPedido, usuario)
        cardapios = self._validate_menu_items(itens, usuario.idRestaurante)
        try:
            novos_itens = [
                ItemPedido.create(
                    db=self.db,
                    idPedido=pedido.idPedido,
                    idCardapio=cardapio.idCardapio,
                    quantidade=item.quantidade,
                    precoUnitario=float(cardapio.preco),
                    observacao=item.observacao,
                    categoria=cardapio.categoria,
                    commit=False,
                )
                for item, cardapio in zip(itens, cardapios, strict=True)
            ]
            self.db.commit()
            for item in novos_itens:
                self.db.refresh(item)
        except Exception:
            self.db.rollback()
            raise

        return {
            "itens": [self._item_data(item) for item in novos_itens],
            "events": [
                self._event_data("item.created", pedido, item) for item in novos_itens
            ],
        }

    def update_item_status(
        self, idItemPedido: uuid.UUID, novo_status: str, usuario: Usuario
    ) -> dict:
        item = (
            self.db.query(ItemPedido)
            .filter(ItemPedido.idItemPedido == idItemPedido)
            .with_for_update()
            .first()
        )
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item do pedido não encontrado.",
            )

        pedido = Pedido.get_by_id(self.db, item.idPedido)
        if pedido is None or pedido.idRestaurante != usuario.idRestaurante:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item do pedido não encontrado.",
            )

        current_index = (
            STATUS_ITEM.index(item.status) if item.status in STATUS_ITEM else -1
        )
        if current_index < 0 or current_index == len(STATUS_ITEM) - 1:
            self._invalid_transition(item.status, novo_status)
        expected_status = STATUS_ITEM[current_index + 1]
        if novo_status != expected_status:
            self._invalid_transition(item.status, novo_status)

        try:
            item.update_stats(self.db, novo_status, commit=False)
            self.db.commit()
            self.db.refresh(item)
            self.db.refresh(pedido)
        except Exception:
            self.db.rollback()
            raise

        return {
            "item": self._item_data(item),
            "event": self._event_data("item.status_changed", pedido, item),
        }

    def queue_snapshot(self, usuario: Usuario) -> dict:
        query = (
            self.db.query(ItemPedido, Pedido)
            .join(Pedido, ItemPedido.idPedido == Pedido.idPedido)
            .filter(
                Pedido.idRestaurante == usuario.idRestaurante,
                Pedido.status.notin_(["Fechado", "Cancelado"]),
                ItemPedido.status != "Cancelado",
            )
        )
        if usuario.funcao == "Garcom":
            query = query.filter(Pedido.idGarcom == usuario.idUsuario)

        rows = query.all()
        return {
            "items": [self._item_data(item) for item, _ in rows],
            "priorityApplied": False,
            "queueVersion": realtime_hub.queue_version,
        }

    async def publish_events(self, events: Iterable[dict]) -> None:
        for event in events:
            await realtime_hub.publish_item_event(
                event_type=event["type"],
                restaurant_id=event["restaurantId"],
                item_data=event["item"],
                assigned_waiter_id=event["assignedWaiterId"],
            )

    def _get_assigned_order(self, idPedido: uuid.UUID, usuario: Usuario) -> Pedido:
        pedido = (
            self.db.query(Pedido)
            .filter(
                Pedido.idPedido == idPedido,
                Pedido.idRestaurante == usuario.idRestaurante,
                Pedido.idGarcom == usuario.idUsuario,
            )
            .first()
        )
        if pedido is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido não encontrado.",
            )
        return pedido

    def _validate_menu_items(
        self, itens: list[PedidoItemCreate], idRestaurante: uuid.UUID
    ) -> list[Cardapio]:
        cardapios: list[Cardapio] = []
        for item in itens:
            cardapio = (
                self.db.query(Cardapio)
                .filter(
                    Cardapio.idCardapio == item.idCardapio,
                    Cardapio.idRestaurante == idRestaurante,
                    Cardapio.status.is_(True),
                )
                .first()
            )
            if cardapio is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Item do cardápio não encontrado neste restaurante.",
                )
            cardapios.append(cardapio)
        return cardapios

    @staticmethod
    def _invalid_transition(current_status: str, requested_status: str) -> None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Transição inválida de '{current_status}' para "
                f"'{requested_status}'."
            ),
        )

    @staticmethod
    def _pedido_data(pedido: Pedido) -> dict:
        return {
            "idPedido": pedido.idPedido,
            "sessao_id": pedido.sessao_id,
            "idRestaurante": pedido.idRestaurante,
            "idMesa": pedido.idMesa,
            "idGarcom": pedido.idGarcom,
            "status": pedido.status,
        }

    @staticmethod
    def _item_data(item: ItemPedido) -> dict:
        return {
            "idItemPedido": str(item.idItemPedido),
            "idPedido": str(item.idPedido),
            "idCardapio": str(item.idCardapio),
            "quantidade": item.quantidade,
            "precoUnitario": float(item.precoUnitario),
            "status": item.status,
            "observacao": item.observacao,
            "categoria": item.categoria,
            "prioridade": item.prioridade,
        }

    @classmethod
    def _event_data(cls, event_type: str, pedido: Pedido, item: ItemPedido) -> dict:
        return {
            "type": event_type,
            "restaurantId": pedido.idRestaurante,
            "assignedWaiterId": pedido.idGarcom,
            "item": cls._item_data(item),
        }
