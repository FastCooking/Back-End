import pytest
from src.core.security import criar_token
from src.models.Cardapio import Cardapio
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.services.UsuarioService import hash_senha


@pytest.fixture
def cenario_novas_regras(db_session):
    restaurante = Restaurante.create(
        db=db_session,
        nome="Restaurante Novas Regras",
        cnpj="99.888.777/0001-66",
        telefone="(11) 98888-7777",
        email="novasregras@fastcooking.com.br",
        cep="01001-000",
        status=True,
    )

    garcom = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Garçom Roberto",
        cpf="111.222.333-44",
        email="roberto@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Garcom",
    )

    gerente = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Gerente Maria",
        cpf="555.666.777-88",
        email="maria@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Gerente",
    )

    cozinheiro = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Cozinheiro Carlos",
        cpf="999.888.777-66",
        email="carlos@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Cozinheiro",
    )

    mesa = Mesa.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        numero=5,
        status="Ocupada",
    )

    item1 = Cardapio.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Hambúrguer Artesanal",
        preco=30.0,
        categoria="Lanche",
    )

    item2 = Cardapio.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Suco Natural",
        preco=10.0,
        categoria="Bebida",
    )

    pedido = Pedido.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        idMesa=mesa.idMesa,
        idGarcom=garcom.idUsuario,
        status="Aberto",
    )

    item_ped1 = ItemPedido.create(
        db=db_session,
        idPedido=pedido.idPedido,
        idCardapio=item1.idCardapio,
        quantidade=2,
        precoUnitario=30.0,
        categoria=item1.categoria,
        status="Pendente",
    )

    item_ped2 = ItemPedido.create(
        db=db_session,
        idPedido=pedido.idPedido,
        idCardapio=item2.idCardapio,
        quantidade=1,
        precoUnitario=10.0,
        categoria=item2.categoria,
        status="Pendente",
    )

    token_garcom = criar_token(garcom.idUsuario, "Garcom", restaurante.idRestaurante)
    token_gerente = criar_token(gerente.idUsuario, "Gerente", restaurante.idRestaurante)
    token_cozinha = criar_token(cozinheiro.idUsuario, "Cozinheiro", restaurante.idRestaurante)

    return {
        "restaurante": restaurante,
        "garcom": garcom,
        "gerente": gerente,
        "cozinheiro": cozinheiro,
        "mesa": mesa,
        "item1": item1,
        "item2": item2,
        "pedido": pedido,
        "item_ped1": item_ped1,
        "item_ped2": item_ped2,
        "headers_garcom": {"Authorization": f"Bearer {token_garcom}"},
        "headers_gerente": {"Authorization": f"Bearer {token_gerente}"},
        "headers_cozinha": {"Authorization": f"Bearer {token_cozinha}"},
    }


