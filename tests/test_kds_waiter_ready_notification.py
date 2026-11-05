import asyncio
import time
import uuid
from contextlib import ExitStack

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import app as app_module
from src.core import security
from src.core.events import DomainEventBus
from src.core.realtime import RealtimeHub
from src.database.connection import Base, get_db
from src.models.Cardapio import Cardapio
from src.models.Mesa import Mesa
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.schemas.KdsNotificationSchema import (
    KdsItemReadyPayloadSchema,
    OrderItemReadyEvent,
)


@pytest.fixture
def kds_waiters_env(tmp_path, monkeypatch):
    monkeypatch.setattr(security, "SECRET_KEY", "kds-waiters-ready-secret-key")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'kds_waiters.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as db:
        rest_main = Restaurante(
            nome="FastCooking Matriz",
            cnpj="12.345.678/0001-90",
            telefone="11988887777",
            email="matriz@fastcooking.test",
            cep="01001-000",
            status=True,
        )
        rest_other = Restaurante(
            nome="FastCooking Filial",
            cnpj="98.765.432/0001-10",
            telefone="11977776666",
            email="filial@fastcooking.test",
            cep="02002-000",
            status=True,
        )
        db.add_all([rest_main, rest_other])
        db.flush()

        mesa = Mesa(
            idRestaurante=rest_main.idRestaurante,
            numero=14,
            status="Indisponivel",
        )
        prato = Cardapio(
            idRestaurante=rest_main.idRestaurante,
            nome="Risoto de Camarão",
            preco=68.90,
            categoria="Prato principal",
            status=True,
        )
        db.add_all([mesa, prato])
        db.flush()

        cook = Usuario(
            idRestaurante=rest_main.idRestaurante,
            nome="Chef Henrique",
            cpf="101.101.101-01",
            email="chef@fastcooking.test",
            senha="hashed_password",
            funcao="Cozinheiro",
            status=True,
        )
        waiter_1 = Usuario(
            idRestaurante=rest_main.idRestaurante,
            nome="Garçom Lucas (Criador)",
            cpf="202.202.202-02",
            email="lucas@fastcooking.test",
            senha="hashed_password",
            funcao="Garcom",
            status=True,
        )
        waiter_2 = Usuario(
            idRestaurante=rest_main.idRestaurante,
            nome="Garçom Mariana (Pool)",
            cpf="303.303.303-03",
            email="mariana@fastcooking.test",
            senha="hashed_password",
            funcao="Garcom",
            status=True,
        )
        waiter_3 = Usuario(
            idRestaurante=rest_main.idRestaurante,
            nome="Garçom Pedro (Pool)",
            cpf="404.404.404-04",
            email="pedro@fastcooking.test",
            senha="hashed_password",
            funcao="Garcom",
            status=True,
        )
        waiter_inactive = Usuario(
            idRestaurante=rest_main.idRestaurante,
            nome="Garçom Inativo",
            cpf="505.505.505-05",
            email="inativo@fastcooking.test",
            senha="hashed_password",
            funcao="Garcom",
            status=False,
        )
        waiter_other_tenant = Usuario(
            idRestaurante=rest_other.idRestaurante,
            nome="Garçom Outro Restaurante",
            cpf="606.606.606-06",
            email="outro@fastcooking.test",
            senha="hashed_password",
            funcao="Garcom",
            status=True,
        )

        db.add_all(
            [
                cook,
                waiter_1,
                waiter_2,
                waiter_3,
                waiter_inactive,
                waiter_other_tenant,
            ]
        )
        db.commit()

        ids = {
            "restaurant": rest_main.idRestaurante,
            "other_restaurant": rest_other.idRestaurante,
            "table": mesa.idMesa,
            "table_number": mesa.numero,
            "menu": prato.idCardapio,
            "cook": cook.idUsuario,
            "waiter_1": waiter_1.idUsuario,
            "waiter_2": waiter_2.idUsuario,
            "waiter_3": waiter_3.idUsuario,
            "waiter_inactive": waiter_inactive.idUsuario,
            "waiter_other_tenant": waiter_other_tenant.idUsuario,
        }

    def override_get_db():
        with session_factory() as db:
            yield db

    app_module.app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app_module.app)
    try:
        yield client, ids
    finally:
        app_module.app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_all_active_waiters_receive_kds_item_ready_under_one_second(kds_waiters_env):
    """
    Requisito 1 (SLA < 1000ms e Contrato do Payload):
    Valida que TODOS os garçons autenticados e em serviço (ON_SHIFT) recebem o evento
    `kds:item_ready` em menos de 1 segundo quando o cozinheiro finaliza o prato no KDS.
    """
    client, ids = kds_waiters_env

    cook_token = security.criar_token(ids["cook"], "Cozinheiro", ids["restaurant"])
    w1_token = security.criar_token(
        ids["waiter_1"], "Garcom", ids["restaurant"], shift_status="ON_SHIFT"
    )
    w2_token = security.criar_token(
        ids["waiter_2"], "Garcom", ids["restaurant"], shift_status="ON_SHIFT"
    )
    w3_token = security.criar_token(
        ids["waiter_3"], "Garcom", ids["restaurant"], shift_status="ON_SHIFT"
    )

    # 1. Garçom 1 abre o pedido na Mesa 14
    order_res = client.post(
        "/pedidos",
        headers={"Authorization": f"Bearer {w1_token}"},
        json={
            "idMesa": str(ids["table"]),
            "itens": [
                {
                    "idCardapio": str(ids["menu"]),
                    "quantidade": 2,
                    "observacao": "Sem coentro, bem quente",
                }
            ],
        },
    )
    assert order_res.status_code == 201
    item_id = order_res.json()["itens"][0]["idItemPedido"]

    # 2. Cozinheiro avança o item para 'Em preparo'
    prep_res = client.patch(
        f"/pedidos/itens/{item_id}/status",
        headers={"Authorization": f"Bearer {cook_token}"},
        json={"status": "Em preparo"},
    )
    assert prep_res.status_code == 200

    # 3. Três garçons em serviço (ON_SHIFT) conectam à sala dedicada via Handshake Header
    with ExitStack() as stack:
        waiter_sockets = []
        for token in (w1_token, w2_token, w3_token):
            ws = stack.enter_context(
                client.websocket_connect(
                    "/ws/waiters",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-Shift-Status": "ON_SHIFT",
                    },
                )
            )
            joined = ws.receive_json()
            assert joined["type"] == "room.joined"
            assert joined["room"] == "room:waiters:active"
            assert joined["shiftStatus"] == "ON_SHIFT"
            waiter_sockets.append(ws)

        # 4. Cozinheiro muda o status para 'Pronto' -> dispara OrderItemReadyEvent
        started_at = time.perf_counter()
        ready_res = client.patch(
            f"/pedidos/itens/{item_id}/status",
            headers={"Authorization": f"Bearer {cook_token}"},
            json={"status": "Pronto"},
        )
        assert ready_res.status_code == 200

        received_payloads = [ws.receive_json() for ws in waiter_sockets]
        elapsed_seconds = time.perf_counter() - started_at

        # Validação estrita de SLA (< 1000ms)
        assert elapsed_seconds < 1.0, f"SLA violado: levou {elapsed_seconds:.3f}s"

        # Validação do contrato do payload em todos os garçons ativos
        event_ids = set()
        for payload in received_payloads:
            validated = KdsItemReadyPayloadSchema(**payload)
            assert validated.event == "kds:item_ready"
            assert validated.type == "kds:item_ready"
            assert validated.tableNumber == 14
            assert validated.notes == "Sem coentro, bem quente"
            assert len(validated.items) == 1
            assert validated.items[0].id == item_id
            assert validated.items[0].name == "Risoto de Camarão"
            assert validated.items[0].quantity == 2
            uuid.UUID(validated.eventId)
            event_ids.add(validated.eventId)

        # Todos os garçons do pool receberam o mesmo evento idempotente
        assert len(event_ids) == 1


