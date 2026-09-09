import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.models.Usuario import Usuario

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
EXPIRA_EM_MINUTOS = 60

security_scheme = HTTPBearer()


def criar_token(idUsuario: int, funcao: str) -> str:
    """Gera um JWT contendo o id e o perfil do funcionário."""
    expira = datetime.now(timezone.utc) + timedelta(minutes=EXPIRA_EM_MINUTOS)
    payload = {"sub": str(idUsuario), "funcao": funcao, "exp": expira}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credenciais: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Decodifica o token e retorna o Usuario autenticado."""
    excecao_credenciais = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credenciais.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        idUsuario = payload.get("sub")
        if idUsuario is None:
            raise excecao_credenciais
    except JWTError:
        raise excecao_credenciais

    usuario = Usuario.get_by_id(db, int(idUsuario))
    if usuario is None or not usuario.status:
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