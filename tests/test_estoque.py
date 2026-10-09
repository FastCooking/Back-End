import uuid

from fastapi.testclient import TestClient

from src.app import app
from src.database.connection import SessionLocal
from src.models.Restaurante import Restaurante

client = TestClient(app)


def _obter_ou_criar_restaurante() -> uuid.UUID:
    session = SessionLocal()
    try:
        restaurante = session.query(Restaurante).first()
        if not restaurante:
            restaurante = Restaurante(
                nome="Restaurante Teste Estoque",
                cnpj="12.345.678/0001-90",
                telefone="(11) 98765-4321",
                email="estoque_restaurante@teste.com",
                cep="01001-000",
                status=True,
            )
            session.add(restaurante)
            session.commit()
            session.refresh(restaurante)
        return restaurante.idRestaurante
    finally:
        session.close()


def test_create_insumo_via_api():
    id_restaurante = _obter_ou_criar_restaurante()
    payload = {
        "idRestaurante": str(id_restaurante),
        "nome": "Tomate",
        "quantidadeEmEstoque": 20.5,
        "quantidadeMinima": 5,
    }

    response = client.post("/insumos", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["nome"] == "Tomate"
    assert data["quantidadeEmEstoque"] == 20.5
    assert data["quantidadeMinima"] == 5


def test_create_insumo_rejeita_quantidade_negativa():
    id_restaurante = _obter_ou_criar_restaurante()
    payload = {
        "idRestaurante": str(id_restaurante),
        "nome": "Cebola",
        "quantidadeEmEstoque": -1,
        "quantidadeMinima": 2,
    }

    response = client.post("/insumos", json=payload)

    assert response.status_code == 422


def test_get_insumo_por_id():
    id_restaurante = _obter_ou_criar_restaurante()
    payload = {
        "idRestaurante": str(id_restaurante),
        "nome": "Alho",
        "quantidadeEmEstoque": 12,
        "quantidadeMinima": 3,
    }

    created = client.post("/insumos", json=payload)
    insumo_id = created.json()["idEstoque"]

    response = client.get(f"/insumos/{insumo_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["idEstoque"] == insumo_id
    assert data["nome"] == "Alho"


def test_listar_insumos():
    id_restaurante = _obter_ou_criar_restaurante()
    client.post(
        "/insumos",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Tomate",
            "quantidadeEmEstoque": 20.5,
            "quantidadeMinima": 5,
        },
    )

    response = client.get("/insumos")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(item["nome"] == "Tomate" for item in data)


def test_create_ficha_tecnica():
    id_restaurante = _obter_ou_criar_restaurante()
    item = client.post(
        "/insumos",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Queijo",
            "quantidadeEmEstoque": 50,
            "quantidadeMinima": 10,
        },
    )
    item_id = item.json()["idEstoque"]

    cardapio = client.post(
        "/cardapio",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Pizza Teste",
            "preco": 49.9,
            "categoria": "Pizzas",
            "pathImage": "teste.png",
            "descricao": "pizza teste",
        },
    )
    cardapio_id = cardapio.json()["idCardapio"]

    payload = {
        "idCardapio": cardapio_id,
        "insumos": [{"idEstoque": item_id, "quantidadeNecessaria": 0.5}],
    }

    response = client.post("/fichas-tecnica", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["idCardapio"] == cardapio_id
    assert data["insumos"][0]["idEstoque"] == item_id


def test_update_ficha_tecnica():
    id_restaurante = _obter_ou_criar_restaurante()
    item = client.post(
        "/insumos",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Tomate",
            "quantidadeEmEstoque": 30,
            "quantidadeMinima": 5,
        },
    )
    item_id = item.json()["idEstoque"]

    cardapio = client.post(
        "/cardapio",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Pizza Atualizacao",
            "preco": 55.0,
            "categoria": "Pizzas",
            "pathImage": "pizza.png",
            "descricao": "pizza atualizacao",
        },
    )
    cardapio_id = cardapio.json()["idCardapio"]

    first = client.post(
        "/fichas-tecnica",
        json={
            "idCardapio": cardapio_id,
            "insumos": [{"idEstoque": item_id, "quantidadeNecessaria": 0.5}],
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/fichas-tecnica",
        json={
            "idCardapio": cardapio_id,
            "insumos": [{"idEstoque": item_id, "quantidadeNecessaria": 2.0}],
        },
    )

    assert second.status_code == 200
    data = second.json()
    assert data["idCardapio"] == cardapio_id
    assert data["insumos"][0]["quantidadeNecessaria"] == 2.0


def test_ficha_tecnica_cardapio_inexistente():
    payload = {
        "idCardapio": str(uuid.uuid4()),
        "insumos": [{"idEstoque": str(uuid.uuid4()), "quantidadeNecessaria": 1.0}],
    }

    response = client.post("/fichas-tecnica", json=payload)

    assert response.status_code == 404


def test_ficha_tecnica_insumo_inexistente():
    id_restaurante = _obter_ou_criar_restaurante()
    cardapio = client.post(
        "/cardapio",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Pizza Insumo Inexistente",
            "preco": 30.0,
            "categoria": "Pizzas",
            "pathImage": "inexistente.png",
            "descricao": "insumo inexistente",
        },
    )
    cardapio_id = cardapio.json()["idCardapio"]

    payload = {
        "idCardapio": cardapio_id,
        "insumos": [{"idEstoque": str(uuid.uuid4()), "quantidadeNecessaria": 1.0}],
    }

    response = client.post("/fichas-tecnica", json=payload)

    assert response.status_code == 404


