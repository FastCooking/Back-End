"""
Suíte de testes de autorização e controle de acesso baseado em funções (RBAC).

Regras de negócio validadas:
1. Adm (Administrador do sistema):
   - Nível mais alto de acesso.
   - Gerencia restaurantes: criar, consultar, editar, alterar status e excluir.
   - Gerencia todos os perfis de funcionários (inclusive criar outro Gerente, outro Adm, Garçom e Cozinheiro).
   - Acessa o módulo administrativo completo.

2. Gerente:
   - Gerencia apenas os funcionários abaixo na hierarquia (Garçom e Cozinheiro).
   - NÃO PODE criar Administrador nem outro Gerente (403 Forbidden).
   - NÃO PODE editar Administrador nem outro Gerente (403 Forbidden).
   - NÃO PODE alterar status de Administrador nem outro Gerente (403 Forbidden).
   - NÃO PODE criar, editar, alterar status ou excluir restaurantes (403 Forbidden).
   - Pode consultar restaurantes (GET /restaurantes).
   - Gerencia recursos da sua filial (mesas, cardápio, estoque, comanda).
   - Não executa operações exclusivas da cozinha (alteração de status de preparo) nem de garçom.

3. Cozinheiro:
   - Acessa a fila de preparo da cozinha (KDS).
   - Aceita e atualiza andamento de preparo dos pratos (PATCH /pedidos/itens/{id}/status).
   - NÃO acessa o módulo administrativo (GET /usuarios, POST /usuarios, POST /restaurantes, POST /mesas -> 403 Forbidden).
   - NÃO executa operações exclusivas de garçom (pagamento, entregas).

4. Garçom:
   - Acessa o módulo de atendimento e entregas.
   - Reivindica e conclui entregas de pedidos prontos.
   - Realiza pagamentos de pedidos e libera sobremesas.
   - NÃO acessa o módulo administrativo (GET /usuarios, POST /restaurantes, POST /mesas -> 403 Forbidden).
   - NÃO executa operações exclusivas da cozinha (PATCH /pedidos/itens/{id}/status -> 403 Forbidden).
"""

import os
import sys
import uuid
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.security import criar_token
from src.models.Cardapio import Cardapio
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.services.UsuarioService import hash_senha


# =====================================================================
# HELPERS
# =====================================================================

def _gerar_cpf_valido(seed: int) -> str:
    """Gera um CPF válido (formatado) a partir de uma semente numérica."""
    base = f"{(seed % 900000000 + 100000000):09d}"
    soma1 = sum(int(base[i]) * (10 - i) for i in range(9))
    d1 = 0 if (soma1 * 10) % 11 == 10 else (soma1 * 10) % 11
    soma2 = sum(int((base + str(d1))[i]) * (11 - i) for i in range(10))
    d2 = 0 if (soma2 * 10) % 11 == 10 else (soma2 * 10) % 11
    return f"{base[:3]}.{base[3:6]}.{base[6:9]}-{d1}{d2}"


def _gerar_cnpj_valido(seed: int) -> str:
    """Gera um CNPJ válido (formatado) a partir de uma semente numérica."""
    base_cnpj = f"{(seed % 90000000 + 10000000):08d}0001"
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s1 = sum(int(base_cnpj[i]) * p1[i] for i in range(12))
    d1 = 0 if s1 % 11 < 2 else 11 - (s1 % 11)
    p2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s2 = sum(int((base_cnpj + str(d1))[i]) * p2[i] for i in range(13))
    d2 = 0 if s2 % 11 < 2 else 11 - (s2 % 11)
    return f"{base_cnpj[:2]}.{base_cnpj[2:5]}.{base_cnpj[5:8]}/{base_cnpj[8:12]}-{d1}{d2}"


# =====================================================================
# FIXTURES E DADOS AUXILIARES
# =====================================================================

