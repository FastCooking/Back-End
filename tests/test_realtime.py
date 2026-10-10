import time
from contextlib import ExitStack
from uuid import UUID

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src import app as app_module
from src.core import security
from src.core.realtime import RealtimeHub
from src.database.connection import Base, get_db
from src.models.Cardapio import Cardapio
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario


@pytest.fixture
def realtime_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(security, "SECRET_KEY", "realtime-test-secret")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'realtime.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as db:
        first_restaurant = Restaurante(
            nome="Restaurante 1",
            cnpj="11.111.111/0001-11",
            telefone="11999999999",
            email="r1@example.test",
            cep="01001-000",
            status=True,
        )
        second_restaurant = Restaurante(
            nome="Restaurante 2",
            cnpj="22.222.222/0001-22",
            telefone="11999999998",
            email="r2@example.test",
            cep="01001-001",
            status=True,
        )
        db.add_all([first_restaurant, second_restaurant])
        db.flush()

        mesa = Mesa(
            idRestaurante=first_restaurant.idRestaurante,
            numero=1,
            status="Disponivel",
        )
        cardapio = Cardapio(
            idRestaurante=first_restaurant.idRestaurante,
            nome="Prato de teste",
            preco=12.50,
            categoria="Teste",
            pathImage="test.png",
            status=True,
        )
        users = {
            "cook": Usuario(
                idRestaurante=first_restaurant.idRestaurante,
                nome="Cozinheiro 1",
                cpf="111.111.111-11",
                email="cook1@example.test",
                senha="unused",
                funcao="Cozinheiro",
                status=True,
            ),
            "cook2": Usuario(
                idRestaurante=first_restaurant.idRestaurante,
                nome="Cozinheiro 2",
                cpf="222.222.222-22",
                email="cook2@example.test",
                senha="unused",
                funcao="Cozinheiro",
                status=True,
            ),
            "waiter": Usuario(
                idRestaurante=first_restaurant.idRestaurante,
                nome="Garcom 1",
                cpf="333.333.333-33",
                email="waiter1@example.test",
                senha="unused",
                funcao="Garcom",
                status=True,
            ),
            "other_waiter": Usuario(
                idRestaurante=first_restaurant.idRestaurante,
                nome="Garcom 2",
                cpf="444.444.444-44",
                email="waiter2@example.test",
                senha="unused",
                funcao="Garcom",
                status=True,
            ),
            "other_cook": Usuario(
                idRestaurante=second_restaurant.idRestaurante,
                nome="Cozinheiro 3",
                cpf="555.555.555-55",
                email="cook3@example.test",
                senha="unused",
                funcao="Cozinheiro",
                status=True,
            ),
            "admin": Usuario(
                idRestaurante=first_restaurant.idRestaurante,
                nome="Administrador",
                cpf="666.666.666-66",
                email="admin@example.test",
                senha="unused",
                funcao="Adm",
                status=True,
            ),
            "customer": Usuario(
                idRestaurante=first_restaurant.idRestaurante,
                nome="Cliente sem mecanismo definido",
                cpf="777.777.777-77",
                email="customer@example.test",
                senha="unused",
                funcao="Cliente",
                status=True,
            ),
        }
        db.add_all([mesa, cardapio, *users.values()])
        db.commit()
        ids = {
            "restaurant": first_restaurant.idRestaurante,
            "other_restaurant": second_restaurant.idRestaurante,
            "table": mesa.idMesa,
            "menu": cardapio.idCardapio,
            **{key: value.idUsuario for key, value in users.items()},
        }

    def override_get_db():
        with session_factory() as db:
            yield db

    app_module.app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app_module.app)
    try:
        yield client, session_factory, ids
    finally:
        app_module.app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _token(user_id: int, role: str) -> str:
    return security.criar_token(user_id, role)


def _auth_message(token: str) -> dict[str, str]:
    return {"type": "authenticate", "token": token}