class _SimulatedWaiterSocket:
    """Mock de WebSocket para simular clientes saudáveis, desconectados e lentos (half-open)."""

    def __init__(self, mode: str = "healthy", delay_seconds: float = 0.0):
        self.mode = mode
        self.delay_seconds = delay_seconds
        self.messages: list[dict] = []

    async def send_json(self, data: dict) -> None:
        # Permite o frame inicial 'room.joined' e simula falha durante o broadcast
        if self.messages:
            if self.mode == "disconnected":
                raise RuntimeError("Socket closed abruptly (ECONNRESET)")
            if self.mode == "half_open_slow":
                await asyncio.sleep(self.delay_seconds)
        self.messages.append(data)


@pytest.mark.anyio
async def test_fault_isolation_dead_and_slow_sockets_do_not_block_healthy_waiters():
    """
    Requisito 2 (Isolamento de Falhas e Non-Blocking Broadcast):
    Simula garçons com conexão interrompida e em half-open state (timeout) e prova que
    os garçons saudáveis recebem o alerta sem atraso e que os sockets defeituosos são descartados.
    """
    hub = RealtimeHub(send_timeout=0.08)
    bus = DomainEventBus()
    bus.subscribe(OrderItemReadyEvent, hub.broadcast_item_ready)

    restaurant_id = uuid.uuid4()
    healthy_waiter_1 = _SimulatedWaiterSocket(mode="healthy")
    healthy_waiter_2 = _SimulatedWaiterSocket(mode="healthy")
    crashed_waiter = _SimulatedWaiterSocket(mode="disconnected")
    slow_half_open_waiter = _SimulatedWaiterSocket(
        mode="half_open_slow", delay_seconds=0.50
    )

    for idx, sock in enumerate(
        (healthy_waiter_1, healthy_waiter_2, crashed_waiter, slow_half_open_waiter),
        start=1,
    ):
        await hub.join_waiters_room(
            websocket=sock,  # type: ignore[arg-type]
            restaurant_id=restaurant_id,
            user_id=f"waiter-{idx}",
            role="Garcom",
            shift_status="ON_SHIFT",
        )

    assert len(hub.get_active_waiter_connections(restaurant_id)) == 4

    event = OrderItemReadyEvent(
        restaurant_id=restaurant_id,
        order_id=uuid.uuid4(),
        table_number=7,
        item_id=uuid.uuid4(),
        item_name="Filé à Parmegiana",
        quantity=1,
        notes=None,  # Deve ser normalizado para ""
    )

    started_at = time.perf_counter()
    await bus.publish(event)
    elapsed_seconds = time.perf_counter() - started_at

    # O broadcast total deve respeitar o timeout curto (0.08s) e ficar muito abaixo de 1s
    assert elapsed_seconds < 0.25

    # Garçons saudáveis receberam o evento normalmente
    for healthy in (healthy_waiter_1, healthy_waiter_2):
        assert len(healthy.messages) == 2
        ready_msg = healthy.messages[-1]
        assert ready_msg["event"] == "kds:item_ready"
        assert ready_msg["tableNumber"] == 7
        assert ready_msg["notes"] == ""
        assert ready_msg["items"][0]["name"] == "Filé à Parmegiana"

    # Os 2 sockets problemáticos foram automaticamente expurgados da sala ativa
    remaining = hub.get_active_waiter_connections(restaurant_id)
    assert len(remaining) == 2
    remaining_sockets = {sub.websocket for sub in remaining}
    assert healthy_waiter_1 in remaining_sockets
    assert healthy_waiter_2 in remaining_sockets
    assert crashed_waiter not in remaining_sockets
    assert slow_half_open_waiter not in remaining_sockets


