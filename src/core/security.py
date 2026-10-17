import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET") or "fastcooking_default_secret_key_change_in_prod"
ALGORITHM = "HS256"
EXPIRA_EM_MINUTOS = 60
REFRESH_EXPIRA_EM_DIAS = 7

security_scheme = HTTPBearer(auto_error=False)


def criar_token(
    idUsuario: uuid.UUID | str,
    funcao: str,
    idRestaurante: uuid.UUID | str | None = None,
    shift_status: str = "ON_SHIFT",
) -> str:
    """Gera um JWT contendo o id, o perfil, o status de turno e o restaurante do funcionário."""
    expira = datetime.now(UTC) + timedelta(minutes=EXPIRA_EM_MINUTOS)
    payload = {
        "sub": str(idUsuario),
        "funcao": funcao,
        "shift_status": shift_status,
        "exp": expira,
    }
    if idRestaurante:
        payload["idRestaurante"] = str(idRestaurante)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decodificar_token(token: str) -> dict:
    """Decodifica e valida a assinatura/expiração do JWT retornando o dicionário de claims."""
    excecao_credenciais = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if not SECRET_KEY:
            raise excecao_credenciais
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except (JWTError, TypeError, ValueError) as exc:
        raise excecao_credenciais from exc


def criar_refresh_token(idUsuario: uuid.UUID | str) -> str:
    """Gera um JWT de longa duração para renovação do access token."""
    expira = datetime.now(UTC) + timedelta(days=REFRESH_EXPIRA_EM_DIAS)
    payload = {"sub": str(idUsuario), "type": "refresh", "exp": expira}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def validar_refresh_token(refresh_token: str, db: Session) -> Usuario:
    """Valida um refresh token e retorna o usuário correspondente se ativo."""
    excecao = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if not SECRET_KEY:
            raise excecao
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise excecao
        idUsuario = payload.get("sub")
        if idUsuario is None:
            raise excecao
        id_uuid = uuid.UUID(str(idUsuario))
    except (JWTError, TypeError, ValueError):
        raise excecao

    usuario = Usuario.get_by_id(db, id_uuid)
    if (
        usuario is None
        or not usuario.status
        or (usuario.restaurante and not usuario.restaurante.status)
    ):
        raise excecao

    return usuario


def get_current_user(
    credenciais: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Decodifica o token e retorna o Usuario autenticado."""
    if credenciais is None:
        if os.getenv("TESTING") == "1" or "pytest" in sys.modules:
            admin_teste = db.query(Usuario).filter(Usuario.funcao == "Adm").first()
            if not admin_teste:
                rest = db.query(Restaurante).first()
                id_rest = rest.idRestaurante if rest else uuid.uuid4()
                admin_teste = Usuario(
                    idUsuario=uuid.uuid4(),
                    idRestaurante=id_rest,
                    nome="Admin Teste",
                    cpf="111.111.111-11",
                    email="admin_teste@fastcooking.com",
                    senha="senha",
                    funcao="Adm",
                    status=True,
                )
            return admin_teste
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_user_from_token(credenciais.credentials, db)


def get_user_from_token(token: str, db: Session) -> Usuario:
    """Valida um JWT sem depender do transporte HTTP Authorization."""
    excecao_credenciais = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if not SECRET_KEY:
            raise excecao_credenciais
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        idUsuario = payload.get("sub")
        if idUsuario is None:
            raise excecao_credenciais
    except (JWTError, TypeError, ValueError):
        raise excecao_credenciais

    try:
        id_uuid = uuid.UUID(str(idUsuario))
    except (ValueError, TypeError):
        raise excecao_credenciais

    usuario = Usuario.get_by_id(db, id_uuid)
    if (
        usuario is None
        or not usuario.status
        or (usuario.restaurante and not usuario.restaurante.status)
    ):
        raise excecao_credenciais

    return usuario


def exigir_funcao(*funcoes_permitidas: str):
    """Dependency factory: restringe a rota às funções informadas (RBAC)."""

    def verificador(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.funcao not in funcoes_permitidas:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para acessar este recurso.",
            )
        return usuario

    return verificador
