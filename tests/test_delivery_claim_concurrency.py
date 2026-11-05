import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import app as app_module
from src.core import security
from src.database.connection import Base, get_db
from src.models.Cardapio import Cardapio
from src.models.Entrega import Entrega
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.schemas.DeliverySchema import DeliveryClaimedWsPayloadSchema, DeliveryState


@pytest.fixture
def delivery_env(tmp_path, monkeypatch):
    """
    Ambiente isolado com banco SQLite em arquivo temporário (suporta múltiplas conexões
    reais simultâneas entre threads para teste de concorrência real).
    """
    monkeypatch.setattr(security, "SECRET_KEY", "delivery-concurrency-test-secret")
    db_file = tmp_path / "delivery_concurrency.sqlite"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    with session_factory() as db:
        restaurante = Restaurante(
            nome="FastCooking Concurrency Lab",
            cnpj="11.222.333/0001-44",
            telefone="11999990000",
            email="lab@fastcooking.test",
            cep="01001-000",
            status=True,
        )
        outro_restaurante = Restaurante(
            nome="Outro Tenant",
            cnpj="55.666.777/0001-88",
            telefone="11988880000",
            email="outro@fastcooking.test",
            cep="02002-000",
            status=True,
        )
        db.add_all([restaurante, outro_restaurante])
        db.flush()

        mesa_10 = Mesa(
            idRestaurante=restaurante.idRestaurante,
            numero=10,
            status="Indisponivel",
        )
        mesa_22 = Mesa(
            idRestaurante=restaurante.idRestaurante,
            numero=22,
            status="Indisponivel",
        )
        prato_1 = Cardapio(
            idRestaurante=restaurante.idRestaurante,
            nome="Picanha na Chapa",
            preco=89.90,
            categoria="Prato principal",
            status=True,
        )
        prato_2 = Cardapio(
            idRestaurante=restaurante.idRestaurante,
            nome="Salmão Grelhado",
            preco=74.50,
            categoria="Prato principal",
            status=True,
        )
        db.add_all([mesa_10, mesa_22, prato_1, prato_2])
        db.flush()

        cook = Usuario(
            idRestaurante=restaurante.idRestaurante,
            nome="Chef Cozinha",
            cpf="100.000.000-01",
            email="cook@fastcooking.test",
            senha="hashed_password",
            funcao="Cozinheiro",
            status=True,
        )

        waiters = []
        for idx in range(1, 7):
            w = Usuario(
                idRestaurante=restaurante.idRestaurante,
                nome=f"Garçom {idx}",
                cpf=f"200.000.000-0{idx}",
                email=f"waiter{idx}@fastcooking.test",
                senha="hashed_password",
                funcao="Garcom",
                status=True,
            )
            waiters.append(w)

        db.add_all([cook, *waiters])
        db.commit()

        ids = {
            "restaurant": restaurante.idRestaurante,
            "other_restaurant": outro_restaurante.idRestaurante,
            "mesa_10": mesa_10.idMesa,
            "mesa_22": mesa_22.idMesa,
            "prato_1": prato_1.idCardapio,
            "prato_2": prato_2.idCardapio,
            "cook": cook.idUsuario,
            "waiters": [w.idUsuario for w in waiters],
        }

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app_module.app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app_module.app)
    try:
        yield client, session_factory, ids
    finally:
        app_module.app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _waiter_token(waiter_id: uuid.UUID, restaurant_id: uuid.UUID) -> str:
    return security.criar_token(
        waiter_id,
        "Garcom",
        restaurant_id,
        shift_status="ON_SHIFT",
    )


def _cook_token(cook_id: uuid.UUID, restaurant_id: uuid.UUID) -> str:
    return security.criar_token(cook_id, "Cozinheiro", restaurant_id)


def _create_ready_item(
    client: TestClient,
    ids: dict,
    mesa_key: str = "mesa_10",
    prato_key: str = "prato_1",
    observacao: str = "Sem cebola",
) -> str:
    """Cria um pedido e avança o item no KDS até o status 'Pronto'."""
    w_token = _waiter_token(ids["waiters"][0], ids["restaurant"])
    c_token = _cook_token(ids["cook"], ids["restaurant"])

    order_res = client.post(
        "/pedidos",
        headers={"Authorization": f"Bearer {w_token}"},
        json={
            "idMesa": str(ids[mesa_key]),
            "itens": [
                {
                    "idCardapio": str(ids[prato_key]),
                    "quantidade": 1,
                    "observacao": observacao,
                }
            ],
        },
    )
    assert order_res.status_code == 201, order_res.text
    item_id = order_res.json()["itens"][0]["idItemPedido"]

    r1 = client.patch(
        f"/pedidos/itens/{item_id}/status",
        headers={"Authorization": f"Bearer {c_token}"},
        json={"status": "Em preparo"},
    )
    assert r1.status_code == 200

    r2 = client.patch(
        f"/pedidos/itens/{item_id}/status",
        headers={"Authorization": f"Bearer {c_token}"},
        json={"status": "Pronto"},
    )
    assert r2.status_code == 200
    return item_id


