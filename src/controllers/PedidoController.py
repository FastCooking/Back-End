import asyncio
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, WebSocket
from fastapi import status as http_status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.websockets import WebSocketDisconnect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.realtime import realtime_hub
from src.core.security import decodificar_token, exigir_funcao, get_user_from_token
from src.database.connection import get_db
from src.models.Usuario import Usuario
from src.schemas.PedidoSchema import (
    ItemPedidoStatusUpdate,
    PedidoCreate,
    PedidoItemCreate,
)
from src.services.PedidoService import PedidoService

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])

security_optional = HTTPBearer(auto_error=False)


def get_optional_user(
    credenciais: HTTPAuthorizationCredentials | None = Depends(security_optional),
    db: Session = Depends(get_db),
) -> Usuario | None:
    if credenciais is None:
        return None
    try:
        return get_user_from_token(credenciais.credentials, db)
    except Exception:  # noqa: BLE001
        return None


@router.post("", status_code=http_status.HTTP_201_CREATED)
def criar_pedido(
    dados: PedidoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(get_optional_user),
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
    usuario: Usuario | None = Depends(get_optional_user),
) -> dict:
    service = PedidoService(db)
    result = service.add_items(idPedido, itens, usuario)
    background_tasks.add_task(service.publish_events, result.pop("events"))
    return result


@router.get("/{idPedido}")
def obter_pedido(
    idPedido: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    service = PedidoService(db)
    return service.get_order(idPedido)


@router.get("/{idPedido}/tracking")
def obter_tracking_pedido(
    idPedido: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    service = PedidoService(db)
    return service.get_order_tracking(idPedido)


@router.websocket("/tracking/{idPedido}")
@router.websocket("/ws/tracking/{idPedido}")
async def tracking_websocket(
    websocket: WebSocket,
    idPedido: uuid.UUID,
    db: Session = Depends(get_db),
) -> None:
    await handle_tracking_websocket(websocket, idPedido, db)


async def handle_tracking_websocket(
    websocket: WebSocket,
    idPedido: uuid.UUID,
    db: Session,
) -> None:
    await websocket.accept()
    service = PedidoService(db)
    snapshot = service.get_order_tracking(idPedido)
    if snapshot.get("type") == "ERROR":
        await websocket.send_json(snapshot)
        await websocket.close(code=4404)
        return

    await realtime_hub.connect_tracking(
        websocket=websocket,
        order_id=idPedido,
        snapshot_factory=lambda: service.get_order_tracking(idPedido),
    )

    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if msg == "ping":
                    await websocket.send_text("pong")
            except TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        await websocket.close(code=1011)
    finally:
        await realtime_hub.disconnect_tracking(websocket)


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


@router.patch("/itens/{idItemPedido}/liberar-sobremesa")
def liberar_sobremesa(
    idItemPedido: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Garcom")),
) -> dict:
    service = PedidoService(db)
    result = service.liberar_sobremesa(idItemPedido, usuario)
    background_tasks.add_task(
        service.publish_events,
        result.pop("events"),
    )
    return result


@router.patch("/itens/{idItemPedido}/cancelar")
def cancelar_item(
    idItemPedido: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Garcom", "Gerente", "Adm")),
) -> dict:
    service = PedidoService(db)
    result = service.cancelar_item(idItemPedido, usuario)
    background_tasks.add_task(service.publish_events, [result.pop("event")])
    return result


from pydantic import BaseModel

from src.models.Mesa import Mesa
from src.models.Pagamento import Pagamento
from src.models.Pedido import Pedido
from src.models.Sessao import Sessao


class PagamentoCreateRequest(BaseModel):
    formaPagamento: str
    valor: float | None = None


@router.post("/{idPedido}/pagamento", status_code=http_status.HTTP_201_CREATED)
def registrar_pagamento(
    idPedido: uuid.UUID,
    dados: PagamentoCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Garcom", "Gerente", "Adm")),
) -> dict:
    service = PedidoService(db)
    pedido = Pedido.get_by_id(db, idPedido)
    if not pedido or pedido.idRestaurante != usuario.idRestaurante:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Pedido não encontrado.",
        )

    if pedido.status in ("Fechado", "Cancelado"):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Este pedido já foi encerrado.",
        )

    # Calcula valor total se não informado
    valor_total = dados.valor
    if valor_total is None or valor_total <= 0:
        dados_pedido = service.get_order(idPedido)
        valor_total = float(dados_pedido.get("total", 0.0))

    # Cria pagamento
    pagamento = Pagamento.create(
        db,
        idPedido=idPedido,
        formaPagamento=dados.formaPagamento,
        valor=valor_total,
    )

    # Fecha o pedido
    pedido.update_stats(db, "Fechado", commit=False)
    pedido.dataFechamento = datetime.now()

    # Libera a mesa
    mesa = Mesa.get_by_id(db, pedido.idMesa)
    if mesa:
        mesa.update(db, status="Disponivel", commit=False)

    # Encerra sessão da mesa se existir
    sessoes_abertas = db.query(Sessao).filter(Sessao.idMesa == pedido.idMesa, Sessao.status == "Aberta").all()
    for s in sessoes_abertas:
        s.status = "Fechada"

    db.commit()
    db.refresh(pedido)
    if mesa:
        db.refresh(mesa)

    event_payload = {
        "type": "order.closed",
        "idPedido": str(idPedido),
        "idMesa": str(pedido.idMesa),
        "status": "Fechado",
        "valor": float(valor_total),
        "formaPagamento": dados.formaPagamento,
    }
    background_tasks.add_task(realtime_hub.publish_event, pedido.idRestaurante, event_payload)

    return {
        "message": f"Pagamento de R$ {valor_total:.2f} registrado com sucesso. Pedido encerrado e mesa liberada.",
        "pagamento": {
            "idPagamento": str(pagamento.idPagamento),
            "formaPagamento": pagamento.formaPagamento,
            "valor": float(pagamento.valor),
        },
        "pedido": {
            "idPedido": str(pedido.idPedido),
            "status": pedido.status,
            "idMesa": str(pedido.idMesa),
        },
    }


