from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.schemas.AuthSchema import LoginRequest, TokenResponse
from src.services.AuthService import AuthService

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login",
    description="Autentica um funcionário e retorna um token JWT contendo seu perfil.",
)
def login(dados: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    service = AuthService(db)
    return service.login(dados)