def test_concurrent_waiters_claiming_same_item_only_one_wins_and_others_get_409(
    delivery_env,
):
    """
    1. Teste de Concorrência Real (Race Condition):
    Dispara 6 requisições simultâneas (sincronizadas por threading.Barrier) de 6 garçons
    distintos tentando assumir o mesmo item pronto no mesmo milissegundo.
    Verifica que:
    - Exatamente 1 garçom vence com HTTP 200 OK.
    - Os outros 5 garçons recebem HTTP 409 Conflict com código 'ITEM_ALREADY_CLAIMED'.
    - Nenhum erro HTTP 500 ocorre.
    """
    client, session_factory, ids = delivery_env
    item_id = _create_ready_item(client, ids)

    waiter_ids = ids["waiters"]
    num_waiters = len(waiter_ids)
    barrier = threading.Barrier(num_waiters)

    def attempt_claim(waiter_id: uuid.UUID):
        token = _waiter_token(waiter_id, ids["restaurant"])
        with TestClient(app_module.app) as thread_client:
            barrier.wait(timeout=5.0)
            return waiter_id, thread_client.post(
                "/api/deliveries/claim",
                headers={"Authorization": f"Bearer {token}"},
                json={"itemId": item_id},
            )

    with ThreadPoolExecutor(max_workers=num_waiters) as pool:
        futures = [pool.submit(attempt_claim, wid) for wid in waiter_ids]
        results = [f.result() for f in futures]

    status_codes = [res.status_code for _, res in results]
    assert 500 not in status_codes, (
        f"Erro 500 detectado: {[r.text for _, r in results]}"
    )
    assert status_codes.count(200) == 1
    assert status_codes.count(409) == num_waiters - 1

    winner_id, winner_res = next((wid, r) for wid, r in results if r.status_code == 200)
    winner_body = winner_res.json()
    assert winner_body["itemId"] == item_id
    assert winner_body["claimedByWaiterId"] == str(winner_id)
    assert winner_body["status"] == DeliveryState.IN_DELIVERY.value
    assert winner_body["tableNumber"] == 10

    for _, conflict_res in (pair for pair in results if pair[1].status_code == 409):
        body = conflict_res.json()
        assert body["code"] == "ITEM_ALREADY_CLAIMED"

    # Verifica persistência ACID no banco de dados
    with session_factory() as db:
        entregas = (
            db.query(Entrega).filter(Entrega.idItemPedido == uuid.UUID(item_id)).all()
        )
        assert len(entregas) == 1
        assert entregas[0].idGarcom == winner_id
        assert entregas[0].status == DeliveryState.IN_DELIVERY.value


def test_busy_waiter_with_active_delivery_receives_422_unprocessable_entity(
    delivery_env,
):
    """
    2. Teste de Garçom Ocupado (Regra 1-para-1):
    Um garçom que já possui 1 entrega ativa tenta assumir um segundo item pronto
    e recebe HTTP 422 Unprocessable Entity (WAITER_ALREADY_HAS_ACTIVE_DELIVERY).
    """
    client, session_factory, ids = delivery_env
    item_1 = _create_ready_item(client, ids, mesa_key="mesa_10", prato_key="prato_1")
    item_2 = _create_ready_item(client, ids, mesa_key="mesa_22", prato_key="prato_2")

    waiter_1_id = ids["waiters"][0]
    w1_token = _waiter_token(waiter_1_id, ids["restaurant"])

    # Garçom 1 assume o primeiro item com sucesso (200 OK)
    first_claim = client.post(
        "/api/deliveries/claim",
        headers={"Authorization": f"Bearer {w1_token}"},
        json={"itemId": item_1},
    )
    assert first_claim.status_code == 200, first_claim.text

    # Garçom 1 tenta assumir o segundo item enquanto ainda está com o primeiro ativo -> 422
    second_claim = client.post(
        f"/api/items/{item_2}/claim",
        headers={"Authorization": f"Bearer {w1_token}"},
    )
    assert second_claim.status_code == 422, second_claim.text
    err_payload = second_claim.json()
    assert err_payload["code"] == "WAITER_ALREADY_HAS_ACTIVE_DELIVERY"

    # Confirma que o segundo item permanece disponível (WAITING_DELIVERY_PICKUP) para outro garçom livre
    with session_factory() as db:
        item_db = (
            db.query(ItemPedido)
            .filter(ItemPedido.idItemPedido == uuid.UUID(item_2))
            .one()
        )
        assert item_db.claimedByWaiterId is None
        assert item_db.deliveryStatus == DeliveryState.WAITING_DELIVERY_PICKUP.value