def test_alterar_quantidade_item_pendente(client, cenario_novas_regras):
    headers = cenario_novas_regras["headers_garcom"]
    item_id = str(cenario_novas_regras["item_ped1"].idItemPedido)

    # 1. Altera quantidade de 2 para 4
    resp = client.patch(
        f"/pedidos/itens/{item_id}/quantidade",
        json={"quantidade": 4},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["item"]["quantidade"] == 4

    # 2. Altera quantidade para 0 -> cancela item
    resp_zero = client.patch(
        f"/pedidos/itens/{item_id}/quantidade",
        json={"quantidade": 0},
        headers=headers,
    )
    assert resp_zero.status_code == 200
    assert resp_zero.json()["item"]["status"] == "Cancelado"


def test_bloqueio_alterar_quantidade_em_preparo(client, cenario_novas_regras):
    headers_cozinha = cenario_novas_regras["headers_cozinha"]
    headers_garcom = cenario_novas_regras["headers_garcom"]
    item_id = str(cenario_novas_regras["item_ped1"].idItemPedido)

    # Cozinha coloca em preparo
    client.patch(
        f"/pedidos/itens/{item_id}/status",
        json={"status": "Em preparo"},
        headers=headers_cozinha,
    )

    # Garçom tenta alterar quantidade de item em preparo -> 409
    resp = client.patch(
        f"/pedidos/itens/{item_id}/quantidade",
        json={"quantidade": 5},
        headers=headers_garcom,
    )
    assert resp.status_code == 409
    assert "Não é possível alterar a quantidade" in resp.json()["detail"]


def test_bloqueio_pagamento_com_itens_em_preparo(client, cenario_novas_regras):
    headers_cozinha = cenario_novas_regras["headers_cozinha"]
    headers_garcom = cenario_novas_regras["headers_garcom"]
    item_id = str(cenario_novas_regras["item_ped1"].idItemPedido)
    pedido_id = str(cenario_novas_regras["pedido"].idPedido)

    # Cozinha põe item em preparo
    client.patch(
        f"/pedidos/itens/{item_id}/status",
        json={"status": "Em preparo"},
        headers=headers_cozinha,
    )

    # Garçom tenta pagar e fechar mesa -> 409
    resp = client.post(
        f"/pedidos/{pedido_id}/pagamento",
        json={"formaPagamento": "PIX", "valor": 70.0},
        headers=headers_garcom,
    )
    assert resp.status_code == 409
    assert "Não é possível fechar a mesa com itens em preparo" in resp.json()["detail"]


def test_pagamentos_multiplos_e_fechamento(client, cenario_novas_regras):
    headers_garcom = cenario_novas_regras["headers_garcom"]
    headers_gerente = cenario_novas_regras["headers_gerente"]
    headers_cozinha = cenario_novas_regras["headers_cozinha"]
    pedido_id = str(cenario_novas_regras["pedido"].idPedido)
    item1_id = str(cenario_novas_regras["item_ped1"].idItemPedido)

    # Cozinha avança item1 para Pronto
    client.patch(f"/pedidos/itens/{item1_id}/status", json={"status": "Em preparo"}, headers=headers_cozinha)
    client.patch(f"/pedidos/itens/{item1_id}/status", json={"status": "Pronto"}, headers=headers_cozinha)
    # Garçom assume e entrega item1
    client.post(f"/pedidos/itens/{item1_id}/claim", headers=headers_garcom)
    client.post(f"/pedidos/entregas/{item1_id}/complete", headers=headers_garcom)

    # Total atual: item1 (2 x 30 = 60) + item2 pendente (1 x 10 = 10) = 70
    # 1º pagamento parcial: R$ 30 via PIX
    resp1 = client.post(
        f"/pedidos/{pedido_id}/pagamento",
        json={"formaPagamento": "PIX", "valor": 30.0},
        headers=headers_garcom,
    )
    assert resp1.status_code == 201
    assert resp1.json()["pedidoEncerrado"] is False
    assert resp1.json()["totalPago"] == 30.0
    # Notice: item2 was pendente, so it was cancelled on payment attempt, total becomes 60!
    # Saldo restante = 60 - 30 = 30
    assert resp1.json()["totalPedido"] == 60.0
    assert resp1.json()["saldoRestante"] == 30.0

    # 2º pagamento complementar: R$ 30 via Cartão de Crédito pelo gerente
    resp2 = client.post(
        f"/pedidos/{pedido_id}/pagamento",
        json={"formaPagamento": "Cartão de Crédito", "valor": 30.0},
        headers=headers_gerente,
    )
    assert resp2.status_code == 201
    assert resp2.json()["pedidoEncerrado"] is True
    assert resp2.json()["saldoRestante"] == 0.0

    # Consulta pedido via GET /pedidos/{idPedido}
    resp_get = client.get(f"/pedidos/{pedido_id}")
    assert resp_get.status_code == 200
    data_ped = resp_get.json()
    assert data_ped["pedido"]["status"] == "Fechado"
    assert len(data_ped["pagamentos"]) == 2
    assert data_ped["totalPago"] == 60.0
    assert data_ped["saldoRestante"] == 0.0

    # Consulta no histórico de pedidos (GET /pedidos?tipo=historico)
    resp_hist = client.get("/pedidos?tipo=historico", headers=headers_gerente)
    assert resp_hist.status_code == 200
    pedidos_hist = resp_hist.json()
    pedido_fechado = next((p for p in pedidos_hist if p["idPedido"] == pedido_id), None)
    assert pedido_fechado is not None
    assert pedido_fechado["nomeUsuarioFechamento"] == "Gerente Maria"
    assert pedido_fechado["funcaoUsuarioFechamento"] == "Gerente"