def test_security_blocks_unauthenticated_cooks_and_off_shift_waiters(kds_waiters_env):
    """
    Requisito 3 (Segurança, RBAC e Presença ON_SHIFT / OFF_SHIFT):
    Garante que conexões sem token, cozinheiros e garçons fora de serviço (OFF_SHIFT)
    são barrados com códigos 4401/4403 e que um garçom que encerra o turno para de receber alertas.
    """
    client, ids = kds_waiters_env

    cook_token = security.criar_token(ids["cook"], "Cozinheiro", ids["restaurant"])
    off_shift_token = security.criar_token(
        ids["waiter_2"], "Garcom", ids["restaurant"], shift_status="OFF_SHIFT"
    )
    inactive_user_token = security.criar_token(
        ids["waiter_inactive"], "Garcom", ids["restaurant"]
    )
    active_waiter_1_token = security.criar_token(
        ids["waiter_1"], "Garcom", ids["restaurant"], shift_status="ON_SHIFT"
    )
    active_waiter_3_token = security.criar_token(
        ids["waiter_3"], "Garcom", ids["restaurant"], shift_status="ON_SHIFT"
    )

    # 1. Sem token -> fecha com 4401
    with client.websocket_connect("/ws/waiters") as ws_unauth:
        ws_unauth.send_json({"type": "authenticate", "token": ""})
        with pytest.raises(WebSocketDisconnect) as exc_unauth:
            ws_unauth.receive_json()
        assert exc_unauth.value.code == 4401

    # 2. Cozinheiro tentando conectar na sala exclusiva de garçons -> fecha com 4403
    with client.websocket_connect(
        "/ws/waiters",
        headers={"Authorization": f"Bearer {cook_token}"},
    ) as ws_cook:
        with pytest.raises(WebSocketDisconnect) as exc_cook:
            ws_cook.receive_json()
        assert exc_cook.value.code == 4403

    # 3. Garçom com turno OFF_SHIFT -> fecha com 4403
    with client.websocket_connect(
        "/ws/waiters",
        headers={"Authorization": f"Bearer {off_shift_token}"},
    ) as ws_off_shift:
        with pytest.raises(WebSocketDisconnect) as exc_off:
            ws_off_shift.receive_json()
        assert exc_off.value.code == 4403

    # 4. Garçom desativado no banco -> fecha com 4401
    with client.websocket_connect(
        "/ws/waiters",
        headers={"Authorization": f"Bearer {inactive_user_token}"},
    ) as ws_inactive:
        with pytest.raises(WebSocketDisconnect) as exc_inact:
            ws_inactive.receive_json()
        assert exc_inact.value.code == 4401

    # 5. Garçom 3 entra ON_SHIFT, mas encerra o turno (shift:end) antes de o prato ficar pronto
    with ExitStack() as stack:
        ws_w1 = stack.enter_context(
            client.websocket_connect(
                "/ws/waiters",
                headers={"Authorization": f"Bearer {active_waiter_1_token}"},
            )
        )
        assert ws_w1.receive_json()["type"] == "room.joined"

        ws_w3 = stack.enter_context(
            client.websocket_connect(
                "/ws/waiters",
                headers={"Authorization": f"Bearer {active_waiter_3_token}"},
            )
        )
        assert ws_w3.receive_json()["type"] == "room.joined"

        # Garçom 3 encerra seu expediente em tempo real
        ws_w3.send_json({"type": "shift:end"})
        left_msg = ws_w3.receive_json()
        assert left_msg["type"] == "room.left"
        assert left_msg["reason"] == "shift_ended"
        with pytest.raises(WebSocketDisconnect) as exc_left:
            ws_w3.receive_json()
        assert exc_left.value.code == 4403

        # Pedido é criado e avançado para Pronto
        order_res = client.post(
            "/pedidos",
            headers={"Authorization": f"Bearer {active_waiter_1_token}"},
            json={
                "idMesa": str(ids["table"]),
                "itens": [{"idCardapio": str(ids["menu"]), "quantidade": 1}],
            },
        )
        item_id = order_res.json()["itens"][0]["idItemPedido"]

        client.patch(
            f"/pedidos/itens/{item_id}/status",
            headers={"Authorization": f"Bearer {cook_token}"},
            json={"status": "Em preparo"},
        )
        client.patch(
            f"/pedidos/itens/{item_id}/status",
            headers={"Authorization": f"Bearer {cook_token}"},
            json={"status": "Pronto"},
        )

        # Garçom 1 (ainda ON_SHIFT) recebe o alerta normalmente
        ready_alert = ws_w1.receive_json()
        assert ready_alert["event"] == "kds:item_ready"
        assert ready_alert["items"][0]["id"] == item_id

