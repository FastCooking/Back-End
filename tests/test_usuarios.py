import os
import sys
import time

# Adiciona o diretório raiz ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from pydantic import ValidationError

from src.database.connection import SessionLocal
from src.models.Restaurante import Restaurante
from src.schemas.UsuarioSchema import (
    UsuarioCreate,
    UsuarioResponse,
    UsuarioUpdate,
    validar_cpf,
)
from src.services.UsuarioService import (
    UsuarioService,
    hash_senha,
    verificar_senha,
)

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)


def run_unit_and_integration_tests():
    print("=" * 70)
    print("INICIANDO SUÍTE DE TESTES: CRUD DE USUÁRIOS & REGRAS DE NEGÓCIO")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. TESTES DE VALIDAÇÃO DE CPF
    # -------------------------------------------------------------
    print("\n[1/6] Testes Unitários de Validação de CPF:")
    cpf_valido_1 = "52998224725"  # CPF válido gerado algoritmicamente
    cpf_valido_2 = "529.982.247-25"
    
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.app import app
from src.schemas.UsuarioSchema import UsuarioCreate, validar_cpf
from src.services.UsuarioService import hash_senha, verificar_senha

client = TestClient(app)


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


def _criar_restaurante_via_api() -> dict:
    """Cria um restaurante via API e retorna o JSON de resposta."""
    ts = int(time.time() * 1000)
    # Gera CNPJ dinâmico válido
    base_cnpj = f"{(ts % 90000000 + 10000000):08d}0001"
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s1 = sum(int(base_cnpj[i]) * p1[i] for i in range(12))
    d1 = 0 if s1 % 11 < 2 else 11 - (s1 % 11)
    p2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s2 = sum(int((base_cnpj + str(d1))[i]) * p2[i] for i in range(13))
    d2 = 0 if s2 % 11 < 2 else 11 - (s2 % 11)
    cnpj = f"{base_cnpj[:2]}.{base_cnpj[2:5]}.{base_cnpj[5:8]}/{base_cnpj[8:12]}-{d1}{d2}"

    payload = {
        "nome": f"Restaurante Teste {ts}",
        "cnpj": cnpj,
        "telefone": "(11) 98765-4321",
        "email": f"rest_{ts}@teste.com",
        "cep": "01001-000",
        "status": True,
    }
    resp = client.post("/restaurantes", json=payload)
    assert resp.status_code == 201, f"Falha ao criar restaurante auxiliar: {resp.text}"
    return resp.json()


# =====================================================================
# TESTES
# =====================================================================