def _create_order(client: TestClient, ids: dict, waiter_id: int) -> dict:
    response = client.post(
        "/pedidos",
        headers={"Authorization": f"Bearer {_token(waiter_id, 'Garcom')}"},
        json={
            "idMesa": str(ids["table"]),
            "itens": [{"idCardapio": str(ids["menu"]), "quantidade": 2}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_websocket_broadcasts_created_item_to_authorized_clients_within_one_second(
    realtime_environment,
):
    client, _, ids = realtime_environment
    cook_token = _token(ids["cook"], "Cozinheiro")
    cook2_token = _token(ids["cook2"], "Cozinheiro")
    waiter_token = _token(ids["waiter"], "Garcom")

    with ExitStack() as stack:
        sockets = []
        for token in (cook_token, cook2_token, waiter_token):
            websocket = stack.enter_context(client.websocket_connect("/pedidos/ws"))
            websocket.send_json(_auth_message(token))
            snapshot = websocket.receive_json()
            assert snapshot["type"] == "queue.snapshot"
            sockets.append(websocket)

        started = time.perf_counter()
        created = _create_order(client, ids, ids["waiter"])
        received = [socket.receive_json() for socket in sockets]
        elapsed = time.perf_counter() - started

        print(f"Latência API até recebimento do evento: {elapsed * 1000:.2f} ms")
        assert elapsed < 1.0
        assert all(event["type"] == "item.created" for event in received)
        assert all(event["item"]["status"] == "Pendente" for event in received)
        assert len({event["eventId"] for event in received}) == 1

        queue_updates = [socket.receive_json() for socket in sockets]
        assert all(event["type"] == "queue.updated" for event in queue_updates)
        assert (
            created["itens"][0]["idItemPedido"] == received[0]["item"]["idItemPedido"]
        )


def test_status_change_is_broadcast_and_reconnect_receives_current_snapshot(
    realtime_environment,
):
    client, _, ids = realtime_environment
    created = _create_order(client, ids, ids["waiter"])
    item_id = created["itens"][0]["idItemPedido"]
    token = _token(ids["cook"], "Cozinheiro")

    with ExitStack() as stack:
        sockets = [
            stack.enter_context(client.websocket_connect("/pedidos/ws"))
            for _ in range(2)
        ]
        for websocket in sockets:
            websocket.send_json(_auth_message(token))
            websocket.receive_json()

        started = time.perf_counter()
        response = client.patch(
            f"/pedidos/itens/{item_id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "Em preparo"},
        )
        assert response.status_code == 200, response.text
        status_events = [socket.receive_json() for socket in sockets]
        elapsed = time.perf_counter() - started
        print(f"Latência da mudança de status até os clientes: {elapsed * 1000:.2f} ms")
        assert elapsed < 1.0
        assert all(event["type"] == "item.status_changed" for event in status_events)
        assert all(event["item"]["status"] == "Em preparo" for event in status_events)
        assert len({event["eventId"] for event in status_events}) == 1
        for socket in sockets:
            assert socket.receive_json()["type"] == "queue.updated"

    with client.websocket_connect("/pedidos/ws") as reconnected:
        reconnected.send_json(_auth_message(token))
        snapshot = reconnected.receive_json()
    assert snapshot["type"] == "queue.snapshot"
    assert any(
        item["idItemPedido"] == item_id and item["status"] == "Em preparo"
        for item in snapshot["data"]["items"]
    )
    assert snapshot["data"]["priorityApplied"] is False


def test_invalid_status_transition_is_rejected_without_queue_event(
    realtime_environment,
):
    client, session_factory, ids = realtime_environment
    created = _create_order(client, ids, ids["waiter"])
    item_id = created["itens"][0]["idItemPedido"]
    token = _token(ids["cook"], "Cozinheiro")
    from src.core.realtime import realtime_hub

    with client.websocket_connect("/pedidos/ws") as websocket:
        websocket.send_json(_auth_message(token))
        websocket.receive_json()
        version_before = realtime_hub.queue_version
        response = client.patch(
            f"/pedidos/itens/{item_id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "Entregue"},
        )
        assert response.status_code == 409
        assert realtime_hub.queue_version == version_before

    with session_factory() as db:
        item = db.query(ItemPedido).filter_by(idItemPedido=UUID(item_id)).one()
        assert item.status == "Pendente"


def test_websocket_rejects_missing_and_unsupported_authentication(realtime_environment):
    client, _, ids = realtime_environment

    with client.websocket_connect("/pedidos/ws") as websocket:
        websocket.send_json({"type": "authenticate"})
        with pytest.raises(WebSocketDisconnect) as missing:
            websocket.receive_json()
        assert missing.value.code == 4401

    with client.websocket_connect("/pedidos/ws") as websocket:
        websocket.send_json(_auth_message("invalid.jwt.token"))
        with pytest.raises(WebSocketDisconnect) as invalid_token:
            websocket.receive_json()
        assert invalid_token.value.code == 4401

    with client.websocket_connect("/pedidos/ws") as websocket:
        websocket.send_json(_auth_message(_token(ids["admin"], "Adm")))
        with pytest.raises(WebSocketDisconnect) as unsupported:
            websocket.receive_json()
        assert unsupported.value.code == 4403

    with client.websocket_connect("/pedidos/ws") as websocket:
        websocket.send_json(_auth_message(_token(ids["customer"], "Cliente")))
        with pytest.raises(WebSocketDisconnect) as customer:
            websocket.receive_json()
        assert customer.value.code == 4403


def test_failed_commit_does_not_publish_item_event(realtime_environment, monkeypatch):
    client, session_factory, ids = realtime_environment
    created = _create_order(client, ids, ids["waiter"])
    item_id = created["itens"][0]["idItemPedido"]
    token = _token(ids["cook"], "Cozinheiro")
    from src.core.realtime import realtime_hub

    with client.websocket_connect("/pedidos/ws") as websocket:
        websocket.send_json(_auth_message(token))
        websocket.receive_json()
        version_before = realtime_hub.queue_version

        def fail_commit(_self):
            raise RuntimeError("simulated database commit failure")

        monkeypatch.setattr(Session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="simulated database commit failure"):
            _create_order(client, ids, ids["waiter"])

        assert realtime_hub.queue_version == version_before
        with pytest.raises(RuntimeError, match="simulated database commit failure"):
            client.patch(
                f"/pedidos/itens/{item_id}/status",
                headers={"Authorization": f"Bearer {token}"},
                json={"status": "Em preparo"},
            )
        assert realtime_hub.queue_version == version_before
        with session_factory() as db:
            item = db.query(ItemPedido).filter_by(idItemPedido=UUID(item_id)).one()
            assert item.status == "Pendente"


class _FakeWebSocket:
    def __init__(self, fail_after_snapshot: bool = False):
        self.messages = []
        self.fail_after_snapshot = fail_after_snapshot

    async def send_json(self, message):
        if self.fail_after_snapshot and self.messages:
            raise RuntimeError("closed socket")
        self.messages.append(message)


@pytest.mark.anyio
async def test_hub_isolates_audience_and_removes_failed_connections():
    hub = RealtimeHub()
    cook = _FakeWebSocket()
    assigned_waiter = _FakeWebSocket()
    other_waiter = _FakeWebSocket()
    other_restaurant = _FakeWebSocket()
    broken = _FakeWebSocket(fail_after_snapshot=True)

    subscriptions = [
        (cook, 1, 1, "Cozinheiro"),
        (assigned_waiter, 1, 2, "Garcom"),
        (other_waiter, 1, 3, "Garcom"),
        (other_restaurant, 2, 4, "Cozinheiro"),
        (broken, 1, 5, "Cozinheiro"),
    ]
    for websocket, restaurant_id, user_id, role in subscriptions:
        await hub.connect_and_sync(
            websocket,
            restaurant_id,
            user_id,
            role,
            lambda: {"items": []},
        )

    await hub.publish_item_event(
        "item.created",
        restaurant_id=1,
        item_data={"idItemPedido": 10, "status": "Pendente"},
        assigned_waiter_id=2,
    )

    assert [message["type"] for message in cook.messages[-2:]] == [
        "item.created",
        "queue.updated",
    ]
    assert [message["type"] for message in assigned_waiter.messages[-2:]] == [
        "item.created",
        "queue.updated",
    ]
    assert len(other_waiter.messages) == 1
    assert len(other_restaurant.messages) == 1
    assert broken not in {subscription.websocket for subscription in hub._subscriptions}

    await hub.disconnect(cook)
    assert cook not in {subscription.websocket for subscription in hub._subscriptions}
