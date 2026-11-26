from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from src.core.security import criar_token
from src.database.connection import Base
from src.models.AuditoriaCancelamentoItem import AuditoriaCancelamentoItem
from src.models.Cardapio import Cardapio
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Restaurante import Restaurante
from src.models.Sessao import Sessao
from src.models.Usuario import Usuario
from src.services.PedidoService import PedidoService
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
    gerente = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Gerente Teste",
        cpf="444.555.666-77",
        email="gerente_cancela@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Gerente",
    )
    admin = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Administrador Teste",
        cpf="555.666.777-88",
        email="admin_cancela@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Adm",
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

    sessao = Sessao(idMesa=mesa.idMesa, status="Ativa")
    db_session.add(sessao)
    db_session.commit()
    db_session.refresh(sessao)

    pedido = Pedido.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        idMesa=mesa.idMesa,
        idGarcom=garcom.idUsuario,
        sessao_id=str(sessao.idSessao),
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
        "gerente": gerente,
        "admin": admin,
        "mesa": mesa,
        "sessao": sessao,
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
        json={"motivo": "Cliente solicitou"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    dados = response.json()
    assert dados["item"]["status"] == "Cancelado"

    # Verifica no banco de dados
    db_session.refresh(item)
    assert item.status == "Cancelado"
    auditoria = db_session.query(AuditoriaCancelamentoItem).one()
    assert auditoria.origem == "GARCOM"
    assert auditoria.idUsuario == garcom.idUsuario
    assert auditoria.motivo == "Cliente solicitou"
    assert auditoria.idMesa == cenario_pedido["mesa"].idMesa
    assert auditoria.sessao_id == str(cenario_pedido["sessao"].idSessao)
    assert auditoria.dataHora is not None


def test_cliente_cancela_sem_autenticacao_ou_motivo(client, cenario_pedido, db_session):
    item = cenario_pedido["item"]

    response = client.post(
        f"/pedidos/itens/{item.idItemPedido}/cancelamento-cliente"
    )

    assert response.status_code == 200
    assert response.json()["item"]["status"] == "Cancelado"
    auditoria = db_session.query(AuditoriaCancelamentoItem).one()
    assert auditoria.origem == "CLIENTE"
    assert auditoria.idUsuario is None
    assert auditoria.motivo is None
    assert auditoria.idMesa == cenario_pedido["mesa"].idMesa
    assert auditoria.sessao_id == str(cenario_pedido["sessao"].idSessao)


def test_cliente_nao_pode_escolher_origem_da_auditoria(client, cenario_pedido):
    item = cenario_pedido["item"]

    response = client.post(
        f"/pedidos/itens/{item.idItemPedido}/cancelamento-cliente",
        json={"origem": "GARCOM"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("user_key", "role", "origin"),
    [
        ("gerente", "Gerente", "GERENTE"),
        ("admin", "Adm", "ADM"),
    ],
)
def test_gerente_e_admin_cancelam_com_auditoria(
    client, cenario_pedido, db_session, user_key, role, origin
):
    usuario = cenario_pedido[user_key]
    item = cenario_pedido["item"]
    token = criar_token(usuario.idUsuario, role, usuario.idRestaurante)

    response = client.patch(
        f"/pedidos/itens/{item.idItemPedido}/cancelar",
        json={"motivo": "Solicitação do cliente"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    auditoria = db_session.query(AuditoriaCancelamentoItem).one()
    assert auditoria.origem == origin
    assert auditoria.idUsuario == usuario.idUsuario
    assert auditoria.motivo == "Solicitação do cliente"


def test_funcionario_nao_pode_cancelar_sem_justificativa(client, cenario_pedido):
    garcom = cenario_pedido["garcom"]
    item = cenario_pedido["item"]
    token = criar_token(garcom.idUsuario, garcom.funcao, garcom.idRestaurante)

    response = client.patch(
        f"/pedidos/itens/{item.idItemPedido}/cancelar",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code in (400, 422)


def test_funcionario_nao_pode_cancelar_com_justificativa_em_branco(
    client, cenario_pedido
):
    garcom = cenario_pedido["garcom"]
    item = cenario_pedido["item"]
    token = criar_token(garcom.idUsuario, garcom.funcao, garcom.idRestaurante)

    response = client.patch(
        f"/pedidos/itens/{item.idItemPedido}/cancelar",
        json={"motivo": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_garcom_nao_pode_cancelar_item_em_preparo(client, cenario_pedido, db_session):
    garcom = cenario_pedido["garcom"]
    item = cenario_pedido["item"]
    item.status = "Em preparo"
    db_session.commit()

    token = criar_token(garcom.idUsuario, garcom.funcao, garcom.idRestaurante)

    response = client.patch(
        f"/pedidos/itens/{item.idItemPedido}/cancelar",
        json={"motivo": "Cliente desistiu"},
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
        json={"motivo": "Cliente desistiu"},
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
        json={"motivo": "Solicitado pelo cliente"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize("item_status", ["Pronto", "Entregue"])
def test_item_pronto_ou_entregue_nao_pode_ser_cancelado(
    client, cenario_pedido, db_session, item_status
):
    garcom = cenario_pedido["garcom"]
    item = cenario_pedido["item"]
    item.status = item_status
    db_session.commit()
    token = criar_token(garcom.idUsuario, garcom.funcao, garcom.idRestaurante)

    response = client.patch(
        f"/pedidos/itens/{item.idItemPedido}/cancelar",
        json={"motivo": "Cliente desistiu"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert db_session.query(AuditoriaCancelamentoItem).count() == 0


def test_endpoint_de_funcionario_rejeita_jwt_invalido(client, cenario_pedido):
    response = client.patch(
        f"/pedidos/itens/{cenario_pedido['item'].idItemPedido}/cancelar",
        json={"motivo": "Cliente desistiu"},
        headers={"Authorization": "Bearer token-invalido"},
    )

    assert response.status_code == 401


def test_delete_exige_motivo_e_usa_auditoria_central(
    client, cenario_pedido, db_session
):
    pedido = cenario_pedido["pedido"]
    item = cenario_pedido["item"]
    garcom = cenario_pedido["garcom"]
    token = criar_token(garcom.idUsuario, garcom.funcao, garcom.idRestaurante)
    endpoint = f"/pedidos/{pedido.idPedido}/itens/{item.idItemPedido}"

    sem_motivo = client.request(
        "DELETE",
        endpoint,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sem_motivo.status_code in (400, 422)

    response = client.request(
        "DELETE",
        endpoint,
        json={"motivo": "Cliente desistiu"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    auditoria = db_session.query(AuditoriaCancelamentoItem).one()
    assert auditoria.origem == "GARCOM"
    assert auditoria.motivo == "Cliente desistiu"


def test_falha_ao_gravar_auditoria_desfaz_cancelamento(
    client, cenario_pedido, db_session, monkeypatch
):
    item = cenario_pedido["item"]
    original_add = db_session.add

    def falhar_ao_adicionar_auditoria(instance):
        if isinstance(instance, AuditoriaCancelamentoItem):
            raise SQLAlchemyError("falha simulada ao persistir auditoria")
        original_add(instance)

    monkeypatch.setattr(db_session, "add", falhar_ao_adicionar_auditoria)
    with pytest.raises(SQLAlchemyError, match="falha simulada"):
        client.post(
            f"/pedidos/itens/{item.idItemPedido}/cancelamento-cliente"
        )
    db_session.refresh(item)
    assert item.status == "Pendente"
    assert db_session.query(AuditoriaCancelamentoItem).count() == 0


def test_fechamento_e_bloqueado_com_item_pendente(client, cenario_pedido):
    garcom = cenario_pedido["garcom"]
    pedido = cenario_pedido["pedido"]
    token = criar_token(garcom.idUsuario, garcom.funcao, garcom.idRestaurante)

    response = client.post(
        f"/pedidos/{pedido.idPedido}/pagamento",
        json={"formaPagamento": "PIX"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert "itens pendentes" in response.json()["detail"]


def test_concorrencia_cancelamento_versus_inicio_de_preparo(tmp_path, cenario_pedido):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'rf11-concorrencia.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )

    @event.listens_for(engine, "connect")
    def configurar_sqlite(dbapi_connection, _connection_record):
        dbapi_connection.isolation_level = None
        dbapi_connection.execute("PRAGMA busy_timeout = 10000")

    @event.listens_for(engine, "begin")
    def iniciar_transacao_imediata(connection):
        connection.exec_driver_sql("BEGIN IMMEDIATE")

    Base.metadata.create_all(engine)
    RaceSession = sessionmaker(bind=engine, expire_on_commit=False)
    setup_db = RaceSession()
    restaurante = Restaurante.create(
        db=setup_db,
        nome="Restaurante Concorrência RF11",
        cnpj="66.777.888/0001-99",
        telefone="(11) 96666-5555",
        email="rf11-race@restaurante.com",
        cep="01001-000",
        status=True,
    )
    garcom = Usuario.create(
        db=setup_db,
        idRestaurante=restaurante.idRestaurante,
        nome="Garçom Corrida",
        cpf="111.222.333-44",
        email="rf11-garcom@restaurante.com",
        senha=hash_senha("senha123"),
        funcao="Garcom",
    )
    cozinheiro = Usuario.create(
        db=setup_db,
        idRestaurante=restaurante.idRestaurante,
        nome="Cozinheiro Corrida",
        cpf="222.333.444-55",
        email="rf11-cozinha@restaurante.com",
        senha=hash_senha("senha123"),
        funcao="Cozinheiro",
    )
    mesa = Mesa.create(
        db=setup_db,
        idRestaurante=restaurante.idRestaurante,
        numero=1,
        status="Ocupada",
    )
    prato = Cardapio.create(
        db=setup_db,
        idRestaurante=restaurante.idRestaurante,
        nome="Item Concorrente",
        preco=10.0,
        categoria="Prato",
    )
    pedido = Pedido.create(
        db=setup_db,
        idRestaurante=restaurante.idRestaurante,
        idMesa=mesa.idMesa,
    )
    item = ItemPedido.create(
        db=setup_db,
        idPedido=pedido.idPedido,
        idCardapio=prato.idCardapio,
        quantidade=1,
        precoUnitario=10.0,
    )
    ids = (item.idItemPedido, garcom.idUsuario, cozinheiro.idUsuario)
    setup_db.close()

    barrier = Barrier(2)

    def executar(acao):
        db = RaceSession()
        try:
            barrier.wait(timeout=5)
            usuario_id = ids[1] if acao == "cancelar" else ids[2]
            usuario = Usuario.get_by_id(db, usuario_id)
            if acao == "cancelar":
                PedidoService(db).cancelar_item(
                    ids[0], usuario=usuario, motivo="Cliente solicitou"
                )
            else:
                PedidoService(db).update_item_status(
                    ids[0], "Em preparo", usuario=usuario
                )
            return "sucesso"
        except HTTPException as exc:
            return exc.status_code
        finally:
            db.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(executar, ("cancelar", "preparar")))
        assert resultados.count("sucesso") == 1
        assert resultados.count(409) == 1
    finally:
        engine.dispose()
