from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from src.core.websocket_manager import kds_ws_manager
from src.database.connection import get_db
from src.schemas.PedidoSchema import PedidoCriarSchema, PedidoResponseSchema
from src.services.PedidoService import PedidoService

router = APIRouter(
    prefix="/pedidos",
    tags=["Pedidos"]
)

@router.post("/", response_model=PedidoResponseSchema, status_code=status.HTTP_201_CREATED)
def criar_pedido(payload: PedidoCriarSchema, db: Session = Depends(get_db)):
    """
    Cria ou atualiza um pedido atrelando itens. Se já existe um pedido
    aberto para a mesma sessao_id, ele anexa os itens à comanda aberta.
    """
    service = PedidoService(db)
    try:
        pedido = service.processar_pedido(payload)
        return pedido
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Erro interno ao processar pedido")



@router.get("/", response_model=list[PedidoResponseSchema], status_code=status.HTTP_200_OK)
def listar_pedidos(db: Session = Depends(get_db)):
    """Lista todos os pedidos abertos/fechados no banco."""
    service = PedidoService(db)
    return service.listar_pedidos()

@router.get("/{pedido_id}", response_model=PedidoResponseSchema, status_code=status.HTTP_200_OK)
def obter_pedido_por_id(pedido_id: int, db: Session = Depends(get_db)):
    """Busca um pedido específico por ID."""
    service = PedidoService(db)
    pedido = service.obter_pedido(pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return pedido

@router.websocket("/kds/ws")
async def websocket_kds_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket para o Kitchen Display System (KDS).
    Conecte clientes (tablets/monitores da cozinha) aqui para receber 
    atualizações em tempo real dos pedidos recém criados.
    """
    await kds_ws_manager.connect(websocket)
    try:
        while True:
            # Mantém a conexão aberta esperando mensagens do cliente se necessário
            # Pode-se implementar ack's ou comandos de mudança de status a partir da cozinha.
            await websocket.receive_text()
    except WebSocketDisconnect:
        kds_ws_manager.disconnect(websocket)
