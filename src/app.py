import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Adiciona o diretório raiz do projeto ao sys.path para garantir importações com 'src.'
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.controllers.RestauranteController import router as restaurante_router
from src.controllers.UsuarioController import router as usuario_router
from src.database.connection import test_connection

app = FastAPI(
    title="FastCooking API",
    description="API do sistema FastCooking para gerenciamento de restaurantes, pedidos, cardápio e estoque.",
    version="1.0.0",
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    """Trata erros de validação de campos obrigatórios retornando status 400."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "message": "Erro de validação: campos obrigatórios ausentes ou inválidos.",
            "detail": exc.errors(),
        },
    )

app.include_router(usuario_router)
app.include_router(restaurante_router)


@app.get("/", tags=["Health Check"])
async def test():
    return {"message": "FastCooking API is running"}

def getVarsEnv():
    """
    Carrega todas as variáveis de ambiente foram carregadas.
    """
    load_dotenv()

    varsEnv = {
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "BCRYPT_ROUNDS": os.getenv("BCRYPT_ROUNDS"),
        "SERVER_PORT": os.getenv("SERVER_PORT"),
        "JWT_SECRET": os.getenv("JWT_SECRET")
    }

    return varsEnv

def envTest(env: dict):
    """
    Verifica se todas as variáveis de ambiente foram carregadas.
    """

    for key, value in env.items():
        if value is None:
            raise OSError(
                f"[ERRO] A variável de ambiente '{key}' não foi encontrada."
            )

    print("[OK] Variáveis de ambiente carregadas.")

if __name__ == "__main__":
    varsEnv = getVarsEnv()
    envTest(varsEnv)
    test_connection()
    uvicorn.run("src.app:app", host="127.0.0.1", port=int(varsEnv["SERVER_PORT"]), reload=True)