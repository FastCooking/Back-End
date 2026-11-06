import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.core.events import domain_event_bus
from src.core.realtime import realtime_hub
from src.models.Cardapio import Cardapio
from src.models.Entrega import Entrega
from src.models.Estoque import Estoque
from src.models.FichaTecnica import FichaTecnica
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Usuario import Usuario
from src.schemas.DeliverySchema import DeliveryState
from src.schemas.KdsNotificationSchema import OrderItemReadyEvent
from src.schemas.PedidoSchema import PedidoCreate, PedidoItemCreate
from src.services.PrioridadeKDS import calcular_pontuacao, eh_sobremesa
from src.services.RF08Service import RF08Service, RF08ValidationResult
from src.services.SessaoService import SessaoService

STATUS_ITEM = ("Pendente", "Em preparo", "Pronto", "Entregue")


class PedidoService:
    def __init__(self, db: Session):
        self.db = db

    def add_items_to_table(
        self,
        idMesa: uuid.UUID,
        itens: list[PedidoItemCreate],
        usuario: Usuario | None = None,
        sessao_id: str | None = None,
    ) -> dict:
        """
        Adição Universal e Concorrente (RF01):
        Permite que tanto clientes (autoatendimento) quanto garçons adicionem itens à mesa.
        Garante abertura automática da mesa e criação da comanda se for o primeiro item (RF01),
        ou append na comanda existente de forma atômica e serializada.
        """
        mesa = (
            self.db.query(Mesa)
            .filter(Mesa.idMesa == idMesa)
            .with_for_update()
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
        origem = "GARCOM" if usuario else "CLIENTE"

        try:
            cardapios = self._validate_menu_items(itens, idRestaurante)
            self._validate_stock_availability(itens, cardapios, idRestaurante)
            self._ensure_menu_items_active(cardapios)

            # 1. Garante sessão ativa no banco (reutiliza ou abre nova conforme RF01/RF02)
            sessao = SessaoService.abrir_mesa(self.db, mesa.idMesa)
            sessao_id_final = sessao_id or str(sessao.idSessao)

            # 2. Busca comanda ativa com lock pessimista
            pedido = (
                self.db.query(Pedido)
                .filter(
                    Pedido.idMesa == mesa.idMesa,
                    Pedido.status.notin_(["Fechado", "Cancelado"]),
                )
                .with_for_update()
                .first()
            )

            rf01_aplicado = False
            if pedido is None:
                # RF01: Primeiro item cria a comanda e abre a mesa
                rf01_aplicado = True
                pedido = Pedido.create(
                    db=self.db,
                    idRestaurante=idRestaurante,
                    idMesa=mesa.idMesa,
                    idGarcom=idGarcom,
                    sessao_id=sessao_id_final,
                    status="Aberto",
                    commit=False,
                )
                mesa.status = "Indisponivel"
            elif idGarcom and pedido.idGarcom is None:
                pedido.idGarcom = idGarcom

            # 3. Adiciona os itens à comanda unificada
            novos_itens = [
                ItemPedido.create(
                    db=self.db,
                    idPedido=pedido.idPedido,
                    idCardapio=cardapio.idCardapio,
                    quantidade=item.quantidade,
                    precoUnitario=float(cardapio.preco),
                    observacao=item.observacao,
                    categoria=cardapio.categoria,
                    liberadoParaPreparo=not eh_sobremesa(cardapio.categoria),
                    origem=origem,
                    commit=False,
                )
                for item, cardapio in zip(itens, cardapios, strict=True)
            ]

            # 4. Reavalia RF08 imediatamente
            rf08_res = RF08Service.reavaliar_comanda(self.db, pedido)

            self.db.commit()
            self.db.refresh(pedido)
            self.db.refresh(mesa)

            for item in novos_itens:
                self.db.refresh(item)

        except Exception:
            self.db.rollback()
            raise

        events = [
            self._event_data("item.created", pedido, item)
            for item in novos_itens
        ]

        serialized_itens = [self._item_data(item) for item in novos_itens]

        return {
            "rf01Aplicado": rf01_aplicado,
            "origemAdicao": origem,
            "mesa": {
                "idMesa": str(mesa.idMesa),
                "numero": mesa.numero,
                "status": mesa.status,
            },
            "comanda": self._pedido_data(pedido, rf08_res),
            "itens": serialized_itens,
            "itensAdicionados": serialized_itens,
            "events": events,
        }

    def create(self, dados: PedidoCreate, usuario: Usuario | None = None) -> dict:
        """Compatibilidade com POST /pedidos original delegando para add_items_to_table."""
        result = self.add_items_to_table(
            idMesa=dados.idMesa,
            itens=dados.itens,
            usuario=usuario,
            sessao_id=dados.sessao_id,
        )
        return {
            "pedido": result["comanda"],
            "itens": result["itens"],
            "events": result["events"],
            "rf01Aplicado": result["rf01Aplicado"],
        }

    def add_items(
        self,
        idPedido: uuid.UUID,
        itens: list[PedidoItemCreate],
        usuario: Usuario | None = None,
    ) -> dict:
        pedido = self._get_assigned_order(idPedido, usuario)
        idRestaurante = usuario.idRestaurante if usuario else pedido.idRestaurante
        origem = "GARCOM" if usuario else "CLIENTE"

        try:
            cardapios = self._validate_menu_items(itens, idRestaurante)
            self._validate_stock_availability(itens, cardapios, idRestaurante)
            self._ensure_menu_items_active(cardapios)

            novos_itens = [
                ItemPedido.create(
                    db=self.db,
                    idPedido=pedido.idPedido,
                    idCardapio=cardapio.idCardapio,
                    quantidade=item.quantidade,
                    precoUnitario=float(cardapio.preco),
                    observacao=item.observacao,
                    categoria=cardapio.categoria,
                    liberadoParaPreparo=not eh_sobremesa(cardapio.categoria),
                    origem=origem,
                    commit=False,
                )
                for item, cardapio in zip(itens, cardapios, strict=True)
            ]

            # Reavalia regra de negócio RF08
            rf08_res = RF08Service.reavaliar_comanda(self.db, pedido)

            self.db.commit()
            self.db.refresh(pedido)

            for item in novos_itens:
                self.db.refresh(item)

        except Exception:
            self.db.rollback()
            raise

        return {
            "itens": [self._item_data(item) for item in novos_itens],
            "comanda": self._pedido_data(pedido, rf08_res),
            "events": [
                self._event_data("item.created", pedido, item)
                for item in novos_itens
            ],
        }

    def remover_item_comanda(
        self,
        idPedido: uuid.UUID,
        idItemPedido: uuid.UUID,
        usuario: Usuario,
        motivo: str | None = None,
    ) -> dict:
        """
        Remoção em Tempo Real:
        Permite ao garçom remover um item de uma comanda em aberto.
        Atualiza o banco e notifica o KDS e a equipe via WebSocket.
        Reavalia RF08 garantindo consistência de Zero Pendências.
        """
        pedido = (
            self.db.query(Pedido)
            .filter(
                Pedido.idPedido == idPedido,
                Pedido.idRestaurante == usuario.idRestaurante,
            )
            .with_for_update()
            .first()
        )
        if pedido is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido não encontrado neste restaurante.",
            )

        if pedido.status in ("Fechado", "Cancelado"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Não é possível remover item de um pedido encerrado ou cancelado.",
            )

        item = (
            self.db.query(ItemPedido)
            .filter(
                ItemPedido.idItemPedido == idItemPedido,
                ItemPedido.idPedido == idPedido,
            )
            .with_for_update()
            .first()
        )
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item do pedido não encontrado.",
            )

        if item.status == "Cancelado":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O item já está cancelado.",
            )

        if item.status == "Entregue":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Não é possível remover item que já foi entregue.",
            )

        try:
            status_anterior = item.status
            item.update_stats(self.db, "Cancelado", commit=False)
            if motivo:
                item.observacao = f"{item.observacao or ''} [Cancelado: {motivo}]".strip()

            rf08_res = RF08Service.reavaliar_comanda(self.db, pedido)

            self.db.commit()
            self.db.refresh(item)
            self.db.refresh(pedido)
        except Exception:
            self.db.rollback()
            raise

        event = self._event_data("item.removed", pedido, item)

        return {
            "item": self._item_data(item),
            "comanda": self._pedido_data(pedido, rf08_res),
            "statusAnterior": status_anterior,
            "statusAtual": item.status,
            "removidoPor": str(usuario.idUsuario),
            "events": [event],
        }

    def assumir_entrega(
        self,
        idPedido: uuid.UUID,
        usuario: Usuario,
    ) -> dict:
        """
        API de Assumir Entrega (RF08):
        Exige estritamente Zero Pendências na comanda antes de permitir ao garçom assumir.
        """
        pedido = (
            self.db.query(Pedido)
            .filter(
                Pedido.idPedido == idPedido,
                Pedido.idRestaurante == usuario.idRestaurante,
            )
            .with_for_update()
            .first()
        )
        if pedido is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido não encontrado neste restaurante.",
            )

        if pedido.status in ("Fechado", "Cancelado"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Não é possível assumir entrega de pedido encerrado ou cancelado.",
            )

        # Validação RF08 (Zero Pendências)
        rf08_res = RF08Service.exigir_zero_pendencias(self.db, pedido)

        try:
            pedido.idGarcom = usuario.idUsuario
            pedido.status = "EmEntrega"
            self.db.commit()
            self.db.refresh(pedido)
        except Exception:
            self.db.rollback()
            raise

        event = {
            "type": "order.delivery_assumed",
            "restaurantId": pedido.idRestaurante,
            "assignedWaiterId": pedido.idGarcom,
            "item": {
                "idPedido": str(pedido.idPedido),
                "status": pedido.status,
                "assumidoPor": str(usuario.idUsuario),
            },
        }

        return {
            "comanda": self._pedido_data(pedido, rf08_res),
            "assumidoPor": str(usuario.idUsuario),
            "events": [event],
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
        rf08_res = RF08Service.reavaliar_comanda(self.db, pedido)
        total = sum(
            float(it.precoUnitario) * it.quantidade
            for it in itens
            if it.status != "Cancelado"
        )
        pagamentos = [
            {
                "idPagamento": str(p.idPagamento),
                "formaPagamento": p.formaPagamento,
                "valor": float(p.valor),
                "dataPagamento": p.dataPagamento.isoformat() if p.dataPagamento else None,
            }
            for p in (pedido.pagamentos or [])
        ]
        total_pago = sum(p["valor"] for p in pagamentos)
        saldo_restante = max(0.0, round(total - total_pago, 2))
        return {
            "pedido": self._pedido_data(pedido, rf08_res),
            "itens": [self._item_data(item) for item in itens],
            "total": round(total, 2),
            "pagamentos": pagamentos,
            "totalPago": round(total_pago, 2),
            "saldoRestante": saldo_restante,
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
                "idMesa": str(pedido.idMesa) if getattr(pedido, "idMesa", None) else None,
                "idRestaurante": str(pedido.idRestaurante) if getattr(pedido, "idRestaurante", None) else None,
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
            if novo_status == "Em preparo":
                self._debit_stock_for_item(item, pedido)

            item.update_stats(self.db, novo_status, commit=False)
            # Reavalia RF08 sempre que status avança no KDS
            RF08Service.reavaliar_comanda(self.db, pedido)

            if novo_status == "Pronto":
                item.deliveryStatus = DeliveryState.WAITING_DELIVERY_PICKUP.value
                existing_entrega = (
                    self.db.query(Entrega)
                    .filter(Entrega.idItemPedido == item.idItemPedido)
                    .first()
                )
                if existing_entrega is None:
                    self.db.add(
                        Entrega(
                            idRestaurante=pedido.idRestaurante,
                            idPedido=pedido.idPedido,
                            idItemPedido=item.idItemPedido,
                            status=DeliveryState.WAITING_DELIVERY_PICKUP.value,
                            dataCriacao=item.dataCriacao or datetime.now(UTC),
                        )
                    )
            elif novo_status == "Entregue":
                now_utc = datetime.now(UTC)
                item.deliveryStatus = DeliveryState.DELIVERED.value
                item.deliveredAt = now_utc
                if usuario and getattr(usuario, "idUsuario", None):
                    item.claimedByWaiterId = usuario.idUsuario
                existing_entrega = (
                    self.db.query(Entrega)
                    .filter(Entrega.idItemPedido == item.idItemPedido)
                    .first()
                )
                if existing_entrega is not None:
                    existing_entrega.status = DeliveryState.DELIVERED.value
                    existing_entrega.deliveredAt = now_utc

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

    def update_item_quantity(
        self,
        idItemPedido: uuid.UUID,
        nova_quantidade: int,
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

        if pedido is None or (usuario.funcao != "Adm" and pedido.idRestaurante != usuario.idRestaurante):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item do pedido não encontrado.",
            )

        if pedido.status in ("Fechado", "Cancelado"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Não é possível alterar item de um pedido encerrado ou cancelado.",
            )

        if item.status != "Pendente":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Não é possível alterar a quantidade do item pois o preparo já foi iniciado (status atual: '{item.status}').",
            )

        try:
            if nova_quantidade <= 0:
                item.update_stats(self.db, "Cancelado", commit=False)
                RF08Service.reavaliar_comanda(self.db, pedido)
            else:
                item.quantidade = nova_quantidade

            self.db.commit()
            self.db.refresh(item)
            self.db.refresh(pedido)
        except Exception:
            self.db.rollback()
            raise

        return {
            "item": self._item_data(item),
            "event": self._event_data(
                "item.quantity_changed" if nova_quantidade > 0 else "item.status_changed",
                pedido,
                item,
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
            RF08Service.reavaliar_comanda(self.db, pedido)
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
            RF08Service.reavaliar_comanda(self.db, pedido)
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
            domain_event = event.get("domainEvent")
            if domain_event is not None:
                await domain_event_bus.publish(domain_event)

            if "item" in event and "restaurantId" in event:
                await realtime_hub.publish_item_event(
                    event_type=event["type"],
                    restaurant_id=event["restaurantId"],
                    item_data=event["item"],
                    assigned_waiter_id=event.get("assignedWaiterId"),
                )

    def _get_assigned_order(
        self,
        idPedido: uuid.UUID,
        usuario: Usuario | None = None,
    ) -> Pedido:
        query = self.db.query(Pedido).filter(Pedido.idPedido == idPedido)
        if usuario is not None and getattr(usuario, "idRestaurante", None):
            query = query.filter(Pedido.idRestaurante == usuario.idRestaurante)

        pedido = query.with_for_update().first()

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

    def _validate_stock_availability(
        self,
        itens: list[PedidoItemCreate],
        cardapios: list[Cardapio],
        idRestaurante: uuid.UUID,
    ) -> None:
        cardapio_ids = {cardapio.idCardapio for cardapio in cardapios}
        fichas = (
            self.db.query(FichaTecnica)
            .filter(FichaTecnica.idCardapio.in_(cardapio_ids))
            .order_by(FichaTecnica.idEstoque)
            .all()
        )
        if not fichas:
            return

        fichas_por_cardapio: dict[uuid.UUID, list[FichaTecnica]] = {}
        for ficha in fichas:
            fichas_por_cardapio.setdefault(ficha.idCardapio, []).append(ficha)

        necessidades: dict[uuid.UUID, Decimal] = {}
        cardapios_por_insumo: dict[uuid.UUID, set[uuid.UUID]] = {}
        for item, cardapio in zip(itens, cardapios, strict=True):
            for ficha in fichas_por_cardapio.get(cardapio.idCardapio, []):
                necessidade = Decimal(str(ficha.quantidadeNecessaria)) * item.quantidade
                necessidades[ficha.idEstoque] = (
                    necessidades.get(ficha.idEstoque, Decimal(0)) + necessidade
                )
                cardapios_por_insumo.setdefault(ficha.idEstoque, set()).add(
                    cardapio.idCardapio
                )

        estoques_por_id = self._lock_stock_rows(idRestaurante, necessidades)
        insumos_indisponiveis = self._missing_stock(
            necessidades, estoques_por_id
        )
        if not insumos_indisponiveis:
            return

        cardapio_indisponivel = next(
            (
                cardapio
                for cardapio in cardapios
                if any(
                    cardapio.idCardapio in cardapios_por_insumo[idEstoque]
                    for idEstoque in insumos_indisponiveis
                )
            ),
            cardapios[0],
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Item do cardápio '{cardapio_indisponivel.nome}' indisponível "
                "por falta de estoque."
            ),
        )

    def _lock_stock_rows(
        self,
        idRestaurante: uuid.UUID,
        necessidades: dict[uuid.UUID, Decimal],
    ) -> dict[uuid.UUID, Estoque]:
        estoques = (
            self.db.query(Estoque)
            .filter(
                Estoque.idRestaurante == idRestaurante,
                Estoque.idEstoque.in_(necessidades),
            )
            .order_by(Estoque.idEstoque)
            .with_for_update()
            .populate_existing()
            .all()
        )
        return {estoque.idEstoque: estoque for estoque in estoques}

    @staticmethod
    def _missing_stock(
        necessidades: dict[uuid.UUID, Decimal],
        estoques_por_id: dict[uuid.UUID, Estoque],
    ) -> set[uuid.UUID]:
        return {
            idEstoque
            for idEstoque, quantidade_necessaria in necessidades.items()
            if idEstoque not in estoques_por_id
            or Decimal(str(estoques_por_id[idEstoque].quantidadeEstoque))
            < quantidade_necessaria
        }

    @staticmethod
    def _ensure_menu_items_active(cardapios: list[Cardapio]) -> None:
        if any(not cardapio.status for cardapio in cardapios):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item do cardápio não encontrado neste restaurante.",
            )

    def _debit_stock_for_item(self, item: ItemPedido, pedido: Pedido) -> None:
        fichas = (
            self.db.query(FichaTecnica)
            .filter(FichaTecnica.idCardapio == item.idCardapio)
            .order_by(FichaTecnica.idEstoque)
            .all()
        )
        if not fichas:
            return

        quantidades_necessarias = {
            ficha.idEstoque: Decimal(str(ficha.quantidadeNecessaria)) * item.quantidade
            for ficha in fichas
        }
        estoques_por_id = self._lock_stock_rows(
            pedido.idRestaurante, quantidades_necessarias
        )
        if self._missing_stock(quantidades_necessarias, estoques_por_id):
            cardapio = self.db.query(Cardapio).filter(
                Cardapio.idCardapio == item.idCardapio
            ).first()
            nome_cardapio = cardapio.nome if cardapio else "Item do cardápio"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Item do cardápio '{nome_cardapio}' indisponível por falta de estoque.",
            )

        cardapio = self.db.query(Cardapio).filter(
            Cardapio.idCardapio == item.idCardapio
        ).first()
        for ficha in fichas:
            estoque = estoques_por_id[ficha.idEstoque]
            estoque.quantidadeEstoque = (
                Decimal(str(estoque.quantidadeEstoque))
                - quantidades_necessarias[ficha.idEstoque]
            )
            if cardapio is not None and (
                Decimal(str(estoque.quantidadeEstoque))
                < Decimal(str(ficha.quantidadeNecessaria))
            ):
                cardapio.status = False

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
    def _pedido_data(pedido: Pedido, resultado_rf08: RF08ValidationResult | None = None) -> dict:
        data = {
            "idPedido": pedido.idPedido,
            "sessao_id": pedido.sessao_id,
            "idRestaurante": pedido.idRestaurante,
            "idMesa": pedido.idMesa,
            "idGarcom": pedido.idGarcom,
            "status": pedido.status,
        }
        if resultado_rf08 is not None:
            data.update({
                "possuiPendencias": resultado_rf08.possui_pendencias,
                "elegivelAssumirEntrega": resultado_rf08.elegivel_assumir_entrega,
                "itensPendentesCount": resultado_rf08.itens_pendentes_count,
            })
        return data

    @staticmethod
    def _item_data(item: ItemPedido) -> dict:
        data_criacao = item.dataCriacao
        tempo_preparo_item = item.cardapio.tempoPreparo if (item.cardapio and getattr(item.cardapio, "tempoPreparo", None)) else None

        tempo_espera, pontuacao = calcular_pontuacao(
            item.categoria,
            data_criacao,
            tempo_preparo=tempo_preparo_item,
        )

        nome_item = item.cardapio.nome if item.cardapio else None
        numero_mesa = (
            item.pedido.mesa.numero
            if (item.pedido and item.pedido.mesa)
            else None
        )
        origem = getattr(item, "origem", "CLIENTE")

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
            "origem": origem,
            "tempoEsperaMinutos": tempo_espera,
            "pontuacao": pontuacao,
            "tempoPreparo": tempo_preparo_item or 15,
            "claimedByWaiterId": str(item.claimedByWaiterId) if item.claimedByWaiterId else None,
            "deliveredAt": item.deliveredAt.isoformat() if item.deliveredAt else None,
        }

    @classmethod
    def _event_data(
        cls,
        event_type: str,
        pedido: Pedido,
        item: ItemPedido,
    ) -> dict:
        item_payload = cls._item_data(item)
        domain_event: OrderItemReadyEvent | None = None

        if event_type == "item.status_changed" and item.status == "Pronto":
            table_num = (
                item_payload.get("numeroMesa")
                if item_payload.get("numeroMesa") is not None
                else (pedido.mesa.numero if pedido.mesa else str(pedido.idMesa))
            )
            domain_event = OrderItemReadyEvent(
                restaurant_id=pedido.idRestaurante,
                order_id=pedido.idPedido,
                table_number=table_num,
                item_id=item.idItemPedido,
                item_name=item_payload.get("nomeItem") or "Item do Cardápio",
                quantity=item.quantidade,
                notes=item.observacao or "",
                assigned_waiter_id=pedido.idGarcom,
            )

        return {
            "type": event_type,
            "restaurantId": pedido.idRestaurante,
            "assignedWaiterId": pedido.idGarcom,
            "item": item_payload,
            "domainEvent": domain_event,
        }
