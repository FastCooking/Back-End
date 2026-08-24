import os
from dotenv import load_dotenv
from database.connection import Database
from fastapi import FastAPI
import uvicorn

app = FastAPI()

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
    }

    return varsEnv

def envTest(env: dict):
    """
    Verifica se todas as variáveis de ambiente foram carregadas.
    """

    for key, value in env.items():
        if value is None:
            raise EnvironmentError(
                f"[ERRO] A variável de ambiente '{key}' não foi encontrada."
            )

    print("[OK] Variáveis de ambiente carregadas.")

if __name__ == "__main__":
    varsEnv = getVarsEnv()
    envTest(varsEnv)

    db = Database(varsEnv["DATABASE_URL"])
    db.test_connection()

    uvicorn.run("app:app",host="127.0.0.1",port=int(varsEnv["SERVER_PORT"]),reload=True)