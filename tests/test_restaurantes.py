import os
import sys
import time

# Adiciona o diretório raiz ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from pydantic import ValidationError

from src.database.connection import SessionLocal
from src.schemas.RestauranteSchema import (
    RestauranteCreate,
    RestauranteResponse,
    RestauranteUpdate,
    validar_cep,
    validar_cnpj,
    validar_telefone,
)
from src.services.RestauranteService import RestauranteService

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://fastcooking:fastcooking@localhost:5432/FASTCOOKING",
)


def run_restaurante_tests():
    print("=" * 70)
    print("INICIANDO SUÍTE DE TESTES: CRUD DE RESTAURANTES & REGRAS DE NEGÓCIO")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. TESTES UNITÁRIOS DE VALIDAÇÃO DE CNPJ, CEP E TELEFONE
    # -------------------------------------------------------------
    print("\n[1/4] Testes Unitários de Formatação e Validação de Campos:")
    cnpj_valido_1 = "11222333000181"
    cnpj_valido_2 = "11.222.333/0001-81"
    assert validar_cnpj(cnpj_valido_1) == "11.222.333/0001-81"
    assert validar_cnpj(cnpj_valido_2) == "11.222.333/0001-81"
    print("   [PASS] CNPJ válido formatado corretamente.")

    cnpjs_invalidos = [
        "00000000000000",  # dígitos repetidos
        "11222333000180",  # dígito verificador incorreto
        "123456",          # tamanho insuficiente
    ]
    for c_inv in cnpjs_invalidos:
        try:
            validar_cnpj(c_inv)
            raise AssertionError(f"CNPJ inválido '{c_inv}' foi aceito!")
        except ValueError:
            pass
    print("   [PASS] CNPJs inválidos rejeitados com sucesso.")

    assert validar_cep("01001000") == "01001-000"
    assert validar_cep("01001-000") == "01001-000"
    print("   [PASS] CEP validado e formatado.")

    assert validar_telefone("11987654321") == "(11) 98765-4321"
    assert validar_telefone("1133334444") == "(11) 3333-4444"
    print("   [PASS] Telefones fixo e móvel validados e formatados.")

    # -------------------------------------------------------------
    # 2. TESTES DE VALIDAÇÃO DE SCHEMAS PYDANTIC
    # -------------------------------------------------------------
    print("\n[2/4] Testes de Schemas Pydantic:")
    try:
        RestauranteCreate(
            nome="R",  # Menos de 2 caracteres
            cnpj="11.222.333/0001-81",
            telefone="(11) 98765-4321",
            email="contato@restaurante.com",
            cep="01001-000",
        )
        raise AssertionError("Nome muito curto foi aceito!")
    except ValidationError:
        print("   [PASS] Nome menor que 2 caracteres rejeitado.")

    # -------------------------------------------------------------
    # 3. TESTES DE INTEGRAÇÃO COM BANCO DE DADOS (CRUD COMPLETO)
    # -------------------------------------------------------------
    print("\n[3/4] Testes de Integração com Banco de Dados (Service Layer & Model):")
    session = SessionLocal()

    try:
        service = RestauranteService(session)
        ts = int(time.time())

        # 3.1 CREATE
        # Gera CNPJ dinâmico válido
        base_cnpj = f"{(ts % 90000000 + 10000000):08d}0001"
        p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        s1 = sum(int(base_cnpj[i]) * p1[i] for i in range(12))
        d1 = 0 if s1 % 11 < 2 else 11 - (s1 % 11)
        p2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        s2 = sum(int((base_cnpj + str(d1))[i]) * p2[i] for i in range(13))
        d2 = 0 if s2 % 11 < 2 else 11 - (s2 % 11)
        cnpj_dinamico = f"{base_cnpj[:2]}.{base_cnpj[2:5]}.{base_cnpj[5:8]}/{base_cnpj[8:12]}-{d1}{d2}"

        dados_restaurante = RestauranteCreate(
            nome=f"Restaurante Gourmet {ts}",
            cnpj=cnpj_dinamico,
            telefone="(11) 98765-4321",
            email=f"gourmet_{ts}@restaurante.com",
            cep="01001-000",
            status=True,
        )
        restaurante_criado = service.create(dados_restaurante)
        id_criado = restaurante_criado.idRestaurante

        assert id_criado is not None
        assert restaurante_criado.nome == f"Restaurante Gourmet {ts}"
        assert restaurante_criado.cnpj == cnpj_dinamico
        assert restaurante_criado.status is True
        print(f"   [PASS] CREATE: Restaurante ID {id_criado} cadastrado com sucesso.")

        # 3.2 DUPLICATE CHECKS
        try:
            service.create(dados_restaurante)
            raise AssertionError("Permitiu cadastrar restaurante duplicado!")
        except HTTPException as e:
            assert e.status_code == 409
            print("   [PASS] Validação de unicidade de CNPJ e E-mail confirmada (409 Conflict).")

        # 3.3 GET BY ID
        restaurante_lido = service.get_by_id(id_criado)
        assert restaurante_lido.idRestaurante == id_criado
        response_model = RestauranteResponse.model_validate(restaurante_lido)
        assert response_model.nome == restaurante_criado.nome
        print("   [PASS] GET BY ID: Restaurante recuperado e validado pelo schema de resposta.")

        # 3.4 LIST WITH SEARCH & PAGINATION
        lista_todos = service.list_all()
        assert any(r.idRestaurante == id_criado for r in lista_todos)
        lista_busca = service.list_all(busca=f"Restaurante Gourmet {ts}")
        assert any(r.idRestaurante == id_criado for r in lista_busca)
        print("   [PASS] LIST: Listagem e busca textual funcionando.")

        # 3.5 UPDATE
        dados_update = RestauranteUpdate(
            nome=f"Restaurante Gourmet Atualizado {ts}",
            telefone="(11) 91111-2222",
        )
        restaurante_atualizado = service.update(id_criado, dados_update)
        assert restaurante_atualizado.nome == f"Restaurante Gourmet Atualizado {ts}"
        assert restaurante_atualizado.telefone == "(11) 91111-2222"
        print("   [PASS] UPDATE: Dados atualizados com sucesso.")

        # 3.6 STATUS CHANGE
        service.change_status(id_criado, False)
        assert service.get_by_id(id_criado).status is False
        service.change_status(id_criado, True)
        assert service.get_by_id(id_criado).status is True
        print("   [PASS] STATUS CHANGE: Ativação/desativação efetuada.")

        # 3.7 DELETE (Disable)
        service.delete(id_criado)
        assert service.get_by_id(id_criado).status is False
        print("   [PASS] DELETE: Restaurante desativado conforme método disable do Model.")

    finally:
        session.close()

    print("\n" + "=" * 70)
    print("TODOS OS TESTES DE RESTAURANTE PASSARAM COM 100% DE SUCESSO!")
    print("=" * 70)


if __name__ == "__main__":
    run_restaurante_tests()