def test_ficha_tecnica_quantidade_invalida():
    id_restaurante = _obter_ou_criar_restaurante()
    item = client.post(
        "/insumos",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Alho",
            "quantidadeEmEstoque": 15,
            "quantidadeMinima": 5,
        },
    )
    item_id = item.json()["idEstoque"]

    cardapio = client.post(
        "/cardapio",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Pizza Quantidade",
            "preco": 44.0,
            "categoria": "Pizzas",
            "pathImage": "q.png",
            "descricao": "quantidade invalida",
        },
    )
    cardapio_id = cardapio.json()["idCardapio"]

    response = client.post(
        "/fichas-tecnica",
        json={
            "idCardapio": cardapio_id,
            "insumos": [{"idEstoque": item_id, "quantidadeNecessaria": 0}],
        },
    )

    assert response.status_code == 422


def test_ficha_tecnica_insumos_duplicados():
    id_restaurante = _obter_ou_criar_restaurante()
    item = client.post(
        "/insumos",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Cebola",
            "quantidadeEmEstoque": 20,
            "quantidadeMinima": 5,
        },
    )
    item_id = item.json()["idEstoque"]

    cardapio = client.post(
        "/cardapio",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Pizza Duplicada",
            "preco": 50.0,
            "categoria": "Pizzas",
            "pathImage": "dup.png",
            "descricao": "duplicada",
        },
    )
    cardapio_id = cardapio.json()["idCardapio"]

    response = client.post(
        "/fichas-tecnica",
        json={
            "idCardapio": cardapio_id,
            "insumos": [
                {"idEstoque": item_id, "quantidadeNecessaria": 1.0},
                {"idEstoque": item_id, "quantidadeNecessaria": 2.0},
            ],
        },
    )

    assert response.status_code == 422


def test_buscar_ficha_tecnica_por_id_retorna_apenas_esse_vinculo():
    id_restaurante = _obter_ou_criar_restaurante()
    item = client.post(
        "/insumos",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Azeite",
            "quantidadeEmEstoque": 12,
            "quantidadeMinima": 2,
        },
    )
    item_id = item.json()["idEstoque"]

    cardapio = client.post(
        "/cardapio",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Pizza Azeite",
            "preco": 58.0,
            "categoria": "Pizzas",
            "pathImage": "azeite.png",
            "descricao": "pizza azeite",
        },
    )
    cardapio_id = cardapio.json()["idCardapio"]

    created = client.post(
        "/fichas-tecnica",
        json={
            "idCardapio": cardapio_id,
            "insumos": [
                {"idEstoque": item_id, "quantidadeNecessaria": 0.6},
                {"idEstoque": str(uuid.uuid4()), "quantidadeNecessaria": 0.2},
            ],
        },
    )
    assert created.status_code == 404

    created = client.post(
        "/fichas-tecnica",
        json={
            "idCardapio": cardapio_id,
            "insumos": [{"idEstoque": item_id, "quantidadeNecessaria": 0.6}],
        },
    )
    assert created.status_code == 201

    ficha_id = created.json()["idFichaTecnica"]
    response = client.get(f"/fichas-tecnica/{ficha_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["idCardapio"] == cardapio_id
    assert len(data["insumos"]) == 1
    assert data["insumos"][0]["idEstoque"] == item_id


def test_buscar_ficha_tecnica_completa_do_cardapio():
    id_restaurante = _obter_ou_criar_restaurante()
    item1 = client.post(
        "/insumos",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Queijo",
            "quantidadeEmEstoque": 50,
            "quantidadeMinima": 10,
        },
    )
    item2 = client.post(
        "/insumos",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Molho",
            "quantidadeEmEstoque": 25,
            "quantidadeMinima": 8,
        },
    )

    cardapio = client.post(
        "/cardapio",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Pizza Completa",
            "preco": 60.0,
            "categoria": "Pizzas",
            "pathImage": "completa.png",
            "descricao": "pizza completa",
        },
    )
    cardapio_id = cardapio.json()["idCardapio"]

    client.post(
        "/fichas-tecnica",
        json={
            "idCardapio": cardapio_id,
            "insumos": [
                {"idEstoque": item1.json()["idEstoque"], "quantidadeNecessaria": 0.5},
                {"idEstoque": item2.json()["idEstoque"], "quantidadeNecessaria": 0.25},
            ],
        },
    )

    response = client.get(f"/fichas-tecnica/cardapio/{cardapio_id}/completa")

    assert response.status_code == 200
    data = response.json()
    assert data["cardapio"]["idCardapio"] == cardapio_id
    assert data["cardapio"]["nome"] == "Pizza Completa"
    assert len(data["insumos"]) == 2
    assert {item["nome"] for item in data["insumos"]} == {"Queijo", "Molho"}


def test_buscar_ficha_tecnica_completa_cardapio_inexistente():
    response = client.get(f"/fichas-tecnica/cardapio/{uuid.uuid4()}/completa")

    assert response.status_code == 404


def test_buscar_ficha_tecnica_completa_sem_ficha():
    id_restaurante = _obter_ou_criar_restaurante()
    cardapio = client.post(
        "/cardapio",
        json={
            "idRestaurante": str(id_restaurante),
            "nome": "Sem Ficha",
            "preco": 20.0,
            "categoria": "Lanches",
            "pathImage": "sem.png",
            "descricao": "sem ficha",
        },
    )
    cardapio_id = cardapio.json()["idCardapio"]

    response = client.get(f"/fichas-tecnica/cardapio/{cardapio_id}/completa")

    assert response.status_code == 200
    data = response.json()
    assert data["cardapio"]["idCardapio"] == cardapio_id
    assert data["insumos"] == []
