import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import app as app_module
from src.core import security
from src.database.connection import Base, get_db
from src.models.Cardapio import Cardapio
from src.models.Mesa import Mesa
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario


@pytest.fixture
def pedido_env(tmp_path, monkeypatch):
    monkeypatch.setattr(security, "SECRET_KEY", "pedido-test-secret")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'pedido.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as db:
        rest = Restaurante(
            nome="Restaurante Comanda",
            cnpj="11.111.111/0001-11",
            telefone="11999999999",
            email="rc@example.test",
            cep="01001-000",
            status=True,
        )
        db.add(rest)
        db.flush()

        mesa = Mesa(
            idRestaurante=rest.idRestaurante,
            numero=10,
            status="Ocupada",
        )
        db.add(mesa)
        db.flush()

        item1 = Cardapio(
            idRestaurante=rest.idRestaurante,
            nome="Hambúrguer Artesanal",
            preco=35.0,
            categoria="Pratos principais",
            status=True,
        )
        item2 = Cardapio(
            idRestaurante=rest.idRestaurante,
            nome="Pudim de Leite",
            preco=15.0,
            categoria="Sobremesas",
            status=True,
        )
        db.add_all([item1, item2])
        db.flush()

        garcom = Usuario(
            nome="Garçom Teste",
            email="garcom@test.com",
            cpf="111.111.111-11",
            senha=b"$2b$12$Xs8OAPwFkuebFY548yaHhu6nJopBQgBIK/DD897/mMIR4uzOQz4aC".decode("utf-8"),
            funcao="Garcom",
            idRestaurante=rest.idRestaurante,
            status=True,
        )
        db.add(garcom)
        db.commit()

        yield {
            "engine": engine,
            "session_factory": session_factory,
            "idRestaurante": rest.idRestaurante,
            "idMesa": mesa.idMesa,
            "item1": item1.idCardapio,
            "item2": item2.idCardapio,
            "garcom": garcom,
        }


def test_cliente_pode_criar_pedido_e_comanda_compartilhada(pedido_env):
    def override_get_db():
        with pedido_env["session_factory"]() as db:
            yield db

    app_module.app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app_module.app)

    try:
        # 1. Cliente cria pedido sem token
        payload1 = {
            "idMesa": str(pedido_env["idMesa"]),
            "sessao_id": "sessao-mesa-10-cliente-1",
            "itens": [
                {
                    "idCardapio": str(pedido_env["item1"]),
                    "quantidade": 2,
                    "observacao": "Sem cebola",
                }
            ],
        }
        res1 = client.post("/pedidos", json=payload1)
        assert res1.status_code == 201, res1.text
        data1 = res1.json()
        id_pedido_1 = data1["pedido"]["idPedido"]
        assert len(data1["itens"]) == 1
        assert data1["itens"][0]["nomeItem"] == "Hambúrguer Artesanal"
        assert data1["itens"][0]["numeroMesa"] == 10

        # 2. Cliente 2 na mesma mesa cria pedido -> reutiliza mesma comanda/pedido ativo
        payload2 = {
            "idMesa": str(pedido_env["idMesa"]),
            "sessao_id": "sessao-mesa-10-cliente-2",
            "itens": [
                {
                    "idCardapio": str(pedido_env["item2"]),
                    "quantidade": 1,
                    "observacao": "",
                }
            ],
        }
        res2 = client.post("/pedidos", json=payload2)
        assert res2.status_code == 201, res2.text
        data2 = res2.json()
        assert data2["pedido"]["idPedido"] == id_pedido_1

        # 3. Consulta pedido por GET /pedidos/{idPedido}
        res_get = client.get(f"/pedidos/{id_pedido_1}")
        assert res_get.status_code == 200
        data_get = res_get.json()
        assert len(data_get["itens"]) == 2

        # 4. Adiciona itens ao pedido diretamente
        payload_add = [
            {
                "idCardapio": str(pedido_env["item1"]),
                "quantidade": 1,
                "observacao": "Ao ponto",
            }
        ]
        res_add = client.post(f"/pedidos/{id_pedido_1}/itens", json=payload_add)
        assert res_add.status_code == 201
        res_get2 = client.get(f"/pedidos/{id_pedido_1}")
        # 5. Lista pedidos por GET /pedidos (com token de Garcom ou Gerente)
        token_garcom = security.criar_token(
            pedido_env["garcom"].idUsuario, "Garcom", pedido_env["idRestaurante"]
        )
        res_list = client.get("/pedidos", headers={"Authorization": f"Bearer {token_garcom}"})
        assert res_list.status_code == 200, res_list.text
        pedidos_list = res_list.json()
        assert len(pedidos_list) == 1
        assert pedidos_list[0]["idPedido"] == id_pedido_1
        assert pedidos_list[0]["numeroMesa"] == 10
        assert len(pedidos_list[0]["itens"]) == 3

        # Teste com filtro tipo=ativos
        res_ativos = client.get("/pedidos?tipo=ativos", headers={"Authorization": f"Bearer {token_garcom}"})
        assert res_ativos.status_code == 200
        assert len(res_ativos.json()) == 1

        # Teste com filtro tipo=historico (deve vir vazio pois está aberto)
        res_hist = client.get("/pedidos?tipo=historico", headers={"Authorization": f"Bearer {token_garcom}"})
        assert res_hist.status_code == 200
        assert len(res_hist.json()) == 0

    finally:
        app_module.app.dependency_overrides.clear()

