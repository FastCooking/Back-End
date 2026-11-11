import uuid

import pytest

from src.core.security import criar_token
from src.models.AuditoriaCancelamentoItem import AuditoriaCancelamentoItem
from src.models.Cardapio import Cardapio
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.services.UsuarioService import hash_senha


@pytest.fixture
def cenario_completo(db_session):
    restaurante = Restaurante.create(
        db=db_session,
        nome="Restaurante Teste Concorrencia",
        cnpj="99.888.777/0001-66",
        telefone="(11) 98888-7777",
        email="concorrencia@fastcooking.com",
        cep="01001-000",
        status=True,
    )

    garcom1 = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Garçom 1",
        cpf="101.202.303-44",
        email="garcom1@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Garcom",
    )

    garcom2 = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Garçom 2",
        cpf="505.606.707-88",
        email="garcom2@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Garcom",
    )

    cozinheiro = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Cozinheiro Chef",
        cpf="707.808.909-00",
        email="chef@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Cozinheiro",
    )

    mesa = Mesa.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        numero=42,
        status="Disponivel",
    )

    prato_principal = Cardapio.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Costela BBQ",
        descricao="Costela bovina com molho barbecue",
        preco=89.90,
        categoria="prato principal",
    )

    bebida = Cardapio.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Suco de Laranja",
        descricao="Suco natural 500ml",
        preco=12.00,
        categoria="bebida",
    )

    sobremesa = Cardapio.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Petit Gateau",
        descricao="Bolo de chocolate com sorvete",
        preco=25.00,
        categoria="sobremesa",
    )
    db_session.commit()

    return {
        "restaurante": restaurante,
        "garcom1": garcom1,
        "garcom2": garcom2,
        "cozinheiro": cozinheiro,
        "mesa": mesa,
        "prato": prato_principal,
        "bebida": bebida,
        "sobremesa": sobremesa,
    }


