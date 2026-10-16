import uuid
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
def cenario_mesa_garcom(db_session):
    restaurante = Restaurante.create(
        db=db_session,
        nome="Restaurante Teste Chamados",
        cnpj="55.666.777/0001-88",
        telefone="(11) 96666-5555",
        email="chamados@restaurante.com",
        cep="01001-000",
        status=True,
    )

    garcom = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Garçom Salão",
        cpf="555.666.777-88",
        email="garcom_salao@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Garcom",
    )

    mesa = Mesa.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        numero=7,
        status="Ocupada",
    )

    prato = Cardapio.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Prato Comanda",
        preco=30.0,
        categoria="Lanche",
    )

    pedido = Pedido.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        idMesa=mesa.idMesa,
        status="Aberto",
    )

    item = ItemPedido.create(
        db=db_session,
        idPedido=pedido.idPedido,
        idCardapio=prato.idCardapio,
        quantidade=2,
        precoUnitario=30.0,
    )

    return {
        "restaurante": restaurante,
        "garcom": garcom,
        "mesa": mesa,
        "prato": prato,
        "pedido": pedido,
        "item": item,
    }


def test_fluxo_chamar_e_atender_garcom(client, cenario_mesa_garcom):
    mesa = cenario_mesa_garcom["mesa"]
    garcom = cenario_mesa_garcom["garcom"]
    restaurante = cenario_mesa_garcom["restaurante"]
    token = criar_token(garcom.idUsuario, garcom.funcao, garcom.idRestaurante)

    # 1. Cliente na mesa clica para chamar garçom
    res_chamar = client.post(f"/mesas/{mesa.idMesa}/chamar-garcom")
    assert res_chamar.status_code == 200
    assert "chamado" in res_chamar.json()
    assert res_chamar.json()["chamado"]["numero"] == 7

    # 2. Garçom consulta chamados ativos do restaurante
    res_ativos = client.get(
        f"/mesas/chamados/ativos?idRestaurante={restaurante.idRestaurante}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_ativos.status_code == 200
    chamados = res_ativos.json()
    assert len(chamados) >= 1
    assert any(c["idMesa"] == str(mesa.idMesa) for c in chamados)

    # 3. Garçom atende o chamado da mesa
    res_atender = client.post(
        f"/mesas/{mesa.idMesa}/atender-chamado",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_atender.status_code == 200

    # 4. Verifica que o chamado não está mais ativo
    res_ativos2 = client.get(
        f"/mesas/chamados/ativos?idRestaurante={restaurante.idRestaurante}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_ativos2.status_code == 200
    assert not any(c["idMesa"] == str(mesa.idMesa) for c in res_ativos2.json())


def test_obter_pedido_ativo_mesa(client, cenario_mesa_garcom):
    mesa = cenario_mesa_garcom["mesa"]
    res = client.get(f"/mesas/{mesa.idMesa}/pedido-ativo")
    assert res.status_code == 200
    dados = res.json()
    assert dados["pedido"]["idMesa"] == str(mesa.idMesa)
    assert len(dados["itens"]) == 1
    assert dados["itens"][0]["quantidade"] == 2
