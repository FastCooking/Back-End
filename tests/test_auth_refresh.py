import pytest

from src.core.security import criar_refresh_token, criar_token
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.services.UsuarioService import hash_senha


@pytest.fixture
def restaurante_fixture(db_session):
    restaurante = Restaurante.create(
        db=db_session,
        nome="Restaurante Teste Auth",
        cnpj="11.222.333/0001-44",
        telefone="(11) 98888-7777",
        email="auth_teste@restaurante.com",
        cep="01001-000",
        status=True,
    )
    return restaurante


@pytest.fixture
def usuario_fixture(db_session, restaurante_fixture):
    usuario = Usuario.create(
        db=db_session,
        idRestaurante=restaurante_fixture.idRestaurante,
        nome="Usuario Auth Test",
        cpf="111.222.333-44",
        email="auth_test@fastcooking.com.br",
        senha=hash_senha("senha12345"),
        funcao="Garcom",
    )
    return usuario


def test_login_retorna_access_e_refresh_token(client, usuario_fixture):
    response = client.post(
        "/auth/login",
        json={"email": "auth_test@fastcooking.com.br", "senha": "senha12345"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] is not None
    assert data["funcao"] == "Garcom"


def test_refresh_token_sucesso(client, usuario_fixture):
    # Primeiro realiza login para obter refresh token
    login_res = client.post(
        "/auth/login",
        json={"email": "auth_test@fastcooking.com.br", "senha": "senha12345"},
    )
    assert login_res.status_code == 200
    refresh_token = login_res.json()["refresh_token"]

    # Chama o endpoint de refresh
    refresh_res = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    data = refresh_res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["funcao"] == "Garcom"


def test_refresh_token_invalido(client):
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "token_invalido_qualquer"},
    )
    assert response.status_code == 401
    assert "Refresh token" in response.json()["detail"]


def test_refresh_token_rejeita_access_token_comum(client, usuario_fixture):
    # Gera um token de acesso normal sem type: refresh
    access_token = criar_token(usuario_fixture.idUsuario, usuario_fixture.funcao)
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert response.status_code == 401


def test_refresh_token_usuario_desativado(client, db_session, usuario_fixture):
    refresh_token = criar_refresh_token(usuario_fixture.idUsuario)
    usuario_fixture.disable(db_session)

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 401