def test_adicao_concorrente_primeiro_item_rf01(client, cenario_completo, db_session):
    """
    TESTE DE CONCORRÊNCIA E RF01:
    Garante que:
    1. A adição do primeiro item (seja por garçom ou cliente) obrigatoriamente abre a mesa e cria a comanda (RF01).
    2. Adições simultâneas/subsequentes para a mesma mesa fazem append na mesma comanda (sem duplicação).
    3. O banco de dados possui constraint ativa (uq_pedido_ativo_por_mesa) que impede duas comandas abertas na mesma mesa.
    """
    mesa = cenario_completo["mesa"]
    prato = cenario_completo["prato"]
    bebida = cenario_completo["bebida"]
    garcom = cenario_completo["garcom1"]
    token_garcom = criar_token(garcom.idUsuario, garcom.funcao, garcom.idRestaurante)

    # 1. Requisição do cliente (Abre a comanda via RF01)
    res_cliente = client.post(
        f"/pedidos/mesas/{mesa.idMesa}/itens",
        json={
            "sessao_id": str(uuid.uuid4()),
            "itens": [{"idCardapio": str(prato.idCardapio), "quantidade": 1}],
        },
    )
    assert res_cliente.status_code == 201
    dados_cliente = res_cliente.json()
    assert dados_cliente["rf01Aplicado"] is True
    id_comanda_cliente = dados_cliente["comanda"]["idPedido"]

    # 2. Requisição concorrente/imediata do garçom na mesma mesa (Faz append na mesma comanda)
    res_garcom = client.post(
        f"/pedidos/mesas/{mesa.idMesa}/itens",
        headers={"Authorization": f"Bearer {token_garcom}"},
        json={
            "itens": [{"idCardapio": str(bebida.idCardapio), "quantidade": 2}],
        },
    )
    assert res_garcom.status_code == 200
    dados_garcom = res_garcom.json()
    assert dados_garcom["rf01Aplicado"] is False
    assert dados_garcom["comanda"]["idPedido"] == id_comanda_cliente

    # 3. Validação no banco: apenas 1 comanda ativa para a mesa
    pedidos_ativos = (
        db_session.query(Pedido)
        .filter(
            Pedido.idMesa == mesa.idMesa,
            Pedido.status.notin_(["Fechado", "Cancelado"]),
        )
        .all()
    )
    assert len(pedidos_ativos) == 1, "Deve existir exatamente UMA comanda ativa para a mesa!"
    assert len(pedidos_ativos[0].itens) == 2, "Ambos os itens devem estar na mesma comanda unificada!"

    # 4. Validação da constraint anti-race condition no banco de dados (uq_pedido_ativo_por_mesa)
    from sqlalchemy.exc import IntegrityError
    segundo_pedido = Pedido(
        idRestaurante=mesa.idRestaurante,
        idMesa=mesa.idMesa,
        status="Aberto",
    )
    db_session.add(segundo_pedido)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_adicao_universal_qualquer_garcom_pode_adicionar(client, cenario_completo, db_session):
    """
    CRITÉRIO DE ACEITE 1:
    O garçom pode adicionar itens à comanda de QUALQUER mesa a qualquer momento,
    mesmo que a mesa já tenha sido aberta pelo cliente ou por outro garçom.
    """
    mesa = cenario_completo["mesa"]
    prato = cenario_completo["prato"]
    bebida = cenario_completo["bebida"]
    garcom2 = cenario_completo["garcom2"]

    # 1. Cliente abre a mesa fazendo seu pedido via autoatendimento
    res_cliente = client.post(
        f"/pedidos/mesas/{mesa.idMesa}/itens",
        json={"itens": [{"idCardapio": str(prato.idCardapio), "quantidade": 1}]},
    )
    assert res_cliente.status_code == 201
    dados_cliente = res_cliente.json()
    assert dados_cliente["rf01Aplicado"] is True
    id_pedido = uuid.UUID(dados_cliente["comanda"]["idPedido"])

    # 2. Garçom 2 (qualquer garçom) adiciona bebida à mesma comanda
    token_garcom2 = criar_token(garcom2.idUsuario, garcom2.funcao, garcom2.idRestaurante)
    res_garcom2 = client.post(
        f"/pedidos/mesas/{mesa.idMesa}/itens",
        headers={"Authorization": f"Bearer {token_garcom2}"},
        json={"itens": [{"idCardapio": str(bebida.idCardapio), "quantidade": 3}]},
    )
    assert res_garcom2.status_code == 200
    dados_garcom = res_garcom2.json()
    assert dados_garcom["rf01Aplicado"] is False
    assert uuid.UUID(dados_garcom["comanda"]["idPedido"]) == id_pedido
    assert dados_garcom["origemAdicao"] == "GARCOM"

    # Verifica no banco que a comanda contém os 2 itens com suas respectivas origens
    itens = (
        db_session.query(ItemPedido)
        .filter(ItemPedido.idPedido == id_pedido)
        .order_by(ItemPedido.dataCriacao.asc())
        .all()
    )
    assert len(itens) == 2
    assert itens[0].origem == "CLIENTE"
    assert itens[1].origem == "GARCOM"


def test_remocao_em_tempo_real_e_kds(client, cenario_completo, db_session):
    """
    CRITÉRIO DE ACEITE 4:
    Remoção em Tempo Real: O garçom pode remover itens de uma comanda em aberto.
    O status vai para 'Cancelado', notifica o KDS e reavalia as pendências.
    """
    mesa = cenario_completo["mesa"]
    prato = cenario_completo["prato"]
    garcom = cenario_completo["garcom1"]
    token_garcom = criar_token(garcom.idUsuario, garcom.funcao, garcom.idRestaurante)

    # Cria pedido com 1 prato
    res_criacao = client.post(
        f"/pedidos/mesas/{mesa.idMesa}/itens",
        headers={"Authorization": f"Bearer {token_garcom}"},
        json={"itens": [{"idCardapio": str(prato.idCardapio), "quantidade": 1}]},
    )
    id_pedido = res_criacao.json()["comanda"]["idPedido"]
    id_item = res_criacao.json()["itensAdicionados"][0]["idItemPedido"]

    # Garçom remove o item
    res_remocao = client.request(
        "DELETE",
        f"/pedidos/{id_pedido}/itens/{id_item}",
        headers={"Authorization": f"Bearer {token_garcom}"},
        json={"motivo": "Cliente desistiu"},
    )
    assert res_remocao.status_code == 200
    dados_remocao = res_remocao.json()
    assert dados_remocao["statusAtual"] == "Cancelado"
    assert dados_remocao["statusAnterior"] == "Pendente"

    # Verifica persistência no banco
    item_db = db_session.query(ItemPedido).filter(ItemPedido.idItemPedido == uuid.UUID(id_item)).first()
    assert item_db.status == "Cancelado"
    auditoria = db_session.query(AuditoriaCancelamentoItem).filter_by(
        idItemPedido=item_db.idItemPedido
    ).one()
    assert auditoria.motivo == "Cliente desistiu"
    assert auditoria.origem == "GARCOM"


