from collections.abc import Iterable
from datetime import UTC, datetime
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.core.realtime import realtime_hub
from src.models.Cardapio import Cardapio
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Usuario import Usuario
from src.schemas.PedidoSchema import PedidoCreate, PedidoItemCreate
from src.services.PrioridadeKDS import calcular_pontuacao, eh_sobremesa

STATUS_ITEM = ("Pendente", "Em preparo", "Pronto", "Entregue")


class PedidoService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, dados: PedidoCreate, usuario: Usuario | None = None) -> dict:
        mesa = (
            self.db.query(Mesa)
            .filter(Mesa.idMesa == dados.idMesa)
            .first()
        )
        if mesa is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mesa não encontrada.",
            )

        if usuario is not None and mesa.idRestaurante != usuario.idRestaurante:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mesa não encontrada neste restaurante.",
            )

        idRestaurante = usuario.idRestaurante if usuario else mesa.idRestaurante
        idGarcom = usuario.idUsuario if usuario else None

        cardapios = self._validate_menu_items(
            dados.itens, idRestaurante
        )

        try:
            pedido = Pedido.get_active_for_table(self.db, mesa.idMesa)
            if pedido is None or pedido.status in ("Fechado", "Cancelado"):
                pedido = Pedido.create(
                    db=self.db,
                    idRestaurante=idRestaurante,
                    idMesa=mesa.idMesa,
                    idGarcom=idGarcom,
                    sessao_id=dados.sessao_id,
                    commit=False,
                )
            elif idGarcom and pedido.idGarcom is None:
                pedido.idGarcom = idGarcom

            itens = [
                ItemPedido.create(
                    db=self.db,
                    idPedido=pedido.idPedido,
                    idCardapio=cardapio.idCardapio,
                    quantidade=item.quantidade,
                    precoUnitario=float(cardapio.preco),
                    observacao=item.observacao,
                    categoria=cardapio.categoria,
                    liberadoParaPreparo=not eh_sobremesa(
                        cardapio.categoria
                    ),
                    commit=False,
                )
                for item, cardapio in zip(
                    dados.itens, cardapios, strict=True
                )
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
                self._event_data("item.created", pedido, item)
                for item in itens
            ],
        }

    def add_items(
        self,
        idPedido: uuid.UUID,
        itens: list[PedidoItemCreate],
        usuario: Usuario | None = None,
    ) -> dict:
        pedido = self._get_assigned_order(idPedido, usuario)
        idRestaurante = usuario.idRestaurante if usuario else pedido.idRestaurante
        cardapios = self._validate_menu_items(
            itens, idRestaurante
        )

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
                    liberadoParaPreparo=not eh_sobremesa(
                        cardapio.categoria
                    ),
                    commit=False,
                )
                for item, cardapio in zip(
                    itens, cardapios, strict=True
                )
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
                self._event_data("item.created", pedido, item)
                for item in novos_itens
            ],
        }

    def get_order(self, idPedido: uuid.UUID) -> dict:
        pedido = Pedido.get_by_id(self.db, idPedido)
        if pedido is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido não encontrado.",
            )
        itens = (
            self.db.query(ItemPedido)
            .filter(ItemPedido.idPedido == idPedido)
            .order_by(ItemPedido.dataCriacao.asc())
            .all()
        )
        return {
            "pedido": self._pedido_data(pedido),
            "itens": [self._item_data(item) for item in itens],
        }

    def get_order_tracking(self, idPedido: uuid.UUID) -> dict:
        pedido = Pedido.get_by_id(self.db, idPedido)
        if not pedido:
            return {"type": "ERROR", "message": "Pedido não encontrado."}

        itens = (
            self.db.query(ItemPedido)
            .filter(ItemPedido.idPedido == idPedido)
            .order_by(ItemPedido.dataCriacao.asc())
            .all()
        )

        item_statuses = [it.status for it in itens]
        if not item_statuses or all(s == "Pendente" for s in item_statuses):
            overall_status = "PENDING"
        elif any(s == "Em preparo" for s in item_statuses):
            overall_status = "IN_PREPARATION"
        elif all(s in ("Pronto", "Entregue") for s in item_statuses) and any(s == "Pronto" for s in item_statuses):
            overall_status = "READY"
        elif all(s == "Entregue" for s in item_statuses):
            overall_status = "DELIVERED"
        elif all(s == "Cancelado" for s in item_statuses):
            overall_status = "CANCELLED"
        else:
            overall_status = "IN_PREPARATION"

        table_number = pedido.mesa.numero if pedido.mesa else None
        status_map = {
            "Pendente": "PENDING",
            "Em preparo": "IN_PREPARATION",
            "Pronto": "READY",
            "Entregue": "DELIVERED",
            "Cancelado": "CANCELLED",
        }

        created_at = (
            pedido.dataAbertura.isoformat()
            if getattr(pedido, "dataAbertura", None)
            else datetime.now(UTC).isoformat()
        )

        return {
            "type": "ORDER_UPDATE",
            "order": {
                "id": str(pedido.idPedido),
                "customerName": f"Mesa {table_number}" if table_number else "Cliente",
                "tableNumber": table_number,
                "status": overall_status,
                "estimatedMinutesMin": 15,
                "estimatedMinutesMax": 30,
                "queuePosition": 1,
                "createdAt": created_at,
                "updatedAt": datetime.now(UTC).isoformat(),
                "items": [
                    {
                        "id": str(it.idItemPedido),
                        "name": it.cardapio.nome if it.cardapio else "Item",
                        "quantity": it.quantidade,
                        "notes": it.observacao or "",
                        "status": status_map.get(it.status, it.status),
                    }
                    for it in itens
                ],
            },
        }

    def update_item_status(
        self,
        idItemPedido: uuid.UUID,
        novo_status: str,
        usuario: Usuario,
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

        if not item.liberadoParaPreparo:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este item ainda não foi liberado para preparo.",
            )

        current_index = (
            STATUS_ITEM.index(item.status)
            if item.status in STATUS_ITEM
            else -1
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
            "event": self._event_data(
                "item.status_changed", pedido, item
            ),
        }

    def liberar_sobremesa(
        self,
        idItemPedido: uuid.UUID,
        usuario: Usuario,
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

        if not eh_sobremesa(item.categoria):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Somente sobremesas podem ser liberadas por esta rota.",
            )

        if pedido.status in ("Fechado", "Cancelado"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Não é possível liberar sobremesa de um pedido encerrado.",
            )

        if item.status == "Cancelado":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Não é possível liberar um item cancelado.",
            )

        if item.liberadoParaPreparo:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Esta sobremesa já foi liberada.",
            )

        try:
            item.liberadoParaPreparo = True
            self.db.commit()
            self.db.refresh(item)
            self.db.refresh(pedido)

        except Exception:
            self.db.rollback()
            raise

        return {
            "item": self._item_data(item),
            "events": [
                self._event_data(
                    "item.dessert_released", pedido, item
                )
            ],
        }

    def cancelar_item(
        self,
        idItemPedido: uuid.UUID,
        usuario: Usuario,
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

        if pedido.status in ("Fechado", "Cancelado"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Não é possível cancelar item de um pedido encerrado ou cancelado.",
            )

        if item.status == "Cancelado":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O item já está cancelado.",
            )

        if item.status != "Pendente":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Não é possível cancelar o item. O preparo já foi iniciado ou finalizado (status atual: '{item.status}').",
            )

        try:
            item.update_stats(self.db, "Cancelado", commit=False)
            self.db.commit()
            self.db.refresh(item)
            self.db.refresh(pedido)
        except Exception:
            self.db.rollback()
            raise

        return {
            "item": self._item_data(item),
            "event": self._event_data(
                "item.status_changed", pedido, item
            ),
        }

    def queue_snapshot(self, usuario: Usuario) -> dict:
        query = (
            self.db.query(ItemPedido, Pedido)
            .join(Pedido, ItemPedido.idPedido == Pedido.idPedido)
            .filter(
                Pedido.idRestaurante == usuario.idRestaurante,
                Pedido.status.notin_(["Fechado", "Cancelado"]),
                ItemPedido.status != "Cancelado",
                ItemPedido.liberadoParaPreparo.is_(True),
                ItemPedido.status.in_(["Pendente", "Em preparo"]),
            )
        )

        if usuario.funcao == "Garcom":
            query = query.filter(
                Pedido.idGarcom == usuario.idUsuario
            )

        rows = query.all()
        items = [self._item_data(item) for item, _ in rows]

        items.sort(
            key=lambda item: (
                -item["pontuacao"],
                item["dataCriacao"],
                item["idItemPedido"],
            )
        )

        return {
            "items": items,
            "priorityApplied": True,
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

    def _get_assigned_order(
        self,
        idPedido: uuid.UUID,
        usuario: Usuario | None = None,
    ) -> Pedido:
        query = self.db.query(Pedido).filter(Pedido.idPedido == idPedido)
        if usuario is not None and getattr(usuario, "idRestaurante", None):
            query = query.filter(Pedido.idRestaurante == usuario.idRestaurante)

        pedido = query.first()

        if pedido is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido não encontrado.",
            )

        if usuario is not None and pedido.idGarcom is None and getattr(usuario, "funcao", None) == "Garcom":
            pedido.idGarcom = usuario.idUsuario

        return pedido

    def _validate_menu_items(
        self,
        itens: list[PedidoItemCreate],
        idRestaurante: uuid.UUID,
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
    def _invalid_transition(
        current_status: str,
        requested_status: str,
    ) -> None:
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
        data_criacao = item.dataCriacao

        tempo_espera, pontuacao = calcular_pontuacao(
            item.categoria,
            data_criacao,
        )

        nome_item = item.cardapio.nome if item.cardapio else None
        numero_mesa = (
            item.pedido.mesa.numero
            if (item.pedido and item.pedido.mesa)
            else None
        )

        return {
            "idItemPedido": str(item.idItemPedido),
            "idPedido": str(item.idPedido),
            "idCardapio": str(item.idCardapio),
            "nomeItem": nome_item,
            "numeroMesa": numero_mesa,
            "quantidade": item.quantidade,
            "precoUnitario": float(item.precoUnitario),
            "status": item.status,
            "observacao": item.observacao,
            "categoria": item.categoria,
            "prioridade": item.prioridade,
            "dataCriacao": data_criacao.isoformat(),
            "liberadoParaPreparo": item.liberadoParaPreparo,
            "tempoEsperaMinutos": tempo_espera,
            "pontuacao": pontuacao,
        }

    @classmethod
    def _event_data(
        cls,
        event_type: str,
        pedido: Pedido,
        item: ItemPedido,
    ) -> dict:
        return {
            "type": event_type,
            "restaurantId": pedido.idRestaurante,
            "assignedWaiterId": pedido.idGarcom,
            "item": cls._item_data(item),
        }