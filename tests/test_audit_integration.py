from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.core.audit_logger import obter_caminho_arquivo_auditoria
from src.core.security import criar_token
from src.models.Cardapio import Cardapio
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Restaurante import Restaurante
from src.models.Sessao import Sessao
from src.models.Usuario import Usuario
from src.services.UsuarioService import hash_senha


@pytest.fixture
def cenario_auditoria(db_session, monkeypatch, tmp_path):
    log_dir = tmp_path / "integration_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AUDIT_LOG_DIR", str(log_dir))

    restaurante = Restaurante.create(
        db=db_session,
        nome="Restaurante Auditoria",
        cnpj="11.222.333/0001-44",
        telefone="(11) 98888-7777",
        email="audit@restaurante.com",
        cep="01001-000",
        status=True,
    )

    gerente = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Gerente Auditoria",
        cpf="111.222.333-44",
        email="gerente_audit@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Gerente",
    )

    mesa = Mesa.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        numero=42,
        status="Disponivel",
    )

    sessao = Sessao(
        idMesa=mesa.idMesa,
        status="Ativa",
    )
    db_session.add(sessao)
    db_session.commit()
    db_session.refresh(sessao)

    pedido = Pedido.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        idMesa=mesa.idMesa,
        sessao_id=str(sessao.idSessao),
        status="Aberto",
    )

    item_cardapio = Cardapio.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Prato Teste Audit",
        preco=29.90,
        categoria="Pratos Principais",
        tempoPreparo=15,
    )

    item_pedido = ItemPedido.create(
        db=db_session,
        idPedido=pedido.idPedido,
        idCardapio=item_cardapio.idCardapio,
        quantidade=1,
        precoUnitario=item_cardapio.preco,
        status="Pendente",
    )

    return {
        "log_dir": log_dir,
        "restaurante": restaurante,
        "gerente": gerente,
        "mesa": mesa,
        "sessao": sessao,
        "pedido": pedido,
        "item_pedido": item_pedido,
    }


def test_audit_edicao_e_exclusao_mesa(client: TestClient, cenario_auditoria):
    gerente = cenario_auditoria["gerente"]
    mesa = cenario_auditoria["mesa"]
    log_dir = cenario_auditoria["log_dir"]
    token = criar_token(gerente.idUsuario, gerente.funcao, gerente.idRestaurante)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Edição de mesa
    resp_patch = client.patch(
        f"/mesas/{mesa.idMesa}",
        json={"numero": 43, "status": "Disponivel"},
        headers=headers,
    )
    assert resp_patch.status_code == 200

    # 2. Exclusão de mesa
    resp_delete = client.delete(f"/mesas/{mesa.idMesa}", headers=headers)
    assert resp_delete.status_code == 204

    # Verifica se os logs foram gravados no arquivo diário
    arq_log = obter_caminho_arquivo_auditoria(base_dir=log_dir)
    assert arq_log.exists()
    conteudo = arq_log.read_text(encoding="utf-8")

    assert "ACAO=EDICAO_MESA" in conteudo
    assert f"idUsuario={gerente.idUsuario}" in conteudo
    assert "ACAO=EXCLUSAO_MESA" in conteudo
    assert "numero=43" in conteudo


def test_audit_cancelamento_assistido_e_cliente(client: TestClient, cenario_auditoria):
    gerente = cenario_auditoria["gerente"]
    item_pedido = cenario_auditoria["item_pedido"]
    log_dir = cenario_auditoria["log_dir"]
    token = criar_token(gerente.idUsuario, gerente.funcao, gerente.idRestaurante)
    headers = {"Authorization": f"Bearer {token}"}

    # Cancelamento assistido pelo gerente
    resp_cancela = client.patch(
        f"/pedidos/itens/{item_pedido.idItemPedido}/cancelar",
        json={"motivo": "Cancelamento solicitado pelo cliente na mesa"},
        headers=headers,
    )
    assert resp_cancela.status_code == 200

    arq_log = obter_caminho_arquivo_auditoria(base_dir=log_dir)
    assert arq_log.exists()
    conteudo = arq_log.read_text(encoding="utf-8")

    assert "ACAO=CANCELAMENTO_ASSISTIDO" in conteudo
    assert f"idUsuario={gerente.idUsuario}" in conteudo
    assert "Cancelamento solicitado pelo cliente na mesa" in conteudo


def test_audit_cancelamento_cliente(client: TestClient, cenario_auditoria, db_session):
    mesa = cenario_auditoria["mesa"]
    pedido = cenario_auditoria["pedido"]
    item_cardapio = cenario_auditoria["item_pedido"].cardapio
    log_dir = cenario_auditoria["log_dir"]

    # Cria outro item pendente para cancelamento pelo cliente
    novo_item = ItemPedido.create(
        db=db_session,
        idPedido=pedido.idPedido,
        idCardapio=item_cardapio.idCardapio,
        quantidade=1,
        precoUnitario=item_cardapio.preco,
        status="Pendente",
    )

    resp_cliente = client.post(
        f"/pedidos/itens/{novo_item.idItemPedido}/cancelamento-cliente",
        json={},
    )
    assert resp_cliente.status_code == 200

    arq_log = obter_caminho_arquivo_auditoria(base_dir=log_dir)
    assert arq_log.exists()
    conteudo = arq_log.read_text(encoding="utf-8")

    assert "ACAO=CANCELAMENTO_CLIENTE" in conteudo
    assert f"idMesa={mesa.idMesa}" in conteudo
    assert f"sessao_id={pedido.sessao_id}" in conteudo
    assert "tipoCancelamento=AUTOATENDIMENTO_CLIENTE" in conteudo


def test_audit_login_sucesso_e_falha(client: TestClient, cenario_auditoria):
    gerente = cenario_auditoria["gerente"]
    log_dir = cenario_auditoria["log_dir"]

    # 1. Falha de login
    resp_falha = client.post(
        "/auth/login",
        json={"email": gerente.email, "senha": "senha_totalmente_errada"},
    )
    assert resp_falha.status_code == 401

    # 2. Sucesso de login
    resp_sucesso = client.post(
        "/auth/login",
        json={"email": gerente.email, "senha": "senha123"},
    )
    assert resp_sucesso.status_code == 200

    arq_log = obter_caminho_arquivo_auditoria(base_dir=log_dir)
    assert arq_log.exists()
    conteudo = arq_log.read_text(encoding="utf-8")

    assert "ACAO=LOGIN_FALHA" in conteudo
    assert "ACAO=LOGIN_SUCESSO" in conteudo
    assert f"idUsuario={gerente.idUsuario}" in conteudo
    # Garante LGPD: senha nunca deve constar no log
    assert "senha_totalmente_errada" not in conteudo
    assert "senha123" not in conteudo
