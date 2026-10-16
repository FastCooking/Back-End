import os
from src.core.bootstrap import garantir_usuario_admin
from src.models.Usuario import Usuario
from src.services.UsuarioService import verificar_senha


def test_garantir_usuario_admin_cria_quando_nao_existe(db_session, monkeypatch):
    monkeypatch.setenv("DEFAULT_ADMIN_EMAIL", "test_admin@fastcooking.com.br")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "f4stc0oking_test")

    admin = garantir_usuario_admin(db=db_session)
    assert admin is not None
    assert admin.email == "test_admin@fastcooking.com.br"
    assert admin.funcao == "Adm"
    assert verificar_senha("f4stc0oking_test", admin.senha)

    # Verifica persistência no banco
    buscado = Usuario.get_by_email(db_session, "test_admin@fastcooking.com.br")
    assert buscado is not None
    assert buscado.idUsuario == admin.idUsuario


def test_garantir_usuario_admin_idempotente(db_session, monkeypatch):
    monkeypatch.setenv("DEFAULT_ADMIN_EMAIL", "test_admin@fastcooking.com.br")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "f4stc0oking_test")

    admin1 = garantir_usuario_admin(db=db_session)
    admin2 = garantir_usuario_admin(db=db_session)

    assert admin1.idUsuario == admin2.idUsuario

    total_admins = (
        db_session.query(Usuario)
        .filter(Usuario.email == "test_admin@fastcooking.com.br")
        .count()
    )
    assert total_admins == 1


def test_garantir_usuario_admin_sem_senha_ignora(db_session, monkeypatch):
    monkeypatch.delenv("DEFAULT_ADMIN_PASSWORD", raising=False)
    admin = garantir_usuario_admin(db=db_session)
    assert admin is None