@pytest.fixture
def cenario_rbac(db_session):
    """Cria o cenário base contendo restaurante, usuários de cada papel e pedido."""
    restaurante = Restaurante.create(
        db=db_session,
        nome="Restaurante Matriz RBAC",
        cnpj="11.222.333/0001-44",
        telefone="(11) 98888-7777",
        email="rbac@fastcooking.com.br",
        cep="01001-000",
        status=True,
    )

    restaurante2 = Restaurante.create(
        db=db_session,
        nome="Restaurante Filial RBAC",
        cnpj="22.333.444/0001-55",
        telefone="(11) 98888-6666",
        email="filial_rbac@fastcooking.com.br",
        cep="01002-000",
        status=True,
    )

    adm = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Admin Geral",
        cpf="000.111.222-33",
        email="adm_rbac@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Adm",
    )

    gerente = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Gerente Matriz",
        cpf="111.222.333-44",
        email="gerente_rbac@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Gerente",
    )

    outro_gerente = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Segundo Gerente",
        cpf="444.555.666-77",
        email="gerente2_rbac@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Gerente",
    )

    cozinheiro = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Cozinheiro Chefe",
        cpf="222.333.444-55",
        email="cozinheiro_rbac@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Cozinheiro",
    )

    garcom = Usuario.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Garçom Atendimento",
        cpf="333.444.555-66",
        email="garcom_rbac@fastcooking.com.br",
        senha=hash_senha("senha123"),
        funcao="Garcom",
    )

    mesa = Mesa.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        numero=1,
        status="Ocupada",
    )

    prato = Cardapio.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Prato Teste RBAC",
        descricao="Prato principal",
        preco=35.0,
        categoria="Prato Principal",
    )

    sobremesa = Cardapio.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        nome="Sobremesa Teste RBAC",
        descricao="Sobremesa deliciosa",
        preco=15.0,
        categoria="Sobremesa",
    )

    pedido = Pedido.create(
        db=db_session,
        idRestaurante=restaurante.idRestaurante,
        idMesa=mesa.idMesa,
        idGarcom=garcom.idUsuario,
        status="Aberto",
    )

    item_prato = ItemPedido(
        idPedido=pedido.idPedido,
        idCardapio=prato.idCardapio,
        precoUnitario=prato.preco,
        quantidade=1,
        status="Pendente",
        categoria=prato.categoria,
    )
    item_sobremesa = ItemPedido(
        idPedido=pedido.idPedido,
        idCardapio=sobremesa.idCardapio,
        precoUnitario=sobremesa.preco,
        quantidade=1,
        status="Pendente",
        categoria=sobremesa.categoria,
        liberadoParaPreparo=False,
    )
    db_session.add(item_prato)
    db_session.add(item_sobremesa)
    db_session.commit()
    db_session.refresh(item_prato)
    db_session.refresh(item_sobremesa)

    return {
        "restaurante": restaurante,
        "restaurante2": restaurante2,
        "adm": adm,
        "gerente": gerente,
        "outro_gerente": outro_gerente,
        "cozinheiro": cozinheiro,
        "garcom": garcom,
        "mesa": mesa,
        "item_prato": item_prato,
        "item_sobremesa": item_sobremesa,
        "pedido": pedido,
        "headers_adm": {"Authorization": f"Bearer {criar_token(adm.idUsuario, adm.funcao, restaurante.idRestaurante)}"},
        "headers_gerente": {"Authorization": f"Bearer {criar_token(gerente.idUsuario, gerente.funcao, restaurante.idRestaurante)}"},
        "headers_cozinheiro": {"Authorization": f"Bearer {criar_token(cozinheiro.idUsuario, cozinheiro.funcao, restaurante.idRestaurante)}"},
        "headers_garcom": {"Authorization": f"Bearer {criar_token(garcom.idUsuario, garcom.funcao, restaurante.idRestaurante)}"},
    }


# =====================================================================
# 1. TESTES DO ADMINISTRADOR (ADM)
# =====================================================================

