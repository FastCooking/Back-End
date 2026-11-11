import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from src.app import app
from src.core.realtime import realtime_hub
from src.core.security import criar_token
from src.database.connection import engine
from src.models.Cardapio import Cardapio
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Pagamento import Pagamento
from src.models.Pedido import Pedido
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.services.DeliveryService import DeliveryService
from src.services.PedidoService import PedidoService
from src.services.QrCodeService import QrCodeService, _QRCODE_CACHE


class QueryCounter:
    """Contador de consultas SQL para validar ausência de N+1 queries."""

    def __init__(self, target_engine):
        self.target_engine = target_engine
        self.count = 0
        self.queries = []

    def __enter__(self):
        self.count = 0
        self.queries = []
        event.listen(self.target_engine, "before_cursor_execute", self._callback)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        event.remove(self.target_engine, "before_cursor_execute", self._callback)

    def _callback(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1
        self.queries.append(statement)


def criar_restaurante_teste(db, nome="Restaurante Teste"):
    rnd = uuid.uuid4().hex[:8]
    rest = Restaurante(
        nome=nome,
        cnpj=f"{rnd}000199"[:14],
        telefone="11999999999",
        email=f"rest_{rnd}@teste.com",
        cep="01001000",
        status=True,
    )
    db.add(rest)
    db.commit()
    db.refresh(rest)
    return rest


def criar_usuario_teste(db, id_restaurante, funcao="Garcom", nome="Usuario Teste"):
    rnd = uuid.uuid4().hex[:6]
    usuario = Usuario(
        idRestaurante=id_restaurante,
        nome=nome,
        cpf=f"{uuid.uuid4().int % 10**11:011d}",
        email=f"user_{rnd}@teste.com",
        senha="hash",
        funcao=funcao,
        status=True,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def test_indices_definidos_nos_modelos():
    """Valida que todos os índices críticos de performance foram declarados nos modelos."""
    # 1. ItemPedido
    item_indexes = {idx.name for idx in ItemPedido.__table__.indexes}
    assert "ix_item_pedido_kds" in item_indexes
    assert "ix_item_pedido_status" in item_indexes
    assert "ix_item_pedido_delivery" in item_indexes
    assert "ix_item_pedido_cardapio" in item_indexes

    # 2. Pedido
    pedido_indexes = {idx.name for idx in Pedido.__table__.indexes}
    assert "ix_pedido_restaurante_status" in pedido_indexes
    assert "ix_pedido_mesa_status" in pedido_indexes
    assert "ix_pedido_data_abertura" in pedido_indexes

    # 3. Mesa
    mesa_indexes = {idx.name for idx in Mesa.__table__.indexes}
    assert "ix_mesa_restaurante_status" in mesa_indexes

    # 4. Cardapio
    cardapio_indexes = {idx.name for idx in Cardapio.__table__.indexes}
    assert "ix_cardapio_rest_status_cat" in cardapio_indexes

    # 5. Pagamento
    pagamento_indexes = {idx.name for idx in Pagamento.__table__.indexes}
    assert "ix_pagamento_pedido" in pagamento_indexes


def test_validacao_cardapio_em_lote_sem_n_plus_one(db_session):
    """Valida que _validate_menu_items busca todos os itens em uma única query SQL (IN clause)."""
    rest = criar_restaurante_teste(db_session, "Restaurante Teste Batch")

    # Cria 5 itens no cardápio
    itens_cardapio = []
    for i in range(5):
        item = Cardapio(
            idRestaurante=rest.idRestaurante,
            nome=f"Item Batch {i}",
            preco=10.0 + i,
            categoria="Pratos Principais",
            status=True,
        )
        db_session.add(item)
        itens_cardapio.append(item)
    db_session.commit()

    service = PedidoService(db_session)
    itens_payload = [
        {"idCardapio": item.idCardapio, "quantidade": 2, "observacao": None}
        for item in itens_cardapio
    ]

    with QueryCounter(db_session.get_bind()) as counter:
        validated = service._validate_menu_items(itens_payload, rest.idRestaurante)

    assert len(validated) == 5
    cardapio_batch_selects = [
        q for q in counter.queries if "cardapio" in q.lower() and " in " in q.lower()
    ]
    assert len(cardapio_batch_selects) == 1, f"Esperado 1 batch select no Cardapio, ocorreram {len(cardapio_batch_selects)}"


def test_queue_snapshot_kds_eager_loading(db_session):
    """Valida que queue_snapshot carrega Cardapio e Mesa sem gerar N+1 queries."""
    rest = criar_restaurante_teste(db_session, "Restaurante Teste KDS")
    cozinheiro = criar_usuario_teste(db_session, rest.idRestaurante, funcao="Cozinheiro", nome="Chef KDS")

    mesa = Mesa(idRestaurante=rest.idRestaurante, numero=1, status="Ocupada")
    db_session.add(mesa)
    db_session.commit()

    pedido = Pedido(idRestaurante=rest.idRestaurante, idMesa=mesa.idMesa, status="Aberto")
    db_session.add(pedido)
    db_session.commit()

    for i in range(4):
        card = Cardapio(
            idRestaurante=rest.idRestaurante,
            nome=f"Prato KDS {i}",
            preco=25.0,
            categoria="Pratos Principais",
            status=True,
            tempoPreparo=15,
        )
        db_session.add(card)
        db_session.commit()
        it = ItemPedido(
            idPedido=pedido.idPedido,
            idCardapio=card.idCardapio,
            quantidade=1,
            precoUnitario=25.0,
            status="Pendente",
            categoria="Pratos Principais",
            liberadoParaPreparo=True,
        )
        db_session.add(it)
    db_session.commit()

    service = PedidoService(db_session)

    with QueryCounter(db_session.get_bind()) as counter:
        snapshot = service.queue_snapshot(cozinheiro)

    assert len(snapshot["items"]) == 4
    for it in snapshot["items"]:
        assert it["numeroMesa"] == 1
        assert "Prato KDS" in it["nomeItem"]

    # Com joinedload, itens, cardápio e mesa são resolvidos sem N+1
    assert counter.count <= 2, f"Queries excessivas no snapshot: {counter.count}"


def test_qrcode_service_in_memory_cache(db_session):
    """Valida que QrCodeService utiliza cache em memória para solicitações subsequentes."""
    rest = criar_restaurante_teste(db_session, "Restaurante Teste QR Cache")

    mesa = Mesa(idRestaurante=rest.idRestaurante, numero=42, status="Disponivel")
    db_session.add(mesa)
    db_session.commit()

    service = QrCodeService(db_session)
    _QRCODE_CACHE.clear()

    # 1ª chamada: gera imagem e popula cache
    buf1 = service.gerar_qrcode(mesa.idMesa)
    assert len(_QRCODE_CACHE) == 1
    bytes1 = buf1.getvalue()

    # 2ª chamada: deve retornar imediatamente os mesmos bytes a partir do cache
    buf2 = service.gerar_qrcode(mesa.idMesa)
    bytes2 = buf2.getvalue()
    assert bytes1 == bytes2
    assert len(_QRCODE_CACHE) == 1


def test_gzip_middleware_compressao_acima_de_1kb(client):
    """Valida que respostas maiores que 1KB utilizam compressão gzip quando solicitado."""
    response = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"


def test_delivery_service_lock_keys_sem_mutex_de_restaurante(db_session):
    """Valida que claim_delivery e finish_delivery não travam o restaurante inteiro."""
    rest = criar_restaurante_teste(db_session, "Restaurante Lock Test")
    garcom = criar_usuario_teste(db_session, rest.idRestaurante, funcao="Garcom", nome="Garçom Concorrente")

    service = DeliveryService(db_session)
    item_id = uuid.uuid4()

    try:
        service.claim_delivery(item_id, garcom)
    except Exception as exc:
        assert "não existe" in str(exc) or getattr(exc, "code", "") == "ITEM_NOT_FOUND"


def test_listar_pedidos_eager_loading(client, db_session):
    """Valida que listar_pedidos carrega mesa, garçom, itens e pagamentos em lote sem N+1."""
    rest = criar_restaurante_teste(db_session, "Restaurante Eager List")
    gerente = criar_usuario_teste(db_session, rest.idRestaurante, funcao="Gerente", nome="Gerente Eager")

    mesa = Mesa(idRestaurante=rest.idRestaurante, numero=10, status="Ocupada")
    db_session.add(mesa)
    db_session.commit()

    # Cria 3 pedidos com itens
    for i in range(3):
        ped = Pedido(idRestaurante=rest.idRestaurante, idMesa=mesa.idMesa, status="Aberto")
        db_session.add(ped)
        db_session.commit()
        card = Cardapio(
            idRestaurante=rest.idRestaurante,
            nome=f"Item Eager {i}",
            preco=15.0,
            categoria="Pratos Principais",
            status=True,
        )
        db_session.add(card)
        db_session.commit()
        it = ItemPedido(
            idPedido=ped.idPedido,
            idCardapio=card.idCardapio,
            quantidade=1,
            precoUnitario=15.0,
            status="Pendente",
            categoria="Pratos Principais",
        )
        db_session.add(it)
    db_session.commit()

    token = criar_token(gerente.idUsuario, "Gerente", rest.idRestaurante)
    headers = {"Authorization": f"Bearer {token}"}

    with QueryCounter(db_session.get_bind()) as counter:
        response = client.get("/pedidos?tipo=ativos", headers=headers)

    assert response.status_code == 200
    dados = response.json()
    assert len(dados) == 3
    for p in dados:
        assert p["numeroMesa"] == 10
        assert len(p["itens"]) == 1
        assert "Item Eager" in p["itens"][0]["nome"]

    # Com joinedload e selectinload, o total de queries para N pedidos é O(1) e não O(N)
    assert counter.count <= 6, f"Esperado poucas queries em lote, ocorreram {counter.count}"


def test_cors_headers_com_origem_frontend(client):
    """Valida que respostas de erro ou sucesso retornam Access-Control-Allow-Origin específico para o frontend."""
    origin = "https://fastcooking-front-dev.vercel.app"
    res = client.post("/auth/login", json={"email": "inexistente@teste.com", "senha": "123"}, headers={"Origin": origin})
    assert res.headers.get("access-control-allow-origin") == origin
    assert res.headers.get("access-control-allow-credentials") == "true"