def test_rf08_zero_pendencias_e_assumir_entrega(client, cenario_completo, db_session):
    """
    CRITÉRIO DE ACEITE 5 (RF08):
    Dependência com 'assumir entrega', que exige 'zero pendências'.
    - Enquanto houver itens em 'Pendente', 'assumir-entrega' é BLOQUEADO (409 Conflict).
    - Quando o item é finalizado para 'Pronto' (ou os pendentes são cancelados),
      'assumir-entrega' é PERMITIDO (200 OK).
    - Se um novo item for adicionado posteriormente, 'zero pendências' é invalidado.
    """
    mesa = cenario_completo["mesa"]
    prato = cenario_completo["prato"]
    bebida = cenario_completo["bebida"]
    garcom = cenario_completo["garcom1"]
    token_garcom = criar_token(garcom.idUsuario, garcom.funcao, garcom.idRestaurante)

    # 1. Cria comanda com 2 itens
    res_pedido = client.post(
        f"/pedidos/mesas/{mesa.idMesa}/itens",
        headers={"Authorization": f"Bearer {token_garcom}"},
        json={
            "itens": [
                {"idCardapio": str(prato.idCardapio), "quantidade": 1},
                {"idCardapio": str(bebida.idCardapio), "quantidade": 1},
            ]
        },
    )
    id_pedido = res_pedido.json()["comanda"]["idPedido"]
    itens = res_pedido.json()["itensAdicionados"]
    id_item_prato = itens[0]["idItemPedido"]
    id_item_bebida = itens[1]["idItemPedido"]

    # 2. Tenta assumir entrega com itens Pendentes -> DEVE FALHAR (RF08)
    res_assumir_falha = client.post(
        f"/pedidos/{id_pedido}/assumir-entrega",
        headers={"Authorization": f"Bearer {token_garcom}"},
    )
    assert res_assumir_falha.status_code == 409
    assert "Violação RF08" in res_assumir_falha.json()["detail"]

    # 3. Cozinha avança o prato para Pronto e garçom cancela a bebida (mutação)
    item_prato_db = db_session.query(ItemPedido).filter(ItemPedido.idItemPedido == uuid.UUID(id_item_prato)).first()
    item_prato_db.status = "Pronto"
    db_session.commit()

    # Cancela o item de bebida via rota de remoção
    res_remocao = client.request(
        "DELETE",
        f"/pedidos/{id_pedido}/itens/{id_item_bebida}",
        json={"motivo": "Cliente desistiu da bebida"},
        headers={"Authorization": f"Bearer {token_garcom}"},
    )
    assert res_remocao.status_code == 200
    assert res_remocao.json()["comanda"]["possuiPendencias"] is False
    assert res_remocao.json()["comanda"]["elegivelAssumirEntrega"] is True

    # 4. Agora existe ZERO PENDÊNCIAS -> Assumir entrega deve ser APROVADO!
    res_assumir_sucesso = client.post(
        f"/pedidos/{id_pedido}/assumir-entrega",
        headers={"Authorization": f"Bearer {token_garcom}"},
    )
    assert res_assumir_sucesso.status_code == 200
    dados_entrega = res_assumir_sucesso.json()
    assert dados_entrega["comanda"]["status"] == "EmEntrega"
    assert dados_entrega["assumidoPor"] == str(garcom.idUsuario)

    # 5. Se o cliente adicionar mais um item na mesma comanda, RF08 reverte elegibilidade
    res_novo_item = client.post(
        f"/pedidos/mesas/{mesa.idMesa}/itens",
        json={"itens": [{"idCardapio": str(bebida.idCardapio), "quantidade": 1}]},
    )
    assert res_novo_item.status_code == 200
    assert res_novo_item.json()["comanda"]["possuiPendencias"] is True
    assert res_novo_item.json()["comanda"]["elegivelAssumirEntrega"] is False
    assert res_novo_item.json()["comanda"]["status"] == "Aberto"
