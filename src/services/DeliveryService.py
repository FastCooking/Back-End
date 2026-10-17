import threading
import uuid
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from src.core.events import domain_event_bus
from src.core.realtime import realtime_hub
from src.models.Entrega import Entrega
from src.models.ItemPedido import ItemPedido
from src.models.Pedido import Pedido
from src.models.Usuario import Usuario
from src.schemas.DeliverySchema import (
    ACTIVE_DELIVERY_STATES,
    DeliveryClaimedEvent,
    DeliveryClaimedResponseSchema,
    DeliveryCompletedResponseSchema,
    DeliveryState,
    QueuedDeliveryItemSchema,
)
from src.schemas.KdsNotificationSchema import OrderItemReadyEvent
from src.services.PedidoService import PedidoService


class DeliveryDomainError(HTTPException):
    """
    Exceção de domínio enriquecida com código semântico padronizado
    para respostas HTTP 404, 409 e 422.
    """

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(
            status_code=status_code,
            detail=f"{code}: {message}",
        )


class _KeyedLockRegistry:
    """
    Coordenador de locks determinísticos em memória por chave (item_id / waiter_id).
    Atua em conjunto com o bloqueio pessimista do banco (`SELECT ... FOR UPDATE`)
    e updates atômicos condicionais, garantindo serialização segura inclusive em
    ambientes de teste concorrentes (SQLite StaticPool / multi-thread) sem gerar HTTP 500.
    """

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    @contextmanager
    def acquire_ordered(self, *keys: str):
        sorted_unique_keys = sorted({str(k) for k in keys if k})
        acquired: list[threading.RLock] = []
        with self._guard:
            locks_to_acquire = [
                self._locks.setdefault(k, threading.RLock()) for k in sorted_unique_keys
            ]
        try:
            for lock in locks_to_acquire:
                lock.acquire()
                acquired.append(lock)
            yield
        finally:
            for lock in reversed(acquired):
                lock.release()


_concurrency_locks = _KeyedLockRegistry()


