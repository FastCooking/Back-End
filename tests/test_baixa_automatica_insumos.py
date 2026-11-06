import uuid

import pytest

from src.core.security import criar_token
from src.models.Cardapio import Cardapio
from src.models.Estoque import Estoque
from src.models.FichaTecnica import FichaTecnica
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.services.UsuarioService import hash_senha


@pytest.fixture
def cenario_estoque_pedido(db_session):
    restaurante = Restaurante.create(
        db=db_session,
        nome="Restaurante Baixa Automática",
        cnpj="51.234.567/0001-81",
        telefone="(11) 95555-1111",
        email="baixa.automatica@teste.com",
        cep="01001-000",
        status=True,
    )
    mesa = Mesa.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        numero=51,
    )
    cardapio = Cardapio.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Prato com insumo",
        preco=25,
        categoria="Prato Principal",
    )
    insumo = Estoque.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Ingrediente",
        unidadeMedida="UN",
        quantidadeEstoque=5,
    )
    FichaTecnica.create(
        db=db_session,
        idCardapio=cardapio.idCardapio,
        idEstoque=insumo.idEstoque,
        quantidadeNecessaria=2,
    )
    cozinheiro = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Cozinheiro",
        cpf="111.444.777-88",
        email="cozinheiro.baixa@teste.com",
        senha=hash_senha("senha123"),
        funcao="Cozinheiro",
    )
    garcom = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Garçom",
        cpf="111.444.777-89",
        email="garcom.baixa@teste.com",
        senha=hash_senha("senha123"),
        funcao="Garcom",
    )

    return {
        "restaurante": restaurante,
        "mesa": mesa,
        "cardapio": cardapio,
        "insumo": insumo,
        "cozinheiro": cozinheiro,
        "garcom": garcom,
        "headers_cozinha": {
            "Authorization": (
                f"Bearer {criar_token(cozinheiro.idUsuario, cozinheiro.funcao, restaurante.idRestaurante)}"
            )
        },
    }


def _criar_pedido(client, cenario, quantidade=1):
    return client.post(
        f"/pedidos/mesas/{cenario['mesa'].idMesa}/itens",
        json={
            "itens": [
                {
                    "idCardapio": str(cenario["cardapio"].idCardapio),
                    "quantidade": quantidade,
                }
            ]
        },
    )


def test_criacao_valida_estoque_antes_de_abrir_pedido(
    client, db_session, cenario_estoque_pedido
):
    cenario = cenario_estoque_pedido
    cenario["insumo"].quantidadeEstoque = 1
    db_session.commit()

    response = _criar_pedido(client, cenario)

    assert response.status_code == 400
    assert "indisponível" in response.json()["detail"]
    assert db_session.query(Pedido).count() == 0
    assert cenario["mesa"].status == "Disponivel"
    assert float(cenario["insumo"].quantidadeEstoque) == 1


def test_baixa_ocorre_apenas_ao_iniciar_preparo_e_indisponibiliza_cardapio(
    client, db_session, cenario_estoque_pedido
):
    cenario = cenario_estoque_pedido
    response = _criar_pedido(client, cenario, quantidade=2)

    assert response.status_code == 201
    item_id = uuid.UUID(response.json()["itens"][0]["idItemPedido"])
    assert float(cenario["insumo"].quantidadeEstoque) == 5

    prep = client.patch(
        f"/pedidos/itens/{item_id}/status",
        json={"status": "Em preparo"},
        headers=cenario["headers_cozinha"],
    )

    assert prep.status_code == 200
    db_session.refresh(cenario["insumo"])
    db_session.refresh(cenario["cardapio"])
    item = db_session.query(ItemPedido).filter_by(idItemPedido=item_id).one()
    assert item.status == "Em preparo"
    assert float(cenario["insumo"].quantidadeEstoque) == 1
    assert cenario["cardapio"].status is False

    ready = client.patch(
        f"/pedidos/itens/{item_id}/status",
        json={"status": "Pronto"},
        headers=cenario["headers_cozinha"],
    )
    assert ready.status_code == 200
    db_session.refresh(cenario["insumo"])
    assert float(cenario["insumo"].quantidadeEstoque) == 1

    unavailable_order = _criar_pedido(client, cenario)
    assert unavailable_order.status_code == 400
    assert "indisponível" in unavailable_order.json()["detail"]


def test_adicao_a_pedido_existente_tambem_valida_estoque(
    client, db_session, cenario_estoque_pedido
):
    cenario = cenario_estoque_pedido
    created = _criar_pedido(client, cenario)
    pedido_id = created.json()["comanda"]["idPedido"]
    cenario["insumo"].quantidadeEstoque = 1
    db_session.commit()

    response = client.post(
        f"/pedidos/{pedido_id}/itens",
        json=[
            {
                "idCardapio": str(cenario["cardapio"].idCardapio),
                "quantidade": 1,
            }
        ],
    )

    assert response.status_code == 400
    assert "indisponível" in response.json()["detail"]
    assert db_session.query(ItemPedido).count() == 1
    assert float(cenario["insumo"].quantidadeEstoque) == 1


def test_preparo_sem_saldo_suficiente_nao_muda_status_nem_estoque(
    client, db_session, cenario_estoque_pedido
):
    cenario = cenario_estoque_pedido
    response = _criar_pedido(client, cenario)
    item_id = uuid.UUID(response.json()["itens"][0]["idItemPedido"])
    cenario["insumo"].quantidadeEstoque = 1
    db_session.commit()

    prep = client.patch(
        f"/pedidos/itens/{item_id}/status",
        json={"status": "Em preparo"},
        headers=cenario["headers_cozinha"],
    )

    assert prep.status_code == 400
    db_session.refresh(cenario["insumo"])
    item = db_session.query(ItemPedido).filter_by(idItemPedido=item_id).one()
    assert item.status == "Pendente"
    assert float(cenario["insumo"].quantidadeEstoque) == 1


@pytest.mark.parametrize("item_status", ["Em preparo", "Pronto", "Entregue"])
def test_nao_cancela_item_com_preparo_iniciado(
    client, db_session, cenario_estoque_pedido, item_status
):
    cenario = cenario_estoque_pedido
    pedido = Pedido.create(
        db=db_session,
        idRestaurante=cenario["restaurante"].idRestaurante,
        idMesa=cenario["mesa"].idMesa,
        status="Aberto",
    )
    item = ItemPedido.create(
        db=db_session,
        idPedido=pedido.idPedido,
        idCardapio=cenario["cardapio"].idCardapio,
        quantidade=1,
        precoUnitario=25,
        status=item_status,
    )

    response = client.patch(
        f"/pedidos/itens/{item.idItemPedido}/cancelar",
        headers={
            "Authorization": (
                f"Bearer {criar_token(cenario['garcom'].idUsuario, cenario['garcom'].funcao, cenario['restaurante'].idRestaurante)}"
            )
        },
    )

    assert response.status_code == 409
    assert "preparo já foi iniciado" in response.json()["detail"]
