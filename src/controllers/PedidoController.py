import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, WebSocket
from fastapi import status as http_status
from fastapi.websockets import WebSocketDisconnect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.realtime import realtime_hub
from src.core.security import exigir_funcao, get_user_from_token
from src.database.connection import get_db
from src.models.Usuario import Usuario
from src.schemas.PedidoSchema import (
    ItemPedidoStatusUpdate,
    PedidoCreate,
    PedidoItemCreate,
)
from src.services.PedidoService import PedidoService

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


@router.post("", status_code=http_status.HTTP_201_CREATED)
def criar_pedido(
    dados: PedidoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Garcom")),
) -> dict:
    service = PedidoService(db)
    result = service.create(dados, usuario)
    background_tasks.add_task(service.publish_events, result.pop("events"))
    return result


@router.post("/{idPedido}/itens", status_code=http_status.HTTP_201_CREATED)
def adicionar_itens_ao_pedido(
    idPedido: uuid.UUID,
    itens: list[PedidoItemCreate],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Garcom")),
) -> dict:
    service = PedidoService(db)
    result = service.add_items(idPedido, itens, usuario)
    background_tasks.add_task(service.publish_events, result.pop("events"))
    return result


@router.patch("/itens/{idItemPedido}/status")
def alterar_status_item(
    idItemPedido: uuid.UUID,
    dados: ItemPedidoStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Cozinheiro")),
) -> dict:
    service = PedidoService(db)
    result = service.update_item_status(idItemPedido, dados.status, usuario)
    background_tasks.add_task(service.publish_events, [result.pop("event")])
    return result


@router.get("/kds/fila")
def obter_fila(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Cozinheiro", "Garcom")),
) -> dict:
    return PedidoService(db).queue_snapshot(usuario)


@router.websocket("/kds/ws")
@router.websocket("/ws")
async def pedidos_websocket(
    websocket: WebSocket,
    db: Session = Depends(get_db),
) -> None:
    await websocket.accept()
    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        token = (
            auth_message.get("token")
            if isinstance(auth_message, dict)
            and auth_message.get("type") == "authenticate"
            else None
        )
        if not isinstance(token, str) or not token:
            await websocket.close(code=4401)
            return

        try:
            usuario = get_user_from_token(token, db)
        except HTTPException:
            await websocket.close(code=4401)
            return

        if usuario.funcao not in ("Cozinheiro", "Garcom"):
            await websocket.close(code=4403)
            return

        service = PedidoService(db)
        await realtime_hub.connect_and_sync(
            websocket=websocket,
            restaurant_id=usuario.idRestaurante,
            user_id=usuario.idUsuario,
            role=usuario.funcao,
            snapshot_factory=lambda: service.queue_snapshot(usuario),
        )

        while True:
            await websocket.receive_text()
    except (TimeoutError, ValueError):
        await websocket.close(code=4401)
    except WebSocketDisconnect:
        pass
    except (OSError, RuntimeError, SQLAlchemyError):
        await websocket.close(code=1011)
    finally:
        await realtime_hub.disconnect(websocket)