def test_adm_pode_gerenciar_restaurantes_completamente(client, cenario_rbac):
    """Adm tem permissão total para criar, consultar, atualizar e excluir restaurantes."""
    headers = cenario_rbac["headers_adm"]

    # 1. Criar novo restaurante com CNPJ válido
    novo_rest_payload = {
        "nome": "Novo Restaurante Adm",
        "cnpj": _gerar_cnpj_valido(998877),
        "telefone": "(11) 91111-2222",
        "email": "novo_adm@fastcooking.com.br",
        "cep": "01001-000",
        "status": True,
    }
    resp = client.post("/restaurantes", json=novo_rest_payload, headers=headers)
    assert resp.status_code == 201
    id_novo_rest = resp.json()["idRestaurante"]

    # 2. Consultar lista
    resp_lista = client.get("/restaurantes", headers=headers)
    assert resp_lista.status_code == 200

    # 3. Editar restaurante
    resp_edit = client.put(
        f"/restaurantes/{id_novo_rest}",
        json={"nome": "Restaurante Atualizado Adm"},
        headers=headers,
    )
    assert resp_edit.status_code == 200
    assert resp_edit.json()["nome"] == "Restaurante Atualizado Adm"

    # 4. Alterar status do restaurante
    resp_status = client.patch(
        f"/restaurantes/{id_novo_rest}/status",
        json={"status": False},
        headers=headers,
    )
    assert resp_status.status_code == 200
    assert resp_status.json()["status"] is False

    # 5. Excluir restaurante
    resp_del = client.delete(f"/restaurantes/{id_novo_rest}", headers=headers)
    assert resp_del.status_code == 204


def test_adm_pode_criar_qualquer_tipo_de_usuario(client, cenario_rbac):
    """Adm tem permissão para cadastrar Gerentes, outros Adms, Cozinheiros e Garçons."""
    headers = cenario_rbac["headers_adm"]
    id_rest = str(cenario_rbac["restaurante"].idRestaurante)

    cargos = ["Adm", "Gerente", "Cozinheiro", "Garcom"]
    for idx, cargo in enumerate(cargos):
        payload = {
            "nome": f"Usuário {cargo} por Adm",
            "cpf": _gerar_cpf_valido(idx + 100),
            "email": f"user_{cargo.lower()}_{idx}@fastcooking.com.br",
            "senha": "SenhaForte@123",
            "funcao": cargo,
            "idRestaurante": id_rest,
        }
        resp = client.post("/usuarios", json=payload, headers=headers)
        assert resp.status_code == 201, f"Adm deveria conseguir criar usuário com função {cargo}: {resp.text}"
        assert resp.json()["funcao"] == cargo


# =====================================================================
# 2. TESTES DO GERENTE
# =====================================================================

def test_gerente_nao_pode_criar_editar_ou_excluir_restaurantes(client, cenario_rbac):
    """Gerente NÃO pode criar, editar, alterar status nem excluir restaurantes (403 Forbidden)."""
    headers = cenario_rbac["headers_gerente"]
    id_rest = str(cenario_rbac["restaurante2"].idRestaurante)

    # 1. Tentar criar restaurante -> 403
    resp_criar = client.post(
        "/restaurantes",
        json={
            "nome": "Tentativa Gerente",
            "cnpj": "88.777.666/0001-55",
            "telefone": "(11) 93333-4444",
            "email": "gerente_negado@fastcooking.com.br",
            "cep": "01001-000",
            "status": True,
        },
        headers=headers,
    )
    assert resp_criar.status_code == 403

    # 2. Tentar editar restaurante -> 403
    resp_edit = client.put(
        f"/restaurantes/{id_rest}",
        json={"nome": "Nome Alterado Gerente"},
        headers=headers,
    )
    assert resp_edit.status_code == 403

    # 3. Tentar alterar status do restaurante -> 403
    resp_status = client.patch(
        f"/restaurantes/{id_rest}/status",
        json={"status": False},
        headers=headers,
    )
    assert resp_status.status_code == 403

    # 4. Tentar excluir restaurante -> 403
    resp_del = client.delete(f"/restaurantes/{id_rest}", headers=headers)
    assert resp_del.status_code == 403

    # 5. Mas Gerente PODE consultar restaurantes -> 200
    resp_get = client.get("/restaurantes", headers=headers)
    assert resp_get.status_code == 200