@router.get("")
def listar_pedidos(
    idRestaurante: uuid.UUID | None = None,
    status: str | None = None,
    tipo: str | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Gerente", "Adm", "Garcom")),
) -> list[dict]:
    """Lista pedidos do restaurante com filtros de status ou tipo (ativos/historico)."""
    rest_id = usuario.idRestaurante if usuario.funcao != "Adm" else (idRestaurante or usuario.idRestaurante)

    query = db.query(Pedido).join(Mesa, Pedido.idMesa == Mesa.idMesa).outerjoin(Usuario, Pedido.idGarcom == Usuario.idUsuario)
    if rest_id:
        query = query.filter(Pedido.idRestaurante == rest_id)
    if status:
        query = query.filter(Pedido.status == status)
    elif tipo == "ativos":
        query = query.filter(Pedido.status.notin_(["Fechado", "Cancelado"]))
    elif tipo == "historico":
        query = query.filter(Pedido.status.in_(["Fechado", "Cancelado"]))

    pedidos = query.order_by(Pedido.dataAbertura.desc()).all()
    resultado = []

    for pedido in pedidos:
        itens_res = []
        total = 0.0
        for it in pedido.itens:
            subtotal = float(it.precoUnitario) * it.quantidade
            if it.status != "Cancelado":
                total += subtotal
            nome_item = it.cardapio.nome if it.cardapio else "Item do cardápio"
            itens_res.append({
                "idItemPedido": str(it.idItemPedido),
                "idCardapio": str(it.idCardapio),
                "nome": nome_item,
                "quantidade": it.quantidade,
                "precoUnitario": float(it.precoUnitario),
                "subtotal": round(subtotal, 2),
                "observacao": it.observacao,
                "status": it.status,
                "categoria": it.categoria,
            })

        pagamentos_res = []
        for p in pedido.pagamentos:
            pagamentos_res.append({
                "idPagamento": str(p.idPagamento),
                "formaPagamento": p.formaPagamento,
                "valor": float(p.valor),
                "dataPagamento": p.dataPagamento.isoformat() if p.dataPagamento else None,
            })

        resultado.append({
            "idPedido": str(pedido.idPedido),
            "idRestaurante": str(pedido.idRestaurante),
            "idMesa": str(pedido.idMesa),
            "numeroMesa": pedido.mesa.numero if pedido.mesa else None,
            "idGarcom": str(pedido.idGarcom) if pedido.idGarcom else None,
            "nomeGarcom": pedido.garcom.nome if pedido.garcom else None,
            "status": pedido.status,
            "dataAbertura": pedido.dataAbertura.isoformat() if pedido.dataAbertura else None,
            "dataFechamento": pedido.dataFechamento.isoformat() if pedido.dataFechamento else None,
            "total": round(total, 2),
            "itens": itens_res,
            "pagamentos": pagamentos_res,
        })

    return resultado