class DeliveryService:
    """
    Serviço transacional responsável pelo ciclo de vida de entregas do salão:
    - Assumir entrega de item pronto (`claim_delivery`) com bloqueio pessimista e regra 1-para-1.
    - Concluir entrega (`complete_delivery`) e despachar reativamente a fila FIFO (`WAITING_DELIVERY_PICKUP`).
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def claim_delivery(
        self,
        item_id: uuid.UUID,
        waiter: Usuario,
    ) -> dict:
        """
        Atribui atomicamente um item pronto a um garçom livre.
        - Previne race conditions via lock pessimista (`SELECT FOR UPDATE`) + update condicional atômico.
        - Garante no máximo 1 entrega ativa (`IN_DELIVERY` / `IN_PROGRESS` / `PENDING_DELIVERY`) por garçom.
        """
        lock_keys = (
            f"restaurant:{waiter.idRestaurante}",
            f"item:{item_id}",
            f"waiter:{waiter.idUsuario}",
        )

        with _concurrency_locks.acquire_ordered(*lock_keys):
            self.db.expire_all()

            try:
                # 1. Bloqueio pessimista (SELECT ... FOR UPDATE) no ItemPedido alvo
                item = (
                    self.db.query(ItemPedido)
                    .filter(ItemPedido.idItemPedido == item_id)
                    .with_for_update()
                    .first()
                )

                if item is None:
                    self.db.rollback()
                    raise DeliveryDomainError(
                        status_code=status.HTTP_404_NOT_FOUND,
                        code="ITEM_NOT_FOUND",
                        message="Item não existe ou não está com status 'pronto'.",
                    )

                pedido = Pedido.get_by_id(self.db, item.idPedido)
                if pedido is None or pedido.idRestaurante != waiter.idRestaurante:
                    self.db.rollback()
                    raise DeliveryDomainError(
                        status_code=status.HTTP_404_NOT_FOUND,
                        code="ITEM_NOT_FOUND",
                        message="Item não existe neste restaurante.",
                    )

                entrega = (
                    self.db.query(Entrega)
                    .filter(Entrega.idItemPedido == item.idItemPedido)
                    .with_for_update()
                    .first()
                )

                already_claimed = (
                    item.claimedByWaiterId is not None
                    or item.deliveryStatus
                    in (
                        *ACTIVE_DELIVERY_STATES,
                        DeliveryState.DELIVERED.value,
                    )
                    or item.status == "Entregue"
                    or (
                        entrega is not None
                        and (
                            entrega.idGarcom is not None
                            or entrega.status
                            in (
                                *ACTIVE_DELIVERY_STATES,
                                DeliveryState.DELIVERED.value,
                            )
                        )
                    )
                )

                # 2. Se o item ainda não está pronto e nunca foi assumido -> 404 Not Found
                if item.status != "Pronto" and not already_claimed:
                    self.db.rollback()
                    raise DeliveryDomainError(
                        status_code=status.HTTP_404_NOT_FOUND,
                        code="ITEM_NOT_READY",
                        message=f"Item não está com status 'Pronto' (status atual: '{item.status}').",
                    )

                # 3. Validação de disponibilidade do garçom (Regra 1-para-1 na mesma transação)
                if self._waiter_has_active_delivery(
                    waiter_id=waiter.idUsuario,
                    restaurant_id=waiter.idRestaurante,
                ):
                    self.db.rollback()
                    raise DeliveryDomainError(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        code="WAITER_ALREADY_HAS_ACTIVE_DELIVERY",
                        message="O garçom já possui uma entrega ativa em andamento.",
                    )

                # 4. Se o item já foi assumido por outro garçom (ou já entregue) -> 409 Conflict
                if already_claimed:
                    self.db.rollback()
                    raise DeliveryDomainError(
                        status_code=status.HTTP_409_CONFLICT,
                        code="ITEM_ALREADY_CLAIMED",
                        message="Este item já foi assumido por outro garçom.",
                    )

                now_utc = datetime.now(UTC)

                # 5. Atualização condicional atômica no ItemPedido (CAS / Compare-And-Swap SQL)
                updated_rows = (
                    self.db.query(ItemPedido)
                    .filter(
                        ItemPedido.idItemPedido == item.idItemPedido,
                        ItemPedido.status == "Pronto",
                        ItemPedido.claimedByWaiterId.is_(None),
                        or_(
                            ItemPedido.deliveryStatus.is_(None),
                            ItemPedido.deliveryStatus.in_(
                                [
                                    DeliveryState.READY.value,
                                    DeliveryState.WAITING_DELIVERY_PICKUP.value,
                                ]
                            ),
                        ),
                    )
                    .update(
                        {
                            ItemPedido.deliveryStatus: DeliveryState.IN_DELIVERY.value,
                            ItemPedido.claimedByWaiterId: waiter.idUsuario,
                            ItemPedido.claimedAt: now_utc,
                        },
                        synchronize_session=False,
                    )
                )

                if updated_rows == 0:
                    self.db.rollback()
                    raise DeliveryDomainError(
                        status_code=status.HTTP_409_CONFLICT,
                        code="ITEM_ALREADY_CLAIMED",
                        message="Este item já foi assumido por outro garçom.",
                    )

                if entrega is None:
                    entrega = Entrega(
                        idRestaurante=pedido.idRestaurante,
                        idPedido=pedido.idPedido,
                        idItemPedido=item.idItemPedido,
                        idGarcom=waiter.idUsuario,
                        status=DeliveryState.IN_DELIVERY.value,
                        dataCriacao=item.dataCriacao or now_utc,
                        claimedAt=now_utc,
                    )
                    self.db.add(entrega)
                else:
                    entrega.idGarcom = waiter.idUsuario
                    entrega.status = DeliveryState.IN_DELIVERY.value
                    entrega.claimedAt = now_utc

                self.db.commit()
                self.db.refresh(item)
                self.db.refresh(entrega)
                self.db.refresh(pedido)

            except DeliveryDomainError:
                raise
            except IntegrityError as exc:
                self.db.rollback()
                raise DeliveryDomainError(
                    status_code=status.HTTP_409_CONFLICT,
                    code="ITEM_ALREADY_CLAIMED",
                    message="Conflito de concorrência: este item já foi assumido por outro garçom.",
                ) from exc
            except OperationalError as exc:
                self.db.rollback()
                raise DeliveryDomainError(
                    status_code=status.HTTP_409_CONFLICT,
                    code="ITEM_ALREADY_CLAIMED",
                    message="Conflito transacional concorrente ao assumir o item.",
                ) from exc
            except Exception:
                self.db.rollback()
                raise

            table_number = (
                pedido.mesa.numero if pedido.mesa is not None else str(pedido.idMesa)
            )
            item_name = (
                item.cardapio.nome if item.cardapio is not None else "Item do Cardápio"
            )
            claimed_iso = (
                entrega.claimedAt.isoformat()
                if entrega.claimedAt is not None
                else now_utc.isoformat()
            )

            claimed_domain_event = DeliveryClaimedEvent(
                restaurant_id=pedido.idRestaurante,
                order_id=pedido.idPedido,
                delivery_id=entrega.idEntrega,
                item_id=item.idItemPedido,
                table_number=table_number,
                claimed_by_waiter_id=waiter.idUsuario,
                timestamp=claimed_iso,
            )

            response_schema = DeliveryClaimedResponseSchema(
                deliveryId=str(entrega.idEntrega),
                itemId=str(item.idItemPedido),
                orderId=str(pedido.idPedido),
                restaurantId=str(pedido.idRestaurante),
                tableNumber=table_number,
                itemName=item_name,
                quantity=item.quantidade,
                status=DeliveryState.IN_DELIVERY.value,
                itemStatus=item.status,
                claimedByWaiterId=str(waiter.idUsuario),
                claimedAt=claimed_iso,
            )

            return {
                "delivery": response_schema.model_dump(mode="json"),
                "events": [
                    {
                        "type": "delivery:claimed",
                        "restaurantId": pedido.idRestaurante,
                        "assignedWaiterId": waiter.idUsuario,
                        "item": PedidoService._item_data(item),
                        "domainEvent": claimed_domain_event,
                    }
                ],
            }

    def complete_delivery(
        self,
        delivery_or_item_id: uuid.UUID,
        waiter: Usuario,
    ) -> dict:
        """
        Finaliza a entrega ativa (`DELIVERED` / `Entregue`), libera o garçom (0 entregas ativas)
        e verifica atomicamente a fila FIFO (`WAITING_DELIVERY_PICKUP`) para despachar o próximo item.
        Aceita tanto `idEntrega` quanto `idItemPedido` como identificador.
        """
        lock_keys = (
            f"restaurant:{waiter.idRestaurante}",
            f"waiter:{waiter.idUsuario}",
        )

        with _concurrency_locks.acquire_ordered(*lock_keys):
            self.db.expire_all()

            try:
                entrega = (
                    self.db.query(Entrega)
                    .filter(
                        or_(
                            Entrega.idEntrega == delivery_or_item_id,
                            Entrega.idItemPedido == delivery_or_item_id,
                        )
                    )
                    .with_for_update()
                    .first()
                )

                if entrega is not None:
                    item = (
                        self.db.query(ItemPedido)
                        .filter(ItemPedido.idItemPedido == entrega.idItemPedido)
                        .with_for_update()
                        .first()
                    )
                else:
                    item = (
                        self.db.query(ItemPedido)
                        .filter(ItemPedido.idItemPedido == delivery_or_item_id)
                        .with_for_update()
                        .first()
                    )

                if item is None:
                    self.db.rollback()
                    raise DeliveryDomainError(
                        status_code=status.HTTP_404_NOT_FOUND,
                        code="DELIVERY_NOT_FOUND",
                        message="Entrega ou item não encontrado.",
                    )

                pedido = Pedido.get_by_id(self.db, item.idPedido)
                if pedido is None or pedido.idRestaurante != waiter.idRestaurante:
                    self.db.rollback()
                    raise DeliveryDomainError(
                        status_code=status.HTTP_404_NOT_FOUND,
                        code="DELIVERY_NOT_FOUND",
                        message="Entrega não encontrada neste restaurante.",
                    )

                if (
                    item.status == "Entregue"
                    or item.deliveryStatus == DeliveryState.DELIVERED.value
                    or (
                        entrega is not None
                        and entrega.status == DeliveryState.DELIVERED.value
                    )
                ):
                    self.db.rollback()
                    raise DeliveryDomainError(
                        status_code=status.HTTP_409_CONFLICT,
                        code="DELIVERY_ALREADY_COMPLETED",
                        message="Esta entrega já foi finalizada anteriormente.",
                    )

                assigned_waiter_id = (
                    entrega.idGarcom
                    if (entrega is not None and entrega.idGarcom is not None)
                    else item.claimedByWaiterId
                )

                is_active_delivery = assigned_waiter_id is not None and (
                    item.deliveryStatus in ACTIVE_DELIVERY_STATES
                    or (
                        entrega is not None and entrega.status in ACTIVE_DELIVERY_STATES
                    )
                )

                if not is_active_delivery:
                    self.db.rollback()
                    raise DeliveryDomainError(
                        status_code=status.HTTP_409_CONFLICT,
                        code="DELIVERY_NOT_IN_PROGRESS",
                        message="O item informado não possui uma entrega ativa em andamento.",
                    )

                if waiter.funcao == "Garcom" and assigned_waiter_id != waiter.idUsuario:
                    self.db.rollback()
                    raise DeliveryDomainError(
                        status_code=status.HTTP_409_CONFLICT,
                        code="DELIVERY_ASSIGNED_TO_ANOTHER_WAITER",
                        message="Apenas o garçom responsável pela entrega pode concluí-la.",
                    )

                now_utc = datetime.now(UTC)
                item.status = "Entregue"
                item.deliveryStatus = DeliveryState.DELIVERED.value
                item.deliveredAt = now_utc

                if entrega is None:
                    entrega = Entrega(
                        idRestaurante=pedido.idRestaurante,
                        idPedido=pedido.idPedido,
                        idItemPedido=item.idItemPedido,
                        idGarcom=assigned_waiter_id,
                        status=DeliveryState.DELIVERED.value,
                        dataCriacao=item.dataCriacao or now_utc,
                        claimedAt=item.claimedAt or now_utc,
                        deliveredAt=now_utc,
                    )
                    self.db.add(entrega)
                else:
                    entrega.status = DeliveryState.DELIVERED.value
                    entrega.deliveredAt = now_utc

                self.db.flush()

                # 2. Verifica atomicamente na mesma transação o próximo item FIFO na fila de prontos
                next_queued = self._peek_next_fifo_ready_item(
                    restaurant_id=pedido.idRestaurante,
                    exclude_item_id=item.idItemPedido,
                )

                self.db.commit()
                self.db.refresh(item)
                self.db.refresh(entrega)
                self.db.refresh(pedido)

            except DeliveryDomainError:
                raise
            except Exception:
                self.db.rollback()
                raise

            table_number = (
                pedido.mesa.numero if pedido.mesa is not None else str(pedido.idMesa)
            )
            delivered_iso = (
                entrega.deliveredAt.isoformat()
                if entrega.deliveredAt is not None
                else now_utc.isoformat()
            )

            events: list[dict] = [
                {
                    "type": "item.status_changed",
                    "restaurantId": pedido.idRestaurante,
                    "assignedWaiterId": assigned_waiter_id,
                    "item": PedidoService._item_data(item),
                    "domainEvent": None,
                }
            ]

            next_queued_schema: QueuedDeliveryItemSchema | None = None
            if next_queued is not None:
                next_item, next_pedido, next_entrega = next_queued
                next_table_number = (
                    next_pedido.mesa.numero
                    if next_pedido.mesa is not None
                    else str(next_pedido.idMesa)
                )
                next_item_name = (
                    next_item.cardapio.nome
                    if next_item.cardapio is not None
                    else "Item do Cardápio"
                )
                next_created_iso = (
                    next_item.dataCriacao.isoformat()
                    if next_item.dataCriacao is not None
                    else datetime.now(UTC).isoformat()
                )

                next_queued_schema = QueuedDeliveryItemSchema(
                    deliveryId=str(next_entrega.idEntrega),
                    itemId=str(next_item.idItemPedido),
                    orderId=str(next_pedido.idPedido),
                    restaurantId=str(next_pedido.idRestaurante),
                    tableNumber=next_table_number,
                    itemName=next_item_name,
                    quantity=next_item.quantidade,
                    notes=next_item.observacao or "",
                    status=DeliveryState.WAITING_DELIVERY_PICKUP.value,
                    createdAt=next_created_iso,
                )

                # Re-dispara o evento de oferta de item pronto (kds:item_ready) para a sala de garçons
                ready_offer_event = OrderItemReadyEvent(
                    restaurant_id=next_pedido.idRestaurante,
                    order_id=next_pedido.idPedido,
                    table_number=next_table_number,
                    item_id=next_item.idItemPedido,
                    item_name=next_item_name,
                    quantity=next_item.quantidade,
                    notes=next_item.observacao or "",
                    assigned_waiter_id=waiter.idUsuario,
                )
                events.append(
                    {
                        "type": "delivery:queue_dispatched",
                        "restaurantId": next_pedido.idRestaurante,
                        "assignedWaiterId": waiter.idUsuario,
                        "item": PedidoService._item_data(next_item),
                        "domainEvent": ready_offer_event,
                    }
                )

            response_schema = DeliveryCompletedResponseSchema(
                deliveryId=str(entrega.idEntrega),
                itemId=str(item.idItemPedido),
                orderId=str(pedido.idPedido),
                restaurantId=str(pedido.idRestaurante),
                tableNumber=table_number,
                status=DeliveryState.DELIVERED.value,
                itemStatus=item.status,
                completedByWaiterId=str(waiter.idUsuario),
                deliveredAt=delivered_iso,
                nextQueuedItem=next_queued_schema,
            )

            return {
                "delivery": response_schema.model_dump(mode="json"),
                "events": events,
            }

    def list_ready_queue(self, restaurant_id: uuid.UUID) -> list[dict]:
        """
        Retorna a fila de espera atual de itens prontos não assumidos (`WAITING_DELIVERY_PICKUP`)
        ordenada estritamente por data de criação (FIFO).
        """
        rows = (
            self.db.query(ItemPedido, Pedido)
            .join(Pedido, ItemPedido.idPedido == Pedido.idPedido)
            .filter(
                Pedido.idRestaurante == restaurant_id,
                Pedido.status.notin_(["Fechado", "Cancelado"]),
                ItemPedido.status == "Pronto",
                ItemPedido.claimedByWaiterId.is_(None),
                or_(
                    ItemPedido.deliveryStatus.is_(None),
                    ItemPedido.deliveryStatus.in_(
                        [
                            DeliveryState.READY.value,
                            DeliveryState.WAITING_DELIVERY_PICKUP.value,
                        ]
                    ),
                ),
            )
            .order_by(ItemPedido.dataCriacao.asc(), ItemPedido.idItemPedido.asc())
            .all()
        )

        result: list[dict] = []
        for item, pedido in rows:
            entrega = self._ensure_waiting_entrega(item, pedido)
            table_number = (
                pedido.mesa.numero if pedido.mesa is not None else str(pedido.idMesa)
            )
            item_name = (
                item.cardapio.nome if item.cardapio is not None else "Item do Cardápio"
            )
            created_iso = (
                item.dataCriacao.isoformat()
                if item.dataCriacao is not None
                else datetime.now(UTC).isoformat()
            )
            schema = QueuedDeliveryItemSchema(
                deliveryId=str(entrega.idEntrega),
                itemId=str(item.idItemPedido),
                orderId=str(pedido.idPedido),
                restaurantId=str(pedido.idRestaurante),
                tableNumber=table_number,
                itemName=item_name,
                quantity=item.quantidade,
                notes=item.observacao or "",
                status=DeliveryState.WAITING_DELIVERY_PICKUP.value,
                createdAt=created_iso,
            )
            result.append(schema.model_dump(mode="json"))

        self.db.commit()
        return result

    async def publish_events(self, events: Iterable[dict]) -> None:
        """
        Despacha os eventos de domínio e atualizações de fila de forma assíncrona
        (via BackgroundTasks), sem reter a resposta HTTP do garçom.
        """
        for event in events:
            domain_event = event.get("domainEvent")
            if domain_event is not None:
                await domain_event_bus.publish(domain_event)

            event_type = event.get("type")
            if event_type == "item.status_changed":
                await realtime_hub.publish_item_event(
                    event_type=event_type,
                    restaurant_id=event["restaurantId"],
                    item_data=event["item"],
                    assigned_waiter_id=event.get("assignedWaiterId"),
                )

    def _waiter_has_active_delivery(
        self,
        waiter_id: uuid.UUID,
        restaurant_id: uuid.UUID,
    ) -> bool:
        """
        Verifica se o garçom já possui alguma entrega com status ativo
        (`IN_DELIVERY`, `IN_PROGRESS` ou `PENDING_DELIVERY`) no restaurante.
        """
        active_in_entrega = (
            self.db.query(Entrega.idEntrega)
            .filter(
                Entrega.idRestaurante == restaurant_id,
                Entrega.idGarcom == waiter_id,
                Entrega.status.in_(list(ACTIVE_DELIVERY_STATES)),
            )
            .first()
        )
        if active_in_entrega is not None:
            return True

        active_in_item = (
            self.db.query(ItemPedido.idItemPedido)
            .join(Pedido, ItemPedido.idPedido == Pedido.idPedido)
            .filter(
                Pedido.idRestaurante == restaurant_id,
                ItemPedido.claimedByWaiterId == waiter_id,
                ItemPedido.status == "Pronto",
                ItemPedido.deliveryStatus.in_(list(ACTIVE_DELIVERY_STATES)),
            )
            .first()
        )
        return active_in_item is not None

    def _peek_next_fifo_ready_item(
        self,
        restaurant_id: uuid.UUID,
        exclude_item_id: uuid.UUID | None = None,
    ) -> tuple[ItemPedido, Pedido, Entrega] | None:
        """
        Busca o item mais antigo com status 'Pronto' e 'WAITING_DELIVERY_PICKUP' (FIFO)
        que ainda não tenha sido assumido por nenhum garçom.
        """
        query = (
            self.db.query(ItemPedido, Pedido)
            .join(Pedido, ItemPedido.idPedido == Pedido.idPedido)
            .filter(
                Pedido.idRestaurante == restaurant_id,
                Pedido.status.notin_(["Fechado", "Cancelado"]),
                ItemPedido.status == "Pronto",
                ItemPedido.claimedByWaiterId.is_(None),
                or_(
                    ItemPedido.deliveryStatus.is_(None),
                    ItemPedido.deliveryStatus.in_(
                        [
                            DeliveryState.READY.value,
                            DeliveryState.WAITING_DELIVERY_PICKUP.value,
                        ]
                    ),
                ),
            )
        )
        if exclude_item_id is not None:
            query = query.filter(ItemPedido.idItemPedido != exclude_item_id)

        row = query.order_by(
            ItemPedido.dataCriacao.asc(),
            ItemPedido.idItemPedido.asc(),
        ).first()

        if row is None:
            return None

        next_item, next_pedido = row
        entrega = self._ensure_waiting_entrega(next_item, next_pedido)
        return next_item, next_pedido, entrega

    def _ensure_waiting_entrega(
        self,
        item: ItemPedido,
        pedido: Pedido,
    ) -> Entrega:
        """
        Garante que um ItemPedido pronto possua registro na tabela Entrega com status
        WAITING_DELIVERY_PICKUP.
        """
        if item.deliveryStatus is None:
            item.deliveryStatus = DeliveryState.WAITING_DELIVERY_PICKUP.value

        entrega = (
            self.db.query(Entrega)
            .filter(Entrega.idItemPedido == item.idItemPedido)
            .first()
        )
        if entrega is None:
            entrega = Entrega(
                idRestaurante=pedido.idRestaurante,
                idPedido=pedido.idPedido,
                idItemPedido=item.idItemPedido,
                status=DeliveryState.WAITING_DELIVERY_PICKUP.value,
                dataCriacao=item.dataCriacao or datetime.now(UTC),
            )
            self.db.add(entrega)
            self.db.flush()
        return entrega