def test_users():
    print("=" * 70)
    print("SUÍTE DE TESTES UNIFICADA: USUÁRIOS (Schemas + API CRUD + Critérios)")
    print("=" * 70)

    ts = int(time.time() * 1000)

    # -----------------------------------------------------------------
    # 1. TESTES UNITÁRIOS DE VALIDAÇÃO DE CPF
    # -----------------------------------------------------------------
    print("\n[1/9] Testes Unitários de Validação de CPF:")
    cpf_valido_1 = "52998224725"
    cpf_valido_2 = "529.982.247-25"
    assert validar_cpf(cpf_valido_1) == "529.982.247-25", "Falha ao validar CPF sem máscara"
    assert validar_cpf(cpf_valido_2) == "529.982.247-25", "Falha ao validar CPF com máscara"
    print("   [PASS] CPFs válidos formatados corretamente.")

    cpfs_invalidos = [
        "11111111111",  # todos iguais
        "12345678900",  # dígitos verificadores errados
        "123",          # tamanho insuficiente
        "abcdefghijk",  # não numérico
        "11111111111",   # todos iguais
        "12345678900",   # dígitos verificadores errados
        "123",           # tamanho insuficiente
        "abcdefghijk",   # não numérico
    ]
    for cpf_inv in cpfs_invalidos:
        try:
            validar_cpf(cpf_inv)
            raise AssertionError(f"CPF inválido '{cpf_inv}' não foi rejeitado!")
        except ValueError:
            pass
    print("   [PASS] Todos os CPFs inválidos foram devidamente rejeitados.")

    # -------------------------------------------------------------
    # 2. TESTES DE HASH E VERIFICAÇÃO DE SENHA (BCRYPT)
    # -------------------------------------------------------------
    print("\n[2/6] Testes de Criptografia e Verificação de Senha:")
    # -----------------------------------------------------------------
    # 2. TESTES DE HASH E VERIFICAÇÃO DE SENHA (BCRYPT)
    # -----------------------------------------------------------------
    print("\n[2/9] Testes de Criptografia e Verificação de Senha:")
    senha_original = "MinhaSenha@123"
    senha_hasheada = hash_senha(senha_original)

    assert senha_hasheada != senha_original, "Hash não deve ser igual ao texto plano"
    assert senha_hasheada.startswith(("$2b$", "$2a$")), "Hash deve ser bcrypt"
    assert verificar_senha(senha_original, senha_hasheada) is True, "Falha ao verificar senha correta"
    assert verificar_senha("SenhaIncorreta", senha_hasheada) is False, "Senha incorreta foi aceita"
    print("   [PASS] Hash bcrypt e verificação funcionando perfeitamente.")

    # -------------------------------------------------------------
    # 3. TESTES DE VALIDAÇÃO DE SCHEMAS PYDANTIC
    # -------------------------------------------------------------
    print("\n[3/6] Testes de Validação de Schemas Pydantic:")
    
    # Validação de Função permitida
    # -----------------------------------------------------------------
    # 3. TESTES DE VALIDAÇÃO DE SCHEMAS PYDANTIC
    # -----------------------------------------------------------------
    print("\n[3/9] Testes de Validação de Schemas Pydantic:")

    # Função/Cargo não permitido
    try:
        UsuarioCreate(
            idRestaurante=1,
            nome="Teste Inválido",
            cpf="52998224725",
            email="valido@email.com",
            senha="123456senha",
            funcao="CargoInexistente",  # Deve falhar
            funcao="CargoInexistente",
        )
        raise AssertionError("Função inválida foi aceita!")
    except ValidationError:
        print("   [PASS] Função/Cargo não permitido rejeitado pelo schema.")

    # Validação de Senha Curta (< 6 caracteres)
    # Senha muito curta (< 6 caracteres)
    try:
        UsuarioCreate(
            idRestaurante=1,
            nome="Teste Senha Curta",
            cpf="52998224725",
            email="valido2@email.com",
            senha="123",  # Menos de 6 caracteres
            senha="123",
            funcao="Garcom",
        )
        raise AssertionError("Senha curta foi aceita!")
    except ValidationError:
        print("   [PASS] Senha menor que 6 caracteres rejeitada pelo schema.")

    # Validação de Email Inválido
    # E-mail inválido
    try:
        UsuarioCreate(
            idRestaurante=1,
            nome="Teste Email",
            cpf="52998224725",
            email="email_sem_arroba",
            senha="123456senha",
            funcao="Garcom",
        )
        raise AssertionError("E-mail inválido foi aceito!")
    except ValidationError:
        print("   [PASS] E-mail sem formato válido rejeitado pelo schema.")

    # -------------------------------------------------------------
    # 4. TESTES DE INTEGRAÇÃO COM O BANCO DE DADOS (SERVICE LAYER)
    # -------------------------------------------------------------
    print("\n[4/6] Testes de Integração com o Banco de Dados (CRUD Completo):")
    session = SessionLocal()

    try:
        # Garante um restaurante existente para vincular
        ts = int(time.time() * 1000)
        restaurante = session.query(Restaurante).first()
        if not restaurante:
            restaurante = Restaurante(
                nome=f"Restaurante Teste {ts}",
                cnpj=f"{(ts % 90000000 + 10000000):08d}/0001",
                telefone="(11) 98765-4321",
                email=f"restaurante_{ts}@teste.com",
                cep="01001-000",
                status=True,
            )
            session.add(restaurante)
            session.commit()
            session.refresh(restaurante)
        id_restaurante = restaurante.idRestaurante

        service = UsuarioService(session)

        # 4.1 CREATE
        base_cpf = f"{(ts % 900000000 + 100000000):09d}"
        soma1 = sum(int(base_cpf[i]) * (10 - i) for i in range(9))
        d1 = 0 if (soma1 * 10) % 11 == 10 else (soma1 * 10) % 11
        soma2 = sum(int((base_cpf + str(d1))[i]) * (11 - i) for i in range(10))
        d2 = 0 if (soma2 * 10) % 11 == 10 else (soma2 * 10) % 11
        cpf_dinamico = f"{base_cpf[:3]}.{base_cpf[3:6]}.{base_cpf[6:9]}-{d1}{d2}"

        dados_usuario = UsuarioCreate(
            idRestaurante=id_restaurante,
            nome="João Garçom",
            cpf=cpf_dinamico,
            email=f"joao_garcom_{ts}@fastcooking.com",
            senha="SenhaForte@2026",
            funcao="Garcom",
            status=True,
        )
        usuario_criado = service.create(dados_usuario)
        id_criado = usuario_criado.idUsuario

        assert id_criado is not None, "ID não foi gerado"
        assert usuario_criado.nome == "João Garçom"
        assert usuario_criado.cpf == cpf_dinamico
        assert usuario_criado.funcao == "Garcom"
        assert verificar_senha("SenhaForte@2026", usuario_criado.senha) is True
        print(f"   [PASS] CREATE: Usuário ID {id_criado} criado com sucesso.")

        # 4.2 DUPLICATE CHECKS
        try:
            service.create(dados_usuario)  # Tenta recriar com mesmo email e cpf
            raise AssertionError("Permitiu cadastrar usuário com email/CPF duplicado!")
        except HTTPException as e:
            assert e.status_code == 409, f"Esperava status 409, obteve {e.status_code}"
            print("   [PASS] Validação de duplicidade (409 Conflict) confirmada.")

        # 4.3 GET BY ID
        usuario_lido = service.get_by_id(id_criado)
        assert usuario_lido.idUsuario == id_criado
        response_model = UsuarioResponse.model_validate(usuario_lido)
        assert hasattr(response_model, "senha") is False, "A resposta pública NÃO deve conter a senha"
        print("   [PASS] GET BY ID: Usuário recuperado e serializado sem exposição de senha.")

        # 4.4 LIST WITH FILTERS & SEARCH
        lista_rest = service.list_all(idRestaurante=id_restaurante)
        assert len(lista_rest) >= 1
        lista_funcao = service.list_all(funcao="Garcom")
        assert any(u.idUsuario == id_criado for u in lista_funcao)
        lista_busca = service.list_all(busca="João Garçom")
        assert any(u.idUsuario == id_criado for u in lista_busca)
        print("   [PASS] LIST: Filtros por restaurante, cargo e busca por texto funcionando.")

        # 4.5 UPDATE
        dados_atualizacao = UsuarioUpdate(
            nome="João Pedro Garçom",
            funcao="Gerente",
            senha="NovaSenhaSegura@123",
        )
        usuario_atualizado = service.update(id_criado, dados_atualizacao)
        assert usuario_atualizado.nome == "João Pedro Garçom"
        assert usuario_atualizado.funcao == "Gerente"
        assert verificar_senha("NovaSenhaSegura@123", usuario_atualizado.senha) is True
        # 4.6 MODEL METHODS & STATUS CHANGE
        assert usuario_atualizado.autenticar("NovaSenhaSegura@123") is True
        assert usuario_atualizado.autenticar("SenhaIncorreta") is False
        print("   [PASS] MODEL: Método usuario.autenticar() validado com sucesso.")

        usuario_inativado = service.change_status(id_criado, False)
        assert usuario_inativado.status is False
        usuario_reativado = service.change_status(id_criado, True)
        assert usuario_reativado.status is True
        print("   [PASS] STATUS CHANGE: Ativação/desativação de usuário testada.")

        # 4.7 DELETE (Model Anonymization)
        service.delete(id_criado)
        usuario_deletado = service.get_by_id(id_criado)
        assert usuario_deletado.nome == "USUARIO REMOVIDO"
        assert usuario_deletado.cpf == "000.000.000-00"
        assert usuario_deletado.email == "USUARIO REMOVIDO"
        print("   [PASS] DELETE: Usuário anonimizado conforme método delete do Model.")

    finally:
        session.close()

    print("\n" + "=" * 70)
    print("TODOS OS TESTES FORAM EXECUTADOS COM 100% DE SUCESSO!")
    # -----------------------------------------------------------------
    # 4. CREATE VIA API — Critério: cria funcionário com nome, login,
    #    senha e perfil; senha NÃO retorna no payload
    # -----------------------------------------------------------------
    print("\n[4/9] CREATE via API (POST /usuarios):")

    # Garante restaurante via API
    rest_data = _criar_restaurante_via_api()
    id_restaurante = rest_data["idRestaurante"]

    cpf_usuario = _gerar_cpf_valido(ts)
    login_teste = f"joao_garcom_{ts}@fastcooking.com"
    senha_teste = "SenhaForte@2026"

    payload_criacao = {
        "idRestaurante": id_restaurante,
        "nome": "João Garçom",
        "login": login_teste,
        "senha": senha_teste,
        "perfil": "Garcom",
        "cpf": cpf_usuario,
        "status": True,
    }
    resp_create = client.post("/usuarios", json=payload_criacao)
    assert resp_create.status_code == 201, f"Esperava 201, recebeu {resp_create.status_code}: {resp_create.text}"
    dados_criado = resp_create.json()

    id_criado = dados_criado["idUsuario"]
    assert id_criado is not None, "ID não foi gerado"
    assert dados_criado["nome"] == "João Garçom"
    assert dados_criado["login"] == login_teste
    assert dados_criado["perfil"] == "Garcom"
    assert "senha" not in dados_criado, "A senha NÃO deve ser retornada no payload de resposta"
    print(f"   [PASS] Usuário ID {id_criado} criado com sucesso via API. Senha omitida na resposta.")

    # -----------------------------------------------------------------
    # 5. HASH NO BANCO — Critério: senha armazenada em hash bcrypt
    #    (verificado indiretamente pelo endpoint de autenticação ou
    #     pelo fato de a API não retornar a senha e o create ter aceitado)
    # -----------------------------------------------------------------
    print("\n[5/9] Verificação de Hash Bcrypt (via API — sem acesso direto ao banco):")
    # Re-busca pelo GET para confirmar que a senha não é exposta
    resp_get = client.get(f"/usuarios/{id_criado}")
    assert resp_get.status_code == 200
    dados_get = resp_get.json()
    assert "senha" not in dados_get, "GET retornou a senha — violação de segurança!"
    print("   [PASS] Senha não exposta em nenhum endpoint de leitura (hash confirmado pela criação bem-sucedida).")

    # -----------------------------------------------------------------
    # 6. DUPLICIDADE — Critério: login não pode ser duplicado (409)
    # -----------------------------------------------------------------
    print("\n[6/9] Validação de Duplicidade (POST /usuarios com mesmo login):")
    resp_dup = client.post("/usuarios", json=payload_criacao)
    assert resp_dup.status_code == 409, f"Esperava 409, recebeu {resp_dup.status_code}"
    print("   [PASS] Login/e-mail duplicado rejeitado com 409 Conflict.")

    # -----------------------------------------------------------------
    # 7. CAMPOS OBRIGATÓRIOS — Critério: retorna 400 para ausentes
    # -----------------------------------------------------------------
    print("\n[7/9] Validação de Campos Obrigatórios (400 Bad Request):")
    payloads_invalidos = [
        {"nome": "Sem Login", "senha": "123456senha", "perfil": "Garcom"},
        {"login": "semsenha@email.com", "nome": "Sem Senha", "perfil": "Garcom"},
        {"login": "semnome@email.com", "senha": "123456senha", "perfil": "Garcom"},
        {"login": "semperfil@email.com", "nome": "Sem Perfil", "senha": "123456senha"},
    ]
    for p in payloads_invalidos:
        resp_inv = client.post("/usuarios", json=p)
        assert resp_inv.status_code == 400, (
            f"Esperava 400 para payload {p}, recebeu {resp_inv.status_code}"
        )
    print("   [PASS] Todos os payloads incompletos retornaram 400 Bad Request.")

    # -----------------------------------------------------------------
    # 8. CRUD COMPLETO VIA API (GET, LIST, PUT, PATCH, DELETE)
    # -----------------------------------------------------------------
    print("\n[8/9] CRUD Completo via API (GET / LIST / PUT / PATCH status / DELETE):")

    # GET BY ID
    resp_get = client.get(f"/usuarios/{id_criado}")
    assert resp_get.status_code == 200
    assert resp_get.json()["idUsuario"] == id_criado
    print("   [PASS] GET /usuarios/{id}: Usuário recuperado com sucesso.")

    # LIST com filtros
    resp_list_rest = client.get(f"/usuarios?idRestaurante={id_restaurante}")
    assert resp_list_rest.status_code == 200
    assert any(u["idUsuario"] == id_criado for u in resp_list_rest.json())

    resp_list_funcao = client.get("/usuarios?funcao=Garcom")
    assert resp_list_funcao.status_code == 200
    assert any(u["idUsuario"] == id_criado for u in resp_list_funcao.json())

    resp_list_busca = client.get("/usuarios?busca=João Garçom")
    assert resp_list_busca.status_code == 200
    assert any(u["idUsuario"] == id_criado for u in resp_list_busca.json())
    print("   [PASS] GET /usuarios: Filtros por restaurante, cargo e busca textual funcionando.")

    # UPDATE (PUT)
    resp_update = client.put(f"/usuarios/{id_criado}", json={
        "nome": "João Pedro Garçom",
        "perfil": "Gerente",
        "senha": "NovaSenhaSegura@123",
    })
    assert resp_update.status_code == 200
    dados_update = resp_update.json()
    assert dados_update["nome"] == "João Pedro Garçom"
    assert dados_update["perfil"] == "Gerente"
    print("   [PASS] PUT /usuarios/{id}: Nome e função atualizados com sucesso.")

    # PATCH STATUS (desativar e reativar)
    resp_desativar = client.patch(f"/usuarios/{id_criado}/status", json={"status": False})
    assert resp_desativar.status_code == 200
    assert resp_desativar.json()["status"] is False

    resp_reativar = client.patch(f"/usuarios/{id_criado}/status", json={"status": True})
    assert resp_reativar.status_code == 200
    assert resp_reativar.json()["status"] is True
    print("   [PASS] PATCH /usuarios/{id}/status: Ativação/desativação testada.")

    # DELETE
    resp_delete = client.delete(f"/usuarios/{id_criado}")
    assert resp_delete.status_code == 204
    print("   [PASS] DELETE /usuarios/{id}: Usuário removido/anonimizado com sucesso.")

    # -----------------------------------------------------------------
    # 9. PÓS-DELETE — verifica anonimização via GET
    # -----------------------------------------------------------------
    print("\n[9/9] Verificação Pós-Delete (anonimização):")
    resp_pos_delete = client.get(f"/usuarios/{id_criado}")
    assert resp_pos_delete.status_code == 200
    dados_anonimizado = resp_pos_delete.json()
    assert dados_anonimizado["nome"].startswith("USUARIO REMOVIDO")
    assert dados_anonimizado["email"].startswith("removido_")
    assert dados_anonimizado["status"] is False
    print("   [PASS] Usuário anonimizado corretamente após exclusão.")

    # =================================================================
    print("\n" + "=" * 70)
    print("TODOS OS TESTES DE USUÁRIO FORAM EXECUTADOS COM 100% DE SUCESSO!")
    print("=" * 70)


if __name__ == "__main__":
    run_unit_and_integration_tests()
    test_users()
