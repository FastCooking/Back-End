import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from src.core.security import exigir_funcao
from src.database.connection import get_db
from src.models.Usuario import Usuario
from src.schemas.DeliverySchema import (
    ClaimDeliveryRequestSchema,
    DeliveryClaimedResponseSchema,
    DeliveryCompletedResponseSchema,
    QueuedDeliveryItemSchema,
)
from src.services.DeliveryService import DeliveryService

router = APIRouter(tags=["Entregas (Salão / KDS)"])


@router.post(
    "/api/deliveries/claim",
    response_model=DeliveryClaimedResponseSchema,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/pedidos/entregas/claim",
    response_model=DeliveryClaimedResponseSchema,
    status_code=status.HTTP_200_OK,
)
def claim_delivery_by_body(
    dados: ClaimDeliveryRequestSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Garcom")),
) -> dict:
    """
    Permite a um garçom livre assumir atomicamente a entrega de um item com status 'Pronto'.
    Dispara evento WebSocket 'delivery:claimed' em background para os demais garçons ativos.
    """
    service = DeliveryService(db)
    result = service.claim_delivery(item_id=dados.itemId, waiter=usuario)
    background_tasks.add_task(service.publish_events, result.pop("events"))
    return result["delivery"]


@router.post(
    "/api/items/{item_id}/claim",
    response_model=DeliveryClaimedResponseSchema,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/pedidos/itens/{item_id}/claim",
    response_model=DeliveryClaimedResponseSchema,
    status_code=status.HTTP_200_OK,
)
def claim_delivery_by_path(
    item_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Garcom")),
) -> dict:
    """
    Rota alternativa RESTful por path parameter para assumir a entrega de um item pronto.
    """
    service = DeliveryService(db)
    result = service.claim_delivery(item_id=item_id, waiter=usuario)
    background_tasks.add_task(service.publish_events, result.pop("events"))
    return result["delivery"]


@router.post(
    "/api/deliveries/{delivery_id}/complete",
    response_model=DeliveryCompletedResponseSchema,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/pedidos/entregas/{delivery_id}/complete",
    response_model=DeliveryCompletedResponseSchema,
    status_code=status.HTTP_200_OK,
)
def complete_delivery(
    delivery_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Garcom", "Gerente", "Adm")),
) -> dict:
    """
    Finaliza a entrega ativa (`DELIVERED` / `Entregue`), libera o garçom e, caso existam
    itens pendentes na fila FIFO (`WAITING_DELIVERY_PICKUP`), despacha reativamente o mais antigo.
    """
    service = DeliveryService(db)
    result = service.complete_delivery(delivery_or_item_id=delivery_id, waiter=usuario)
    background_tasks.add_task(service.publish_events, result.pop("events"))
    return result["delivery"]


@router.get(
    "/api/deliveries/queue",
    response_model=list[QueuedDeliveryItemSchema],
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/pedidos/entregas/fila",
    response_model=list[QueuedDeliveryItemSchema],
    status_code=status.HTTP_200_OK,
)
def listar_fila_entregas_prontas(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Garcom", "Gerente", "Adm", "Cozinheiro")),
) -> list[dict]:
    """
    Lista o backlog FIFO de itens prontos aguardando retirada (`WAITING_DELIVERY_PICKUP`).
    """
    service = DeliveryService(db)
    return service.list_ready_queue(restaurant_id=usuario.idRestaurante)

