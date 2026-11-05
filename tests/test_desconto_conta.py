from datetime import datetime

import pytest

from src.core.security import criar_token
from src.models.Cardapio import Cardapio
from src.models.ItemPedido import ItemPedido
from src.models.LogDesconto import LogDesconto
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.services.UsuarioService import hash_senha


@pytest.fixture
def cenario_desconto(db_session):
    restaurante = Restaurante.create(
        db=db_session,
        nome="Restaurante Desconto KFC",
        cnpj="11.222.333/0001-44",
        telefone="(11) 97777-8888",
        email="desconto@fastcooking.com.br",
        cep="01001-000",
        status=True,
    )

    gerente = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Gerente Silva",
        cpf="111.444.777-33",
        email="gerente.silva@fastcooking.com.br",
        senha=hash_senha("senhaGerente123"),
        funcao="Gerente",
    )

    garcom = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Garçom Marcos",
        cpf="222.555.888-44",
        email="marcos.garcom@fastcooking.com.br",
        senha=hash_senha("senhaGarcom123"),
        funcao="Garcom",
    )

    cozinheiro = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Cozinheiro João",
        cpf="333.666.999-55",
        email="joao.cozinha@fastcooking.com.br",
        senha=hash_senha("senhaCozinha123"),
        funcao="Cozinheiro",
    )

    mesa = Mesa.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        numero=7,
        status="Ocupada",
    )

    prato1 = Cardapio.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Combo Balde Frango",
        preco=60.0,
        categoria="Prato Principal",
    )

    prato2 = Cardapio.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Refrigerante Refil",
        preco=15.0,
        categoria="Bebida",
    )

    pedido = Pedido.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        idMesa=mesa.idMesa,
        idGarcom=garcom.idUsuario,
        status="Aberto",
    )

    item1 = ItemPedido.create(
        db=db_session,
        idPedido=pedido.idPedido,
        idCardapio=prato1.idCardapio,
        quantidade=1,
        precoUnitario=60.0,
        status="Pendente",
    )

    item2 = ItemPedido.create(
        db=db_session,
        idPedido=pedido.idPedido,
        idCardapio=prato2.idCardapio,
        quantidade=2,
        precoUnitario=15.0,
        status="Pendente",
    )

    token_garcom = criar_token(garcom.idUsuario, "Garcom", restaurante.idRestaurante)
    token_gerente = criar_token(gerente.idUsuario, "Gerente", restaurante.idRestaurante)
    token_cozinha = criar_token(cozinheiro.idUsuario, "Cozinheiro", restaurante.idRestaurante)

    return {
        "restaurante": restaurante,
        "gerente": gerente,
        "garcom": garcom,
        "cozinheiro": cozinheiro,
        "mesa": mesa,
        "prato1": prato1,
        "prato2": prato2,
        "pedido": pedido,
        "item1": item1,
        "item2": item2,
        "headers_garcom": {"Authorization": f"Bearer {token_garcom}"},
        "headers_gerente": {"Authorization": f"Bearer {token_gerente}"},
        "headers_cozinha": {"Authorization": f"Bearer {token_cozinha}"},
    }


def test_desconto_so_aplicado_apos_validacao_senha_gerente(client, cenario_desconto, db_session):
    """Requisito 1: O desconto só é aplicado após validação da senha do gerente."""
    pedido = cenario_desconto["pedido"]
    headers = cenario_desconto["headers_garcom"]

    # 1. Tentativa sem fornecer senha -> Rejeitado 400
    resp_sem_senha = client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={"tipo": "valor", "valor": 10.0, "motivo": "Cortesia"},
        headers=headers,
    )
    assert resp_sem_senha.status_code == 400
    assert "senha do gerente é obrigatória" in resp_sem_senha.json()["detail"].lower()

    # 2. Tentativa com senha errada -> Rejeitado 401
    resp_senha_errada = client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={"senhaGerente": "senhaInvalida999", "tipo": "valor", "valor": 10.0, "motivo": "Cortesia"},
        headers=headers,
    )
    assert resp_senha_errada.status_code == 401
    assert "senha do gerente inválida" in resp_senha_errada.json()["detail"].lower()

    # Verifica que o pedido NÃO recebeu desconto no banco
    db_session.refresh(pedido)
    assert float(pedido.desconto or 0.0) == 0.0

    # 3. Tentativa com senha correta do gerente -> Sucesso 200
    resp_correta = client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={
            "senhaGerente": "senhaGerente123",
            "tipo": "valor",
            "valor": 20.0,
            "motivo": "Desconto de fidelidade do cliente",
        },
        headers=headers,
    )
    assert resp_correta.status_code == 200
    dados = resp_correta.json()
    assert dados["sucesso"] is True
    assert dados["desconto"]["valor"] == 20.0
    assert dados["desconto"]["gerente"] == "Gerente Silva"

    # Confirma persistência no banco
    db_session.refresh(pedido)
    assert float(pedido.desconto) == 20.0
    assert pedido.motivoDesconto == "Desconto de fidelidade do cliente"
    assert pedido.idGerenteDesconto == cenario_desconto["gerente"].idUsuario


