import uuid
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    funcao: str
    idUsuario: uuid.UUID | None = None
    idRestaurante: uuid.UUID | None = None
    nome: str | None = None