@router.get("/kds/fila")
def obter_fila(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Cozinheiro", "Garcom", "Gerente", "Adm")),
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
        auth_message = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=5,
        )

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
            try:
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=15,
                )
            except TimeoutError:
                conectado = await realtime_hub.refresh_queue(
                    websocket=websocket,
                    snapshot_factory=lambda: service.queue_snapshot(usuario),
                )

                if not conectado:
                    break

    except (TimeoutError, ValueError):
        await websocket.close(code=4401)

    except WebSocketDisconnect:
        pass

    except (OSError, RuntimeError, SQLAlchemyError):
        await websocket.close(code=1011)

    finally:
        await realtime_hub.disconnect(websocket)


def _extract_handshake_credentials(websocket: WebSocket) -> tuple[str | None, str | None]:
    """Extrai token JWT e shiftStatus dos headers ou query params do handshake WebSocket."""
    auth_header = websocket.headers.get("authorization", "")
    token: str | None = None
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    elif websocket.query_params.get("token"):
        token = websocket.query_params.get("token")

    shift_override = (
        websocket.headers.get("x-shift-status")
        or websocket.query_params.get("shiftStatus")
        or websocket.query_params.get("shift")
    )
    return token, shift_override


@router.websocket("/ws/waiters")
@router.websocket("/ws/garcons")
async def waiters_room_websocket(
    websocket: WebSocket,
    db: Session = Depends(get_db),
) -> None:
    await handle_waiter_room_websocket(websocket, db)


async def handle_waiter_room_websocket(
    websocket: WebSocket,
    db: Session,
) -> None:
    """
    Gateway WebSocket dedicado para a sala de garçons em serviço (`room:waiters:active`).
    Suporta autenticação no handshake (Header Authorization / Query ?token=) ou no 1º frame JSON,
    valida role WAITER/Garcom e status ON_SHIFT, e executa heartbeat Ping-Pong.
    """
    await websocket.accept()

    try:
        token, shift_override = _extract_handshake_credentials(websocket)

        if not token:
            auth_message = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=5.0,
            )
            if isinstance(auth_message, dict) and auth_message.get("type") == "authenticate":
                token = auth_message.get("token")
                if not shift_override:
                    shift_override = (
                        auth_message.get("shiftStatus")
                        or auth_message.get("shift_status")
                    )

        if not isinstance(token, str) or not token.strip():
            await websocket.close(code=4401)
            return

        try:
            claims = decodificar_token(token)
            usuario = get_user_from_token(token, db)
        except HTTPException:
            await websocket.close(code=4401)
            return

        effective_role = claims.get("funcao") or usuario.funcao
        effective_shift = (
            shift_override
            or claims.get("shift_status")
            or ("ON_SHIFT" if usuario.status else "OFF_SHIFT")
        ).strip().upper()

        if effective_role not in ("Garcom", "WAITER") or effective_shift != "ON_SHIFT":
            await websocket.close(code=4403)
            return

        await realtime_hub.join_waiters_room(
            websocket=websocket,
            restaurant_id=usuario.idRestaurante,
            user_id=usuario.idUsuario,
            role=effective_role,
            shift_status=effective_shift,
        )

        while True:
            try:
                raw_msg = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=25.0,
                )
                await realtime_hub.record_heartbeat(websocket)

                if raw_msg.strip().lower() == "ping":
                    await websocket.send_text("pong")
                    continue

                try:
                    parsed = json.loads(raw_msg)
                except ValueError:
                    continue

                if not isinstance(parsed, dict):
                    continue

                msg_type = parsed.get("type")
                if msg_type == "ping":
                    await websocket.send_json(
                        {
                            "type": "pong",
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )
                elif msg_type in ("shift:update", "shift:end"):
                    new_shift = (
                        "OFF_SHIFT"
                        if msg_type == "shift:end"
                        else str(parsed.get("shiftStatus", "OFF_SHIFT")).upper()
                    )
                    still_active = await realtime_hub.update_waiter_shift(
                        websocket, new_shift
                    )
                    if not still_active:
                        await websocket.send_json(
                            {
                                "type": "room.left",
                                "room": "room:waiters:active",
                                "reason": "shift_ended",
                                "timestamp": datetime.now(UTC).isoformat(),
                            }
                        )
                        await websocket.close(code=4403)
                        return

            except TimeoutError:
                try:
                    await asyncio.wait_for(
                        websocket.send_json(
                            {
                                "type": "ping",
                                "timestamp": datetime.now(UTC).isoformat(),
                            }
                        ),
                        timeout=realtime_hub.send_timeout,
                    )
                except Exception:  # noqa: BLE001
                    break

    except (TimeoutError, ValueError):
        await websocket.close(code=4401)

    except PermissionError:
        await websocket.close(code=4403)

    except WebSocketDisconnect:
        pass

    except (OSError, RuntimeError, SQLAlchemyError):
        await websocket.close(code=1011)

    finally:
        await realtime_hub.leave_waiters_room(websocket, reason="connection_closed")