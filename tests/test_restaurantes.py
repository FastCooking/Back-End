import os
import sys
import time

# Adiciona o diretório raiz ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pydantic import ValidationError

from src.schemas.RestauranteSchema import (
    RestauranteCreate,
    validar_cep,
    validar_cnpj,
    validar_telefone,
)

from fastapi.testclient import TestClient
from src.app import app

client = TestClient(app)


# =====================================================================
# HELPERS
# =====================================================================

def _gerar_cnpj_valido(seed: int) -> str:
    """Gera um CNPJ válido (formatado) a partir de uma semente numérica."""
    base = f"{(seed % 90000000 + 10000000):08d}0001"
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s1 = sum(int(base[i]) * p1[i] for i in range(12))
    d1 = 0 if s1 % 11 < 2 else 11 - (s1 % 11)
    p2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s2 = sum(int((base + str(d1))[i]) * p2[i] for i in range(13))
    d2 = 0 if s2 % 11 < 2 else 11 - (s2 % 11)
    return f"{base[:2]}.{base[2:5]}.{base[5:8]}/{base[8:12]}-{d1}{d2}"


# =====================================================================
# TESTES
# =====================================================================

def test_restaurant():
    print("=" * 70)
    print("SUÍTE DE TESTES REESCRITA: RESTAURANTES (Schemas + API CRUD)")
    print("=" * 70)

    ts = int(time.time() * 1000)

    # -----------------------------------------------------------------
    # 1. TESTES UNITÁRIOS DE VALIDAÇÃO DE CNPJ, CEP E TELEFONE
    # -----------------------------------------------------------------
    print("\n[1/7] Testes Unitários de Formatação e Validação de Campos:")
    cnpj_valido_1 = "11222333000181"
    cnpj_valido_2 = "11.222.333/0001-81"
    assert validar_cnpj(cnpj_valido_1) == "11.222.333/0001-81"
    assert validar_cnpj(cnpj_valido_2) == "11.222.333/0001-81"
    print("   [PASS] CNPJ válido formatado corretamente.")

    cnpjs_invalidos = [
        "00000000000000",   # dígitos repetidos
        "11222333000180",   # dígito verificador incorreto
        "123456",           # tamanho insuficiente
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

    # -----------------------------------------------------------------
    # 2. TESTES DE VALIDAÇÃO DE SCHEMAS PYDANTIC
    # -----------------------------------------------------------------
    print("\n[2/7] Testes de Schemas Pydantic:")
    try:
        RestauranteCreate(
            nome="R",   # Menos de 2 caracteres
            cnpj="11.222.333/0001-81",
            telefone="(11) 98765-4321",
            email="contato@restaurante.com",
            cep="01001-000",
        )
        raise AssertionError("Nome muito curto foi aceito!")
    except ValidationError:
        print("   [PASS] Nome menor que 2 caracteres rejeitado.")

    # -----------------------------------------------------------------
    # 3. CREATE VIA API (POST /restaurantes)
    # -----------------------------------------------------------------
    print("\n[3/7] CREATE via API (POST /restaurantes):")
    cnpj_teste = _gerar_cnpj_valido(ts)
    payload_criacao = {
        "nome": f"Restaurante Gourmet {ts}",
        "cnpj": cnpj_teste,
        "telefone": "(11) 98765-4321",
        "email": f"gourmet_{ts}@restaurante.com",
        "cep": "01001-000",
        "status": True,
    }
    resp_create = client.post("/restaurantes", json=payload_criacao)
    assert resp_create.status_code == 201, f"Esperava 201, recebeu {resp_create.status_code}: {resp_create.text}"
    dados_criado = resp_create.json()

    id_criado = dados_criado["idRestaurante"]
    assert id_criado is not None
    assert dados_criado["nome"] == f"Restaurante Gourmet {ts}"
    assert dados_criado["cnpj"] == cnpj_teste
    assert dados_criado["status"] is True
    print(f"   [PASS] Restaurante ID {id_criado} cadastrado com sucesso via API.")

    # -----------------------------------------------------------------
    # 4. DUPLICIDADE (409 Conflict)
    # -----------------------------------------------------------------
    print("\n[4/7] Validação de Duplicidade (POST /restaurantes com mesmo CNPJ/e-mail):")
    resp_dup = client.post("/restaurantes", json=payload_criacao)
    assert resp_dup.status_code == 409, f"Esperava 409, recebeu {resp_dup.status_code}"
    print("   [PASS] CNPJ/e-mail duplicado rejeitado com 409 Conflict.")

    # -----------------------------------------------------------------
    # 5. GET BY ID + LIST com filtros
    # -----------------------------------------------------------------
    print("\n[5/7] GET BY ID + LIST via API:")

    resp_get = client.get(f"/restaurantes/{id_criado}")
    assert resp_get.status_code == 200
    assert resp_get.json()["idRestaurante"] == id_criado
    assert resp_get.json()["nome"] == dados_criado["nome"]
    print("   [PASS] GET /restaurantes/{id}: Restaurante recuperado e validado.")

    resp_list = client.get("/restaurantes")
    assert resp_list.status_code == 200
    assert any(r["idRestaurante"] == id_criado for r in resp_list.json())

    resp_busca = client.get(f"/restaurantes?busca=Restaurante Gourmet {ts}")
    assert resp_busca.status_code == 200
    assert any(r["idRestaurante"] == id_criado for r in resp_busca.json())
    print("   [PASS] GET /restaurantes: Listagem e busca textual funcionando.")

    # -----------------------------------------------------------------
    # 6. UPDATE + STATUS CHANGE via API
    # -----------------------------------------------------------------
    print("\n[6/7] UPDATE + STATUS CHANGE via API:")

    resp_update = client.put(f"/restaurantes/{id_criado}", json={
        "nome": f"Restaurante Gourmet Atualizado {ts}",
        "telefone": "(11) 91111-2222",
    })
    assert resp_update.status_code == 200
    dados_update = resp_update.json()
    assert dados_update["nome"] == f"Restaurante Gourmet Atualizado {ts}"
    assert dados_update["telefone"] == "(11) 91111-2222"
    print("   [PASS] PUT /restaurantes/{id}: Dados atualizados com sucesso.")

    # Desativar
    resp_desativar = client.patch(f"/restaurantes/{id_criado}/status", json={"status": False})
    assert resp_desativar.status_code == 200
    assert resp_desativar.json()["status"] is False

    # Reativar
    resp_reativar = client.patch(f"/restaurantes/{id_criado}/status", json={"status": True})
    assert resp_reativar.status_code == 200
    assert resp_reativar.json()["status"] is True
    print("   [PASS] PATCH /restaurantes/{id}/status: Ativação/desativação efetuada.")

    # -----------------------------------------------------------------
    # 7. DELETE via API (soft delete / desativação)
    # -----------------------------------------------------------------
    print("\n[7/7] DELETE via API (POST /restaurantes/{id}):")
    resp_delete = client.delete(f"/restaurantes/{id_criado}")
    assert resp_delete.status_code == 204

    # Verifica que o restaurante foi desativado e anonimizado (soft delete)
    resp_pos_delete = client.get(f"/restaurantes/{id_criado}")
    assert resp_pos_delete.status_code == 200
    dados_anonimizado = resp_pos_delete.json()
    assert dados_anonimizado["nome"].startswith("RESTAURANTE REMOVIDO")
    assert dados_anonimizado["email"].startswith("removido_")
    assert dados_anonimizado["status"] is False
    print("   [PASS] DELETE /restaurantes/{id}: Restaurante anonimizado e desativado com sucesso.")

    # =================================================================
    print("\n" + "=" * 70)
    print("TODOS OS TESTES DE RESTAURANTE PASSARAM COM 100% DE SUCESSO!")
    print("=" * 70)


if __name__ == "__main__":
    test_restaurant()
