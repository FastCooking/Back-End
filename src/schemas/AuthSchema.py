import uuid
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: str
    senha: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    funcao: str
    idUsuario: uuid.UUID | None = None
    idRestaurante: uuid.UUID | None = None
    nome: str | None = None