def test_gerente_gerencia_apenas_cargos_inferiores(client, cenario_rbac):
    """Gerente só pode criar Garçom ou Cozinheiro. Criar Adm ou Gerente é proibido (403)."""
    headers = cenario_rbac["headers_gerente"]
    id_rest = str(cenario_rbac["restaurante"].idRestaurante)

    # 1. Pode criar Garçom -> 201
    resp_garcom = client.post(
        "/usuarios",
        json={
            "nome": "Garçom Criado por Gerente",
            "cpf": _gerar_cpf_valido(201),
            "email": "garcom_pelo_gerente@fastcooking.com.br",
            "senha": "SenhaForte@123",
            "funcao": "Garcom",
            "idRestaurante": id_rest,
        },
        headers=headers,
    )
    assert resp_garcom.status_code == 201

    # 2. Pode criar Cozinheiro -> 201
    resp_cozinha = client.post(
        "/usuarios",
        json={
            "nome": "Cozinheiro Criado por Gerente",
            "cpf": _gerar_cpf_valido(202),
            "email": "cozinha_pelo_gerente@fastcooking.com.br",
            "senha": "SenhaForte@123",
            "funcao": "Cozinheiro",
            "idRestaurante": id_rest,
        },
        headers=headers,
    )
    assert resp_cozinha.status_code == 201

    # 3. Tentar criar outro Gerente -> 403 Forbidden
    resp_gerente = client.post(
        "/usuarios",
        json={
            "nome": "Outro Gerente",
            "cpf": _gerar_cpf_valido(203),
            "email": "outro_gerente_proibido@fastcooking.com.br",
            "senha": "SenhaForte@123",
            "funcao": "Gerente",
            "idRestaurante": id_rest,
        },
        headers=headers,
    )
    assert resp_gerente.status_code == 403

    # 4. Tentar criar Adm -> 403 Forbidden
    resp_adm = client.post(
        "/usuarios",
        json={
            "nome": "Admin Proibido",
            "cpf": _gerar_cpf_valido(204),
            "email": "adm_proibido@fastcooking.com.br",
            "senha": "SenhaForte@123",
            "funcao": "Adm",
            "idRestaurante": id_rest,
        },
        headers=headers,
    )
    assert resp_adm.status_code == 403


def test_gerente_nao_pode_editar_nem_desativar_adm_ou_outro_gerente(client, cenario_rbac):
    """Gerente não pode editar nem desativar Administradores ou outros Gerentes."""
    headers = cenario_rbac["headers_gerente"]
    id_adm = str(cenario_rbac["adm"].idUsuario)
    id_outro_gerente = str(cenario_rbac["outro_gerente"].idUsuario)
    id_garcom = str(cenario_rbac["garcom"].idUsuario)

    # 1. Tentar alterar status do Adm -> 403
    resp_adm_status = client.patch(
        f"/usuarios/{id_adm}/status",
        json={"status": False},
        headers=headers,
    )
    assert resp_adm_status.status_code == 403

    # 2. Tentar alterar status de outro Gerente -> 403
    resp_ger_status = client.patch(
        f"/usuarios/{id_outro_gerente}/status",
        json={"status": False},
        headers=headers,
    )
    assert resp_ger_status.status_code == 403

    # 3. Tentar editar outro Gerente -> 403
    resp_ger_edit = client.put(
        f"/usuarios/{id_outro_gerente}",
        json={"nome": "Nome Modificado Indevidamente"},
        headers=headers,
    )
    assert resp_ger_edit.status_code == 403

    # 4. Mas PODE alterar status do Garçom (subordinado) -> 200
    resp_garcom_status = client.patch(
        f"/usuarios/{id_garcom}/status",
        json={"status": False},
        headers=headers,
    )
    assert resp_garcom_status.status_code == 200
    assert resp_garcom_status.json()["status"] is False