def test_log_desconto_contem_usuario_valor_e_horario(client, cenario_desconto, db_session):
    """Requisito 2: O log de desconto contém usuário (gerente), valor aplicado e horário."""
    pedido = cenario_desconto["pedido"]
    headers = cenario_desconto["headers_garcom"]

    # Aplica desconto percentual de 10% (Subtotal: 60 + 2*15 = 90 -> 10% = 9.0)
    resp = client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={
            "senhaGerente": "senhaGerente123",
            "tipo": "percentual",
            "valor": 10.0,
            "motivo": "Cupom de 10% de aniversário",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data_resp = resp.json()

    # Valida no retorno da API
    assert "log" in data_resp
    assert "Gerente Silva" in data_resp["log"]["usuario"]
    assert data_resp["log"]["valorDesconto"] == 9.0
    assert data_resp["log"]["dataHora"] is not None
    assert data_resp["log"]["sucesso"] is True

    # Valida persistência direta na tabela LogDesconto
    logs_bd = LogDesconto.get_by_pedido(db_session, pedido.idPedido)
    assert len(logs_bd) >= 1
    log_concessao = next(l for l in logs_bd if l.sucesso is True)
    assert "Gerente Silva" in log_concessao.usuario
    assert log_concessao.funcaoUsuario == "Gerente"
    assert float(log_concessao.valorDesconto) == 9.0
    assert log_concessao.dataHora is not None
    assert isinstance(log_concessao.dataHora, datetime)

    # Valida endpoint de consulta de logs de desconto do pedido
    resp_logs = client.get(
        f"/pedidos/{pedido.idPedido}/desconto/logs",
        headers=headers,
    )
    assert resp_logs.status_code == 200
    lista_logs = resp_logs.json()
    assert len(lista_logs) >= 1
    assert "Gerente Silva" in lista_logs[0]["usuario"]
    assert lista_logs[0]["valorDesconto"] == 9.0
    assert lista_logs[0]["dataHora"] is not None


def test_senha_invalida_rejeita_operacao_e_registra_tentativa_falha(client, cenario_desconto, db_session):
    """Requisito 3: Senha inválida rejeita a operação e registra a tentativa falha."""
    pedido = cenario_desconto["pedido"]
    gerente = cenario_desconto["gerente"]
    headers = cenario_desconto["headers_garcom"]

    # Envia senha errada
    resp_errada = client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={
            "senhaGerente": "senhaIncorretaXYZ",
            "tipo": "valor",
            "valor": 15.0,
            "motivo": "Tentativa indevida",
        },
        headers=headers,
    )
    assert resp_errada.status_code == 401
    assert "senha do gerente inválida" in resp_errada.json()["detail"].lower()

    # 1. Verifica incremento no contador de tentativas falhas do gerente
    db_session.refresh(gerente)
    assert gerente.tentativasFalhas == 1

    # 2. Verifica registro de log da tentativa falha
    logs_bd = LogDesconto.get_by_pedido(db_session, pedido.idPedido)
    assert len(logs_bd) >= 1
    log_falha = logs_bd[0]
    assert log_falha.sucesso is False
    assert "Senha do gerente inválida" in log_falha.motivoFalha
    assert "Gerente Silva" in log_falha.usuario
    assert log_falha.dataHora is not None

    # 3. Garante que nenhum desconto foi aplicado ao pedido
    db_session.refresh(pedido)
    assert float(pedido.desconto or 0.0) == 0.0


