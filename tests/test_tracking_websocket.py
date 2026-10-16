import uuid
from contextlib import ExitStack
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import app as app_module
from src.core import security
from src.database.connection import Base, get_db
from src.models.Cardapio import Cardapio
from src.models.Mesa import Mesa
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario


@pytest.fixture
def tracking_env(tmp_path, monkeypatch):
    monkeypatch.setattr(security, "SECRET_KEY", "tracking-test-secret")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'tracking.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as db:
        rest = Restaurante(
            nome="Restaurante Tracking",
            cnpj="11.111.111/0001-11",
            telefone="11999999999",
            email="rt@example.test",
            cep="01001-000",
            status=True,
        )
        db.add(rest)
        db.flush()

        mesa = Mesa(
            idRestaurante=rest.idRestaurante,
            numero=5,
            status="Ocupada",
        )
        db.add(mesa)
        db.flush()

        item = Cardapio(
            idRestaurante=rest.idRestaurante,
            nome="Costela BBQ",
            preco=60.0,
            categoria="Pratos principais",
            status=True,
        )
        db.add(item)
        db.flush()

        cook = Usuario(
            nome="Chef Cozinha",
            email="chef@test.com",
            cpf="222.222.222-22",
            senha=b"$2b$12$Xs8OAPwFkuebFY548yaHhu6nJopBQgBIK/DD897/mMIR4uzOQz4aC".decode("utf-8"),
            funcao="Cozinheiro",
            idRestaurante=rest.idRestaurante,
            status=True,
        )
        waiter1 = Usuario(
            nome="Garçom 1",
            email="garcom1@test.com",
            cpf="333.333.333-33",
            senha=b"$2b$12$Xs8OAPwFkuebFY548yaHhu6nJopBQgBIK/DD897/mMIR4uzOQz4aC".decode("utf-8"),
            funcao="Garcom",
            idRestaurante=rest.idRestaurante,
            status=True,
        )
        waiter2 = Usuario(
            nome="Garçom 2 (Outro)",
            email="garcom2@test.com",
            cpf="444.444.444-44",
            senha=b"$2b$12$Xs8OAPwFkuebFY548yaHhu6nJopBQgBIK/DD897/mMIR4uzOQz4aC".decode("utf-8"),
            funcao="Garcom",
            idRestaurante=rest.idRestaurante,
            status=True,
        )
        db.add_all([cook, waiter1, waiter2])
        db.commit()

        yield {
            "session_factory": session_factory,
            "idRestaurante": rest.idRestaurante,
            "idMesa": mesa.idMesa,
            "idCardapio": item.idCardapio,
            "cook": cook,
            "waiter1": waiter1,
            "waiter2": waiter2,
        }


def test_order_tracking_websocket_and_rf06_notification(tracking_env):
    def override_get_db():
        with tracking_env["session_factory"]() as db:
            yield db

    app_module.app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app_module.app)

    try:
        # 1. Cria pedido com o garçom 1
        waiter1_token = security.criar_token(tracking_env["waiter1"].idUsuario, "Garcom")
        cook_token = security.criar_token(tracking_env["cook"].idUsuario, "Cozinheiro")
        waiter2_token = security.criar_token(tracking_env["waiter2"].idUsuario, "Garcom")

        create_res = client.post(
            "/pedidos",
            headers={"Authorization": f"Bearer {waiter1_token}"},
            json={
                "idMesa": str(tracking_env["idMesa"]),
                "sessao_id": "sessao-track-1",
                "itens": [
                    {
                        "idCardapio": str(tracking_env["idCardapio"]),
                        "quantidade": 1,
                        "observacao": "Sem pimenta",
                    }
                ],
            },
        )
        assert create_res.status_code == 201
        order_data = create_res.json()
        order_id = order_data["pedido"]["idPedido"]
        item_id = order_data["itens"][0]["idItemPedido"]

        # 2. Testa fallback HTTP GET /pedidos/{idPedido}/tracking
        http_track = client.get(f"/pedidos/{order_id}/tracking")
        assert http_track.status_code == 200
        track_json = http_track.json()
        assert track_json["type"] == "ORDER_UPDATE"
        assert track_json["order"]["id"] == order_id
        assert track_json["order"]["status"] == "PENDING"
        assert track_json["order"]["items"][0]["status"] == "PENDING"

        # 3. Testa WebSocket de tracking e notificações de garçons (RF06)
        with ExitStack() as stack:
            # Conecta socket do cliente (tracking)
            track_ws = stack.enter_context(client.websocket_connect(f"/ws/tracking/{order_id}"))
            initial_snap = track_ws.receive_json()
            assert initial_snap["type"] == "ORDER_UPDATE"
            assert initial_snap["order"]["id"] == order_id

            # Conecta socket do Garçom 2 (que NÃO é o garçom atribuído)
            waiter2_ws = stack.enter_context(client.websocket_connect("/pedidos/ws"))
            waiter2_ws.send_json({"type": "authenticate", "token": waiter2_token})
            w2_snap = waiter2_ws.receive_json()
            assert w2_snap["type"] == "queue.snapshot"

            # 4. Cozinheiro inicia preparo do item ("Em preparo")
            prep_res = client.patch(
                f"/pedidos/itens/{item_id}/status",
                headers={"Authorization": f"Bearer {cook_token}"},
                json={"status": "Em preparo"},
            )
            assert prep_res.status_code == 200

            # Cliente tracking recebe ITEM_UPDATE com IN_PREPARATION
            track_msg = track_ws.receive_json()
            assert track_msg["type"] == "ITEM_UPDATE"
            assert track_msg["item"]["status"] == "IN_PREPARATION"

            # 5. Cozinheiro finaliza item ("Pronto") -> RF06 dispara para Garçom 2
            ready_res = client.patch(
                f"/pedidos/itens/{item_id}/status",
                headers={"Authorization": f"Bearer {cook_token}"},
                json={"status": "Pronto"},
            )
            assert ready_res.status_code == 200

            # Cliente tracking recebe ITEM_UPDATE com READY
            track_msg2 = track_ws.receive_json()
            assert track_msg2["type"] == "ITEM_UPDATE"
            assert track_msg2["item"]["status"] == "READY"

            # RF06: Garçom 2 (todos os garçons) recebe o evento de item Pronto
            w2_msg = waiter2_ws.receive_json()
            assert w2_msg["type"] == "item.status_changed"
            assert w2_msg["item"]["status"] == "Pronto"

    finally:
        app_module.app.dependency_overrides.clear()