def test_gerente_nao_executa_operacoes_exclusivas_cozinha_ou_garcom(client, cenario_rbac):
    """Gerente não executa operação exclusiva de Cozinheiro (mudar status do item) nem de Garçom (liberar sobremesa)."""
    headers = cenario_rbac["headers_gerente"]
    id_item_prato = str(cenario_rbac["item_prato"].idItemPedido)
    id_item_sobremesa = str(cenario_rbac["item_sobremesa"].idItemPedido)

    # Operação exclusiva de Cozinheiro
    resp_cozinha = client.patch(
        f"/pedidos/itens/{id_item_prato}/status",
        json={"status": "Em preparo"},
        headers=headers,
    )
    assert resp_cozinha.status_code == 403

    # Operação exclusiva de Garçom
    resp_garcom = client.patch(
        f"/pedidos/itens/{id_item_sobremesa}/liberar-sobremesa",
        headers=headers,
    )
    assert resp_garcom.status_code == 403


# =====================================================================
# 3. TESTES DO COZINHEIRO
# =====================================================================

def test_cozinheiro_acessa_kds_e_atualiza_status_do_prato(client, cenario_rbac):
    """Cozinheiro pode consultar KDS e atualizar andamento de preparo dos pratos."""
    headers = cenario_rbac["headers_cozinheiro"]
    id_item_prato = str(cenario_rbac["item_prato"].idItemPedido)

    # 1. Acessa fila KDS -> 200
    resp_kds = client.get("/pedidos/kds/fila", headers=headers)
    assert resp_kds.status_code == 200

    # 2. Atualiza status para 'Em preparo' -> 200
    resp_prep = client.patch(
        f"/pedidos/itens/{id_item_prato}/status",
        json={"status": "Em preparo"},
        headers=headers,
    )
    assert resp_prep.status_code == 200
    assert resp_prep.json()["item"]["status"] == "Em preparo"

    # 3. Atualiza status para 'Pronto' -> 200
    resp_pronto = client.patch(
        f"/pedidos/itens/{id_item_prato}/status",
        json={"status": "Pronto"},
        headers=headers,
    )
    assert resp_pronto.status_code == 200
    assert resp_pronto.json()["item"]["status"] == "Pronto"


def test_cozinheiro_nao_acessa_modulo_administrativo_nem_garcom(client, cenario_rbac):
    """Cozinheiro não pode acessar cadastro de usuários, restaurantes, mesas nem pagamentos."""
    headers = cenario_rbac["headers_cozinheiro"]
    id_rest = str(cenario_rbac["restaurante"].idRestaurante)
    id_pedido = str(cenario_rbac["pedido"].idPedido)
    id_item = str(cenario_rbac["item_prato"].idItemPedido)

    # Não acessa usuários
    assert client.get("/usuarios", headers=headers).status_code == 403
    assert client.post("/usuarios", json={}, headers=headers).status_code == 403

    # Não acessa restaurantes
    assert client.get("/restaurantes", headers=headers).status_code == 403
    assert client.post("/restaurantes", json={}, headers=headers).status_code == 403

    # Não gerencia mesas
    assert client.post("/mesas", json={"idRestaurante": id_rest, "numero": 99}, headers=headers).status_code == 403

    # Não gerencia cardápio
    assert client.post("/cardapio", json={"idRestaurante": id_rest, "nome": "X"}, headers=headers).status_code == 403

    # Não realiza pagamento (exclusivo de Garçom/Gerente/Adm)
    resp_pag = client.post(
        f"/pedidos/{id_pedido}/pagamento",
        json={"formaPagamento": "PIX"},
        headers=headers,
    )
    assert resp_pag.status_code == 403

    # Não assume entrega no salão (claim de entrega é de Garçom)
    resp_claim = client.post(
        f"/pedidos/itens/{id_item}/claim",
        headers=headers,
    )
    assert resp_claim.status_code == 403


