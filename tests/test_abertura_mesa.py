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