def test_bloqueio_apos_multiplas_tentativas_com_senha_invalida(client, cenario_desconto, db_session):
    """Requisito 3 (Extensão): Bloquear após limite de tentativas com senha inválida."""
    pedido = cenario_desconto["pedido"]
    gerente = cenario_desconto["gerente"]
    headers = cenario_desconto["headers_garcom"]

    # Tentativa 1 incorreta
    client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={"senhaGerente": "errada1", "tipo": "valor", "valor": 5.0},
        headers=headers,
    )
    # Tentativa 2 incorreta
    client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={"senhaGerente": "errada2", "tipo": "valor", "valor": 5.0},
        headers=headers,
    )
    # Tentativa 3 incorreta -> atinge MAX_TENTATIVAS (3)
    client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={"senhaGerente": "errada3", "tipo": "valor", "valor": 5.0},
        headers=headers,
    )

    db_session.refresh(gerente)
    assert gerente.tentativasFalhas >= 3
    assert gerente.bloqueadoAte is not None
    assert gerente.bloqueadoAte > datetime.now()

    # Tentativa 4: deve retornar 403 Forbidden indicando bloqueio
    resp_bloqueado = client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={"senhaGerente": "senhaGerente123", "tipo": "valor", "valor": 5.0},
        headers=headers,
    )
    assert resp_bloqueado.status_code == 403
    assert "bloqueada" in resp_bloqueado.json()["detail"].lower()

    # Verifica registro de log de bloqueio
    logs = LogDesconto.get_by_pedido(db_session, pedido.idPedido)
    log_bloqueado = next((l for l in logs if "bloqueada" in (l.motivoFalha or "").lower()), None)
    assert log_bloqueado is not None


def test_valor_final_da_conta_reflete_corretamente_o_desconto(client, cenario_desconto, db_session):
    """Requisito 4: O valor final da conta reflete corretamente o desconto aplicado."""
    pedido = cenario_desconto["pedido"]
    headers_garcom = cenario_desconto["headers_garcom"]
    headers_gerente = cenario_desconto["headers_gerente"]
    headers_cozinha = cenario_desconto["headers_cozinha"]

    # Subtotal inicial: prato1 (60) + prato2 (2 * 15 = 30) = 90
    resp_get_inicial = client.get(f"/pedidos/{pedido.idPedido}")
    assert resp_get_inicial.status_code == 200
    assert resp_get_inicial.json()["subtotal"] == 90.0
    assert resp_get_inicial.json()["total"] == 90.0

    # Aplica desconto de R$ 25,00
    resp_desc = client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={
            "senhaGerente": "senhaGerente123",
            "tipo": "valor",
            "valor": 25.0,
            "motivo": "Desconto Promocional",
        },
        headers=headers_garcom,
    )
    assert resp_desc.status_code == 200
    dados_desc = resp_desc.json()
    assert dados_desc["pedido"]["subtotal"] == 90.0
    assert dados_desc["pedido"]["desconto"] == 25.0
    assert dados_desc["pedido"]["total"] == 65.0
    assert dados_desc["pedido"]["saldoRestante"] == 65.0

    # Consulta pedido via GET /pedidos/{idPedido}
    resp_get = client.get(f"/pedidos/{pedido.idPedido}")
    assert resp_get.status_code == 200
    dados_pedido = resp_get.json()
    assert dados_pedido["subtotal"] == 90.0
    assert dados_pedido["desconto"] == 25.0
    assert dados_pedido["total"] == 65.0
    assert dados_pedido["saldoRestante"] == 65.0

    # Consulta comanda ativa pela mesa (GET /mesas/{idMesa}/pedido-ativo)
    resp_mesa = client.get(f"/mesas/{cenario_desconto['mesa'].idMesa}/pedido-ativo")
    assert resp_mesa.status_code == 200
    dados_mesa = resp_mesa.json()
    assert dados_mesa["subtotal"] == 90.0
    assert dados_mesa["desconto"] == 25.0
    assert dados_mesa["total"] == 65.0
    assert dados_mesa["saldoRestante"] == 65.0

    # Cozinha avança os itens para permitir fechamento da comanda
    item1 = cenario_desconto["item1"]
    item2 = cenario_desconto["item2"]
    for it in (item1, item2):
        client.patch(f"/pedidos/itens/{it.idItemPedido}/status", json={"status": "Em preparo"}, headers=headers_cozinha)
        client.patch(f"/pedidos/itens/{it.idItemPedido}/status", json={"status": "Pronto"}, headers=headers_cozinha)
        client.post(f"/pedidos/itens/{it.idItemPedido}/claim", headers=headers_garcom)
        client.post(f"/pedidos/entregas/{it.idItemPedido}/complete", headers=headers_garcom)

    # Realiza pagamento exato do valor final da conta com desconto (R$ 65,00)
    resp_pag = client.post(
        f"/pedidos/{pedido.idPedido}/pagamento",
        json={"formaPagamento": "PIX", "valor": 65.0},
        headers=headers_garcom,
    )
    assert resp_pag.status_code == 201
    dados_pag = resp_pag.json()
    assert dados_pag["pedidoEncerrado"] is True
    assert dados_pag["totalPedido"] == 65.0
    assert dados_pag["totalPago"] == 65.0
    assert dados_pag["saldoRestante"] == 0.0

    # Consulta no histórico de pedidos (GET /pedidos?tipo=historico)
    resp_hist = client.get("/pedidos?tipo=historico", headers=headers_gerente)
    assert resp_hist.status_code == 200
    pedidos_hist = resp_hist.json()
    p_fechado = next((p for p in pedidos_hist if p["idPedido"] == str(pedido.idPedido)), None)
    assert p_fechado is not None
    assert p_fechado["subtotal"] == 90.0
    assert p_fechado["desconto"] == 25.0
    assert p_fechado["total"] == 65.0
    assert p_fechado["status"] == "Fechado"