# =====================================================================
# 4. TESTES DO GARÇOM
# =====================================================================

def test_garcom_acessa_atendimento_entregas_e_pagamentos(client, cenario_rbac):
    """Garçom pode liberar sobremesas, assumir entregas e registrar pagamentos."""
    headers = cenario_rbac["headers_garcom"]
    headers_cozinha = cenario_rbac["headers_cozinheiro"]
    id_item_prato = str(cenario_rbac["item_prato"].idItemPedido)
    id_item_sobremesa = str(cenario_rbac["item_sobremesa"].idItemPedido)
    id_pedido = str(cenario_rbac["pedido"].idPedido)

    # 1. Garçom libera sobremesa do cliente -> 200
    resp_libera = client.patch(
        f"/pedidos/itens/{id_item_sobremesa}/liberar-sobremesa",
        headers=headers,
    )
    assert resp_libera.status_code == 200

    # 2. Cozinha avança item: Pendente -> Em preparo -> Pronto
    resp_prep = client.patch(
        f"/pedidos/itens/{id_item_prato}/status",
        json={"status": "Em preparo"},
        headers=headers_cozinha,
    )
    assert resp_prep.status_code == 200

    resp_pronto = client.patch(
        f"/pedidos/itens/{id_item_prato}/status",
        json={"status": "Pronto"},
        headers=headers_cozinha,
    )
    assert resp_pronto.status_code == 200

    # 3. Garçom assume entrega do item pronto -> 200
    resp_claim = client.post(
        f"/pedidos/itens/{id_item_prato}/claim",
        headers=headers,
    )
    assert resp_claim.status_code == 200

    # 4. Garçom conclui entrega do item -> 200
    resp_deliver = client.post(
        f"/pedidos/entregas/{id_item_prato}/complete",
        headers=headers,
    )
    assert resp_deliver.status_code == 200

    # 5. Garçom registra pagamento do pedido -> 201
    resp_pag = client.post(
        f"/pedidos/{id_pedido}/pagamento",
        json={"formaPagamento": "Cartão de Crédito", "valor": 50.0},
        headers=headers,
    )
    assert resp_pag.status_code == 201
    assert resp_pag.json()["pagamento"]["formaPagamento"] == "Cartão de Crédito"


def test_garcom_nao_acessa_modulo_administrativo_nem_operacoes_de_cozinha(client, cenario_rbac):
    """Garçom não pode acessar usuários, restaurantes, mesas nem alterar status de preparo na cozinha."""
    headers = cenario_rbac["headers_garcom"]
    id_rest = str(cenario_rbac["restaurante"].idRestaurante)
    id_item_prato = str(cenario_rbac["item_prato"].idItemPedido)

    # Não acessa usuários
    assert client.get("/usuarios", headers=headers).status_code == 403
    assert client.post("/usuarios", json={}, headers=headers).status_code == 403

    # Não acessa restaurantes
    assert client.get("/restaurantes", headers=headers).status_code == 403
    assert client.post("/restaurantes", json={}, headers=headers).status_code == 403

    # Não gerencia mesas
    assert client.post("/mesas", json={"idRestaurante": id_rest, "numero": 88}, headers=headers).status_code == 403

    # Não gerencia cardápio
    assert client.post("/cardapio", json={"idRestaurante": id_rest, "nome": "Y"}, headers=headers).status_code == 403

    # Não atualiza status de preparo na cozinha (exclusivo do Cozinheiro)
    resp_cozinha = client.patch(
        f"/pedidos/itens/{id_item_prato}/status",
        json={"status": "Em preparo"},
        headers=headers,
    )
    assert resp_cozinha.status_code == 403


# =====================================================================
# EXECUÇÃO DIRETA (STANDALONE)
# =====================================================================
if __name__ == "__main__":
    print("Executando bateria de testes de autorização RBAC...")
    exit_code = pytest.main(["-v", __file__])
    sys.exit(exit_code)
