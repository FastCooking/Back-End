import os
import sys
import time

# Adiciona o diretório raiz ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from src.app import app
from src.core.security import criar_token
from src.database.connection import SessionLocal
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.services.UsuarioService import hash_senha

client = TestClient(app)
DATABASE_URL = os.getenv(
    "DATABASE_URL"
)


def _gerar_cpf_valido(seed: int) -> str:
    base = f"{(seed % 900000000 + 100000000):09d}"
    soma1 = sum(int(base[i]) * (10 - i) for i in range(9))
    digito_1 = 0 if (soma1 * 10) % 11 == 10 else (soma1 * 10) % 11
    soma2 = sum(int((base + str(digito_1))[i]) * (11 - i) for i in range(10))
    digito_2 = 0 if (soma2 * 10) % 11 == 10 else (soma2 * 10) % 11
    return f"{base[:3]}.{base[3:6]}.{base[6:9]}-{digito_1}{digito_2}"


def run_acceptance_criteria_validation():
    print("=" * 70)
    print("VALIDAÇÃO DOS CRITÉRIOS DE ACEITE DA TAREFA")
    print("=" * 70)

    ts = int(time.time())
    login_teste = f"garcom_{ts}@fastcooking.com"
    senha_teste = "SenhaSegura@2026"

    auth_session = SessionLocal()
    try:
        gerente = (
            auth_session.query(Usuario)
            .filter(Usuario.funcao == "Gerente", Usuario.status.is_(True))
            .first()
        )
        if gerente is None:
            restaurante = auth_session.query(Restaurante).first()
            assert restaurante is not None, "É necessário um restaurante para criar o gerente de teste"
            gerente = Usuario(
                idRestaurante=restaurante.idRestaurante,
                nome="Gerente de Teste",
                cpf=_gerar_cpf_valido(int(time.time() * 1000)),
                email=f"gerente_teste_{ts}@fastcooking.com",
                senha=hash_senha("SenhaGerente@2026"),
                funcao="Gerente",
                status=True,
            )
            auth_session.add(gerente)
            auth_session.commit()
            auth_session.refresh(gerente)
        headers = {
            "Authorization": f"Bearer {criar_token(gerente.idUsuario, gerente.funcao)}"
        }
    finally:
        auth_session.close()

    # -------------------------------------------------------------
    # 1. A API cria um funcionário com nome, login, senha e perfil
    # -------------------------------------------------------------
    payload_criacao = {
        "nome": "Carlos Garçom",
        "login": login_teste,
        "senha": senha_teste,
        "perfil": "Garcom",
    }
    response = client.post("/usuarios", json=payload_criacao, headers=headers)
    assert response.status_code == 201, f"Esperava 201 Created, recebeu {response.status_code}: {response.text}"
    dados_retorno = response.json()

    assert dados_retorno["nome"] == "Carlos Garçom"
    assert dados_retorno["login"] == login_teste
    assert dados_retorno["perfil"] == "Garcom"
    assert "senha" not in dados_retorno, "A senha não deve ser retornada no payload de resposta"
    id_criado = dados_retorno["idUsuario"]
    print("[PASS] 1. A API cria um funcionário com nome, login, senha e perfil.")

    # -------------------------------------------------------------
    # 2. A senha é armazenada no banco em formato hash (bcrypt)
    # -------------------------------------------------------------
    session = SessionLocal()
    try:
        usuario_db = session.query(Usuario).filter(Usuario.idUsuario == id_criado).first()
        assert usuario_db is not None, "Usuário não encontrado no banco de dados"
        assert usuario_db.senha != senha_teste, "A senha foi gravada em texto plano!"
        assert usuario_db.senha.startswith(("$2b$", "$2a$")), f"A senha não está em formato bcrypt: {usuario_db.senha}"
        assert usuario_db.autenticar(senha_teste) is True, "A senha em hash não pôde ser autenticada"
        print(f"[PASS] 2. A senha está armazenada no banco com hash bcrypt ({usuario_db.senha[:15]}...).")
    finally:
        session.close()

    # -------------------------------------------------------------
    # 3. A API valida que o login não pode ser duplicado
    # -------------------------------------------------------------
    response_duplicado = client.post(
        "/usuarios", json=payload_criacao, headers=headers
    )
    assert response_duplicado.status_code == 409, f"Esperava 409 Conflict, recebeu {response_duplicado.status_code}"
    print("[PASS] 3. A API valida e impede logins duplicados (409 Conflict).")

    # -------------------------------------------------------------
    # 4. A API retorna erro 400 para campos obrigatórios ausentes
    # -------------------------------------------------------------
    payloads_invalidos = [
        {"nome": "Sem Login", "senha": "123456senha", "perfil": "Garcom"},           # Falta login/email
        {"login": "semsenha@email.com", "nome": "Sem Senha", "perfil": "Garcom"},    # Falta senha
        {"login": "semnome@email.com", "senha": "123456senha", "perfil": "Garcom"},   # Falta nome
        {"login": "semperfil@email.com", "nome": "Sem Perfil", "senha": "123456senha"}, # Falta perfil/funcao
    ]
    for p in payloads_invalidos:
        resp_invalido = client.post("/usuarios", json=p, headers=headers)
        assert resp_invalido.status_code == 400, f"Esperava 400 Bad Request para payload {p}, recebeu {resp_invalido.status_code}"

    print("[PASS] 4. A API retorna erro 400 para campos obrigatórios ausentes.")

    print("\n" + "=" * 70)
    print("TODOS OS REQUISITOS DE ACEITE FORAM VALIDADOS COM 100% DE SUCESSO!")
    print("=" * 70)


if __name__ == "__main__":
    run_acceptance_criteria_validation()