def test_validacoes_de_limite_de_desconto(client, cenario_desconto):
    """Validações de segurança: desconto não pode ultrapassar subtotal ou 100%."""
    pedido = cenario_desconto["pedido"]
    headers = cenario_desconto["headers_garcom"]

    # 1. Desconto em valor maior que o subtotal (subtotal = 90, tentativa = 100) -> 400
    resp_maior_subtotal = client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={
            "senhaGerente": "senhaGerente123",
            "tipo": "valor",
            "valor": 100.0,
        },
        headers=headers,
    )
    assert resp_maior_subtotal.status_code == 400
    assert "não pode ser maior que o subtotal" in resp_maior_subtotal.json()["detail"].lower()

    # 2. Desconto percentual maior que 100% -> 400
    resp_maior_cem = client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={
            "senhaGerente": "senhaGerente123",
            "tipo": "percentual",
            "valor": 110.0,
        },
        headers=headers,
    )
    assert resp_maior_cem.status_code == 400
    assert "não pode ser maior que 100%" in resp_maior_cem.json()["detail"].lower()

    # 3. Desconto zero ou negativo -> 422 (pydantic gt=0)
    resp_zero = client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={
            "senhaGerente": "senhaGerente123",
            "tipo": "valor",
            "valor": 0.0,
        },
        headers=headers,
    )
    assert resp_zero.status_code == 422


def test_remocao_desconto_recalcula_conta(client, cenario_desconto, db_session):
    """Permite remoção de desconto restaurando o valor original da conta."""
    pedido = cenario_desconto["pedido"]
    headers = cenario_desconto["headers_garcom"]

    # Aplica desconto de R$ 30,00
    client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={"senhaGerente": "senhaGerente123", "tipo": "valor", "valor": 30.0},
        headers=headers,
    )

    resp_get_desc = client.get(f"/pedidos/{pedido.idPedido}")
    assert resp_get_desc.json()["total"] == 60.0

    # Remove o desconto
    resp_remove = client.delete(
        f"/pedidos/{pedido.idPedido}/desconto",
        headers=headers,
    )
    assert resp_remove.status_code == 200
    dados_rem = resp_remove.json()
    assert dados_rem["pedido"]["desconto"] == 0.0
    assert dados_rem["pedido"]["total"] == 90.0

    # Confirma via GET
    resp_final = client.get(f"/pedidos/{pedido.idPedido}")
    assert resp_final.json()["desconto"] == 0.0
    assert resp_final.json()["total"] == 90.0


def test_cancelamento_item_com_justificativa_rf11(client, cenario_desconto, db_session):
    """Dependência RF11: Cancelamento de item com justificativa."""
    item1 = cenario_desconto["item1"]
    pedido = cenario_desconto["pedido"]
    headers = cenario_desconto["headers_garcom"]

    # Garçom cancela o item fornecendo a justificativa
    resp = client.patch(
        f"/pedidos/itens/{item1.idItemPedido}/cancelar",
        json={"justificativa": "Cliente desistiu da sobremesa/combo"},
        headers=headers,
    )
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["item"]["status"] == "Cancelado"
    assert "Cliente desistiu" in (dados["item"]["observacao"] or "")

    # Subtotal atualizado reflete a dedução do item cancelado (90 - 60 = 30)
    resp_get = client.get(f"/pedidos/{pedido.idPedido}")
    assert resp_get.json()["total"] == 30.0


def test_aplicar_desconto_via_endpoint_mesa(client, cenario_desconto):
    """Suporte ergonômico: aplicação de desconto direto pelo endpoint da mesa."""
    mesa = cenario_desconto["mesa"]
    headers = cenario_desconto["headers_garcom"]

    resp = client.post(
        f"/mesas/{mesa.idMesa}/desconto",
        json={
            "senhaGerente": "senhaGerente123",
            "tipo": "valor",
            "valor": 15.0,
            "motivo": "Desconto via mesa",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["sucesso"] is True
    assert resp.json()["pedido"]["desconto"] == 15.0
    assert resp.json()["pedido"]["total"] == 75.0
