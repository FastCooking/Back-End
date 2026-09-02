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
    "DATABASE_URL",
    "postgresql+psycopg://fastcooking:fastcooking@localhost:5432/FASTCOOKING",
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
    
    assert validar_cpf(cpf_valido_1) == "529.982.247-25", "Falha ao validar CPF sem máscara"
    assert validar_cpf(cpf_valido_2) == "529.982.247-25", "Falha ao validar CPF com máscara"
    print("   [PASS] CPFs válidos formatados corretamente.")

    cpfs_invalidos = [
        "11111111111",  # todos iguais
        "12345678900",  # dígitos verificadores errados
        "123",          # tamanho insuficiente
        "abcdefghijk",  # não numérico
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
    try:
        UsuarioCreate(
            idRestaurante=1,
            nome="Teste Inválido",
            cpf="52998224725",
            email="valido@email.com",
            senha="123456senha",
            funcao="CargoInexistente",  # Deve falhar
        )
        raise AssertionError("Função inválida foi aceita!")
    except ValidationError:
        print("   [PASS] Função/Cargo não permitido rejeitado pelo schema.")

    # Validação de Senha Curta (< 6 caracteres)
    try:
        UsuarioCreate(
            idRestaurante=1,
            nome="Teste Senha Curta",
            cpf="52998224725",
            email="valido2@email.com",
            senha="123",  # Menos de 6 caracteres
            funcao="Garcom",
        )
        raise AssertionError("Senha curta foi aceita!")
    except ValidationError:
        print("   [PASS] Senha menor que 6 caracteres rejeitada pelo schema.")

    # Validação de Email Inválido
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
    print("=" * 70)


if __name__ == "__main__":
    run_unit_and_integration_tests()