def test_claim_broadcasts_delivery_claimed_event_to_waiters_room_in_realtime(
    delivery_env,
):
    """
    3. Remoção em Tempo Real para os Demais Garçons:
    Imediatamente após o commit do claim, o evento 'delivery:claimed' é emitido para
    a sala 'room:waiters:active' contendo { itemId, tableNumber, claimedByWaiterId, timestamp }.
    """
    client, _, ids = delivery_env
    item_id = _create_ready_item(client, ids, mesa_key="mesa_10")

    w1_id, w2_id, w3_id = ids["waiters"][0], ids["waiters"][1], ids["waiters"][2]
    tokens = [
        _waiter_token(w1_id, ids["restaurant"]),
        _waiter_token(w2_id, ids["restaurant"]),
        _waiter_token(w3_id, ids["restaurant"]),
    ]

    with ExitStack() as stack:
        sockets = []
        for token in tokens:
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
            sockets.append(ws)

        # Garçom 2 assume a entrega
        claim_res = client.post(
            "/api/deliveries/claim",
            headers={"Authorization": f"Bearer {tokens[1]}"},
            json={"itemId": item_id},
        )
        assert claim_res.status_code == 200

        # Todos os garçons conectados na sala recebem o evento 'delivery:claimed'
        for ws in sockets:
            msg = ws.receive_json()
            validated = DeliveryClaimedWsPayloadSchema(**msg)
            assert validated.event == "delivery:claimed"
            assert validated.itemId == item_id
            assert validated.tableNumber == 10
            assert validated.claimedByWaiterId == str(w2_id)
            assert validated.timestamp


