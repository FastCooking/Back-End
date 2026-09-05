import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from src.controllers.CardapioController import router as cardapio_router
from src.controllers.EstoqueController import router as estoque_router
from src.controllers.FichaTecnicaController import router as ficha_tecnica_router
from src.database.connection import Database, init_db

app = FastAPI()
init_db()
app.include_router(cardapio_router)
app.include_router(estoque_router)
app.include_router(ficha_tecnica_router)


@app.get("/")
async def test():
    return "Hello World"


def getVarsEnv():
    """
    Carrega todas as variáveis de ambiente foram carregadas.
    """
    load_dotenv()

    varsEnv = {
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "BCRYPT_ROUNDS": os.getenv("BCRYPT_ROUNDS"),
        "SERVER_PORT": os.getenv("SERVER_PORT"),
        "JWT_SECRET": os.getenv("JWT_SECRET"),
    }

    return varsEnv


def envTest(env: dict):
    """
    Verifica se todas as variáveis de ambiente foram carregadas.
    """

    for key, value in env.items():
        if value is None:
            raise OSError(f"[ERRO] A variável de ambiente '{key}' não foi encontrada.")

    print("[OK] Variáveis de ambiente carregadas.")


if __name__ == "__main__":
    varsEnv = getVarsEnv()
    envTest(varsEnv)

    db = Database(varsEnv["DATABASE_URL"])
    db.test_connection()

    uvicorn.run(
        "app:app", host="127.0.0.1", port=int(varsEnv["SERVER_PORT"]), reload=True
    )
