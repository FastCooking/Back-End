import io
import uuid
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import app as app_module
from src.core import security
from src.database.connection import Base, get_db
from src.models.Restaurante import Restaurante


@pytest.fixture
def cardapio_env(tmp_path, monkeypatch):
    monkeypatch.setattr(security, "SECRET_KEY", "cardapio-img-test-secret")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'cardapio_img.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as db:
        rest = Restaurante(
            nome="Restaurante Cardápio Img",
            cnpj="11.111.111/0001-11",
            telefone="11999999999",
            email="rcimg@example.test",
            cep="01001-000",
            status=True,
        )
        db.add(rest)
        db.commit()

        yield {
            "session_factory": session_factory,
            "idRestaurante": rest.idRestaurante,
        }


def _gerar_imagem_bytes():
    img = Image.new("RGB", (200, 200), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def test_criar_e_editar_item_com_upload_de_imagem(cardapio_env):
    def override_get_db():
        with cardapio_env["session_factory"]() as db:
            yield db

    app_module.app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app_module.app)

    try:
        # 1. Cria item via multipart com upload de imagem
        img_buffer = _gerar_imagem_bytes()
        files = {
            "file": ("prato_teste.jpg", img_buffer, "image/jpeg"),
        }
        data = {
            "nome": "Prato com Foto",
            "preco": "45.90",
            "categoria": "Pratos principais",
            "descricao": "Delicioso prato com foto real",
            "idRestaurante": str(cardapio_env["idRestaurante"]),
        }

        resp = client.post("/cardapio", data=data, files=files)
        assert resp.status_code == 201, resp.text
        criado = resp.json()
        assert criado["nome"] == "Prato com Foto"
        assert criado["pathImage"] is not None
        assert criado["pathImage"].startswith("/uploads/cardapio/")
        id_cardapio = criado["idCardapio"]

        # 2. Edita item via multipart enviando nova foto
        nova_img = _gerar_imagem_bytes()
        new_files = {
            "file": ("nova_foto.jpg", nova_img, "image/jpeg"),
        }
        new_data = {
            "nome": "Prato com Foto Atualizada",
            "preco": "49.90",
        }
        edit_resp = client.put(f"/cardapio/{id_cardapio}", data=new_data, files=new_files)
        assert edit_resp.status_code == 200, edit_resp.text
        atualizado = edit_resp.json()
        assert atualizado["nome"] == "Prato com Foto Atualizada"
        assert atualizado["preco"] == 49.90
        assert atualizado["pathImage"] is not None

        # 3. Exclui o item (remoção lógica e remoção da foto do disco)
        del_resp = client.delete(f"/cardapio/{id_cardapio}")
        assert del_resp.status_code == 200

    finally:
        app_module.app.dependency_overrides.clear()
