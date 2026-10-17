import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request, WebSocket, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Adiciona o diretório raiz do projeto ao sys.path para garantir importações com 'src.'
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import uuid
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session

from src.controllers.AuthController import router as auth_router
from src.controllers.CardapioController import router as cardapio_router
from src.controllers.DeliveryController import router as delivery_router
from src.controllers.EstoqueController import router as estoque_router
from src.controllers.FichaTecnicaController import router as ficha_tecnica_router
from src.controllers.MesaController import router as mesa_router
from src.controllers.PedidoController import router as pedido_router
from src.controllers.RestauranteController import router as restaurante_router
from src.controllers.UsuarioController import router as usuario_router
from src.core.bootstrap import garantir_usuario_admin
from src.database.connection import get_db, test_connection
from src.services.DeliveryService import DeliveryDomainError


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Executa o bootstrap de deploy de forma segura e idempotente
    try:
        garantir_usuario_admin()
    except Exception as exc:  # noqa: BLE001
        print(f"[BOOTSTRAP] Aviso/Erro ao verificar usuário padrão: {exc}")
    yield


app = FastAPI(
    title="FastCooking API",
    description="API do sistema FastCooking para gerenciamento de restaurantes, pedidos, cardápio e estoque.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DeliveryDomainError)
async def delivery_domain_exception_handler(request: Request, exc: DeliveryDomainError):
    """Retorna payload semântico estruturado com código amigável para erros de domínio de entrega."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "error": exc.code,
            "message": exc.message,
            "detail": f"{exc.code}: {exc.message}",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Trata erros de validação: retorna 400 para campos obrigatórios ausentes e 422 para dados inválidos."""
    has_missing = any(err.get("type") == "missing" for err in exc.errors())
    status_code = (
        status.HTTP_400_BAD_REQUEST
        if has_missing
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "message": "Erro de validação: campos obrigatórios ausentes ou inválidos.",
            "detail": jsonable_encoder(exc.errors()),
        },
    )


app.include_router(usuario_router)
app.include_router(restaurante_router)
app.include_router(auth_router)
app.include_router(cardapio_router)
app.include_router(estoque_router)
app.include_router(ficha_tecnica_router)
app.include_router(mesa_router)
app.include_router(pedido_router)
app.include_router(delivery_router)

from fastapi.staticfiles import StaticFiles

uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
try:
    os.makedirs(uploads_dir / "cardapio", exist_ok=True)
except OSError:
    uploads_dir = Path("/tmp/uploads")
    os.makedirs(uploads_dir / "cardapio", exist_ok=True)

if uploads_dir.exists():
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.get("/", tags=["Health Check"])
async def test():
    return {"message": "FastCooking API is running"}


@app.websocket("/ws/tracking/{idPedido}")
async def root_tracking_websocket(
    websocket: WebSocket,
    idPedido: uuid.UUID,
    db: Session = Depends(get_db),
):
    from src.controllers.PedidoController import handle_tracking_websocket
    await handle_tracking_websocket(websocket, idPedido, db)


@app.websocket("/ws/waiters")
async def root_waiters_websocket(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    from src.controllers.PedidoController import handle_waiter_room_websocket
    await handle_waiter_room_websocket(websocket, db)


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
    from src.database.connection import Base, engine
    Base.metadata.create_all(bind=engine)
    test_connection()
    uvicorn.run(
        "src.app:app", host="127.0.0.1", port=int(varsEnv["SERVER_PORT"]), reload=True
    )
