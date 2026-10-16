import uuid

from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Restaurante import Restaurante
from src.models.Sessao import Sessao
from src.services.SessaoService import SessaoService


def criar_mesa(db):
    restaurante = Restaurante(
        idRestaurante=uuid.uuid4(),
        nome="Restaurante Teste",
        cnpj="12345678000199",
        telefone="11999999999",
        email="teste@fastcooking.com",
        cep="06000000",
        status=True,
    )

    mesa = Mesa(
        idMesa=uuid.uuid4(),
        idRestaurante=restaurante.idRestaurante,
        numero=1,
        status="Disponivel",
    )

    db.add(restaurante)
    db.add(mesa)
    db.commit()
    db.refresh(mesa)

    return mesa


def test_abrir_mesa_cria_sessao_sem_pedido(db_session):
    mesa = criar_mesa(db_session)

    sessao = SessaoService.abrir_mesa(db_session, mesa.idMesa)

    assert sessao.idMesa == mesa.idMesa
    assert sessao.status == "Ativa"

    db_session.refresh(mesa)
    assert mesa.status == "Indisponivel"

    assert db_session.query(Sessao).count() == 1
    assert db_session.query(Pedido).count() == 0


def test_abrir_mesa_reutiliza_sessao_ativa(db_session):
    mesa = criar_mesa(db_session)

    primeira = SessaoService.abrir_mesa(db_session, mesa.idMesa)
    segunda = SessaoService.abrir_mesa(db_session, mesa.idMesa)

    assert primeira.idSessao == segunda.idSessao
    assert db_session.query(Sessao).count() == 1


def test_abrir_mesa_inexistente_retorna_404(db_session):
    from fastapi import HTTPException

    id_inexistente = uuid.uuid4()

    try:
        SessaoService.abrir_mesa(db_session, id_inexistente)
        assert False, "Deveria retornar erro 404"
    except HTTPException as erro:
        assert erro.status_code == 404


def test_rf02_expiracao_automatica_sessao_inativa(db_session):
    from datetime import datetime, timedelta

    mesa = criar_mesa(db_session)
    sessao = SessaoService.abrir_mesa(db_session, mesa.idMesa)

    # Simula 11 minutos de inatividade desde a abertura
    sessao.dataAbertura = datetime.now() - timedelta(minutes=11)
    db_session.commit()

    expiradas = SessaoService.expirar_sessoes_inativas(db_session, limite_minutos=10)
    assert len(expiradas) == 1
    assert expiradas[0].idSessao == sessao.idSessao
    assert expiradas[0].status == "Expirada"

    db_session.refresh(mesa)
    assert mesa.status == "Disponivel"


def test_rf02_abrir_mesa_expira_sessao_antiga_e_abre_nova(db_session):
    from datetime import datetime, timedelta

    mesa = criar_mesa(db_session)
    sessao_antiga = SessaoService.abrir_mesa(db_session, mesa.idMesa)

    # Simula 15 minutos atrás
    sessao_antiga.dataAbertura = datetime.now() - timedelta(minutes=15)
    db_session.commit()

    # Reabrir mesa deve criar uma nova sessão ativa porque a anterior expirou
    nova_sessao = SessaoService.abrir_mesa(db_session, mesa.idMesa)
    assert nova_sessao.idSessao != sessao_antiga.idSessao
    assert nova_sessao.status == "Ativa"

    db_session.refresh(sessao_antiga)
    assert sessao_antiga.status == "Expirada"