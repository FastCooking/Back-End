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
def cenario_pedido(db_session):
    restaurante = Restaurante.create(
        db=db_session,
        nome="Restaurante Teste Cancelamento",
        cnpj="44.555.666/0001-77",
        telefone="(11) 97777-6666",
        email="cancela@restaurante.com",
        cep="01001-000",
        status=True,
    )

    garcom = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Garçom Teste",
        cpf="222.333.444-55",
        email="garcom_cancela@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Garcom",
    )

    cozinheiro = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Cozinheiro Teste",
        cpf="333.444.555-66",
        email="cozinha_cancela@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Cozinheiro",
    )

    mesa = Mesa.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        numero=12,
        status="Ocupada",
    )

    prato = Cardapio.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Prato Cancelável",
        descricao="Prato de teste",
        preco=45.0,
        categoria="Prato Principal",
    )

    pedido = Pedido.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        idMesa=mesa.idMesa,
        idGarcom=garcom.idUsuario,
        status="Aberto",
    )

    item = ItemPedido.create(
        db=db_session,
        idPedido=pedido.idPedido,
        idCardapio=prato.idCardapio,
        quantidade=1,
        precoUnitario=45.0,
        status="Pendente",
    )

    return {
        "restaurante": restaurante,
        "garcom": garcom,
        "cozinheiro": cozinheiro,
        "mesa": mesa,
        "prato": prato,
        "pedido": pedido,
        "item": item,
    }


def test_garcom_cancela_item_pendente_com_sucesso(client, cenario_pedido, db_session):
    garcom = cenario_pedido["garcom"]
    item = cenario_pedido["item"]
    token = criar_token(garcom.idUsuario, garcom.funcao, garcom.idRestaurante)

    response = client.patch(
        f"/pedidos/itens/{item.idItemPedido}/cancelar",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    dados = response.json()
    assert dados["item"]["status"] == "Cancelado"

    # Verifica no banco de dados
    db_session.refresh(item)
    assert item.status == "Cancelado"


def test_garcom_nao_pode_cancelar_item_em_preparo(client, cenario_pedido, db_session):
    garcom = cenario_pedido["garcom"]
    item = cenario_pedido["item"]
    item.status = "Em preparo"
    db_session.commit()

    token = criar_token(garcom.idUsuario, garcom.funcao, garcom.idRestaurante)

    response = client.patch(
        f"/pedidos/itens/{item.idItemPedido}/cancelar",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert "preparo já foi iniciado" in response.json()["detail"]


def test_garcom_nao_pode_cancelar_item_ja_cancelado(client, cenario_pedido, db_session):
    garcom = cenario_pedido["garcom"]
    item = cenario_pedido["item"]
    item.status = "Cancelado"
    db_session.commit()

    token = criar_token(garcom.idUsuario, garcom.funcao, garcom.idRestaurante)

    response = client.patch(
        f"/pedidos/itens/{item.idItemPedido}/cancelar",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert "já está cancelado" in response.json()["detail"]


def test_cozinheiro_bloqueado_de_cancelar_item(client, cenario_pedido):
    cozinheiro = cenario_pedido["cozinheiro"]
    item = cenario_pedido["item"]
    token = criar_token(cozinheiro.idUsuario, cozinheiro.funcao, cozinheiro.idRestaurante)

    response = client.patch(
        f"/pedidos/itens/{item.idItemPedido}/cancelar",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