def test_fifo_queue_and_reactive_dispatch_on_delivery_completion(delivery_env):
    """
    4. Teste de Fila FIFO e Despacho Reativo:
    - Garçom 1 está ocupado com a Entrega Inicial.
    - Dois novos itens ficam prontos em sequência (Item FIFO 1 mais antigo, Item FIFO 2 mais recente)
      e aguardam na fila com status WAITING_DELIVERY_PICKUP.
    - Ao chamar POST /api/deliveries/:id/complete:
      1. A entrega atual passa para DELIVERED (e o ItemPedido para 'Entregue').
      2. O garçom volta ao estado livre (0 entregas pendentes).
      3. O sistema verifica atomicamente a fila FIFO e oferta o Item FIFO 1 (mais antigo)
         tanto no payload de resposta quanto via WebSocket para a sala de garçons.
      4. O garçom recém-liberado consegue assumir imediatamente o Item FIFO 1.
    """
    client, session_factory, ids = delivery_env
    w1_id = ids["waiters"][0]
    w1_token = _waiter_token(w1_id, ids["restaurant"])

    # 1. Cria item inicial e Garçom 1 assume
    active_item_id = _create_ready_item(
        client, ids, mesa_key="mesa_10", prato_key="prato_1"
    )
    claim_res = client.post(
        "/api/deliveries/claim",
        headers={"Authorization": f"Bearer {w1_token}"},
        json={"itemId": active_item_id},
    )
    assert claim_res.status_code == 200
    active_delivery_id = claim_res.json()["deliveryId"]

    # 2. Dois novos itens ficam prontos enquanto o garçom está ocupado (Backlog FIFO)
    fifo_item_oldest = _create_ready_item(
        client,
        ids,
        mesa_key="mesa_10",
        prato_key="prato_2",
        observacao="Primeiro da fila FIFO",
    )
    fifo_item_newest = _create_ready_item(
        client,
        ids,
        mesa_key="mesa_22",
        prato_key="prato_1",
        observacao="Segundo da fila FIFO",
    )

    # Garante timestamps determinísticos para testar a ordenação estrita FIFO
    base_time = datetime.now(UTC)
    with session_factory() as db:
        it_old = (
            db.query(ItemPedido)
            .filter_by(idItemPedido=uuid.UUID(fifo_item_oldest))
            .one()
        )
        it_new = (
            db.query(ItemPedido)
            .filter_by(idItemPedido=uuid.UUID(fifo_item_newest))
            .one()
        )
        it_old.dataCriacao = base_time - timedelta(minutes=5)
        it_new.dataCriacao = base_time - timedelta(minutes=1)
        db.commit()

    # Verifica que a fila de espera contém os 2 itens em ordem FIFO
    queue_res = client.get(
        "/api/deliveries/queue",
        headers={"Authorization": f"Bearer {w1_token}"},
    )
    assert queue_res.status_code == 200
    queue_items = queue_res.json()
    assert [q["itemId"] for q in queue_items] == [fifo_item_oldest, fifo_item_newest]
    assert all(
        q["status"] == DeliveryState.WAITING_DELIVERY_PICKUP.value for q in queue_items
    )

    # 3. Garçom 1 conecta ao WebSocket e conclui sua entrega atual
    with client.websocket_connect(
        "/ws/waiters",
        headers={
            "Authorization": f"Bearer {w1_token}",
            "X-Shift-Status": "ON_SHIFT",
        },
    ) as ws_waiter:
        assert ws_waiter.receive_json()["type"] == "room.joined"

        complete_res = client.post(
            f"/api/deliveries/{active_delivery_id}/complete",
            headers={"Authorization": f"Bearer {w1_token}"},
        )
        assert complete_res.status_code == 200, complete_res.text
        completed_data = complete_res.json()

        assert completed_data["deliveryId"] == active_delivery_id
        assert completed_data["itemId"] == active_item_id
        assert completed_data["status"] == DeliveryState.DELIVERED.value
        assert completed_data["itemStatus"] == "Entregue"

        # Valida que o próximo item ofertado é o mais antigo da fila FIFO
        assert completed_data["nextQueuedItem"] is not None
        assert completed_data["nextQueuedItem"]["itemId"] == fifo_item_oldest
        assert (
            completed_data["nextQueuedItem"]["status"]
            == DeliveryState.WAITING_DELIVERY_PICKUP.value
        )

        # Valida que o WebSocket disparou reativamente a oferta do item mais antigo da fila
        dispatched_ws = ws_waiter.receive_json()
        assert dispatched_ws["event"] == "kds:item_ready"
        assert dispatched_ws["items"][0]["id"] == fifo_item_oldest
        assert dispatched_ws["notes"] == "Primeiro da fila FIFO"

    # 4. Agora livre, Garçom 1 consegue assumir o item ofertado da fila FIFO
    next_claim = client.post(
        "/api/deliveries/claim",
        headers={"Authorization": f"Bearer {w1_token}"},
        json={"itemId": fifo_item_oldest},
    )
    assert next_claim.status_code == 200, next_claim.text
    assert next_claim.json()["itemId"] == fifo_item_oldest


def test_claim_returns_404_when_item_does_not_exist_or_is_not_ready(delivery_env):
    """
    5. Teste de Semântica HTTP 404:
    Retorna 404 Not Found quando o item não existe ou ainda está 'Pendente'/'Em preparo'.
    """
    client, _, ids = delivery_env
    w_token = _waiter_token(ids["waiters"][0], ids["restaurant"])

    # Caso A: Item inexistente
    non_existent_res = client.post(
        "/api/deliveries/claim",
        headers={"Authorization": f"Bearer {w_token}"},
        json={"itemId": str(uuid.uuid4())},
    )
    assert non_existent_res.status_code == 404
    assert non_existent_res.json()["code"] == "ITEM_NOT_FOUND"

    # Caso B: Item recém-criado com status 'Pendente' (ainda não está 'Pronto')
    order_res = client.post(
        "/pedidos",
        headers={"Authorization": f"Bearer {w_token}"},
        json={
            "idMesa": str(ids["mesa_10"]),
            "itens": [{"idCardapio": str(ids["prato_1"]), "quantidade": 1}],
        },
    )
    pending_item_id = order_res.json()["itens"][0]["idItemPedido"]

    not_ready_res = client.post(
        "/api/deliveries/claim",
        headers={"Authorization": f"Bearer {w_token}"},
        json={"itemId": pending_item_id},
    )
    assert not_ready_res.status_code == 404
    assert not_ready_res.json()["code"] == "ITEM_NOT_READY"
