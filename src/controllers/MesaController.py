from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.core.security import exigir_funcao
from src.database.connection import get_db
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Usuario import Usuario
from src.schemas.MesaSchema import MesaCreate, MesaResponse, MesaUpdate
from src.services.QrCodeService import QrCodeService
from src.services.SessaoService import SessaoService

router = APIRouter(prefix="/mesas", tags=["Mesas"])


@router.get(
    "",
    response_model=list[MesaResponse],
    summary="Listar mesas",
    description="Retorna a lista de mesas cadastradas no restaurante informado.",
)
def listar_mesas(
    idRestaurante: UUID = Query(..., description="ID do restaurante"),
    status: str | None = Query(None, description="Filtro opcional por status"),
    db: Session = Depends(get_db),
):
    mesas = Mesa.get_all_by_restaurant(db, idRestaurante, status)
    return mesas


@router.post(
    "",
    response_model=MesaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar nova mesa",
)
def criar_mesa(
    dados: MesaCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
):
    existente = Mesa.get_by_number(db, dados.idRestaurante, dados.numero)
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mesa número {dados.numero} já cadastrada neste restaurante.",
        )
    mesa = Mesa.create(
        db,
        idRestaurante=dados.idRestaurante,
        numero=dados.numero,
        status=dados.status,
    )
    return mesa


@router.get(
    "/{idMesa}",
    response_model=MesaResponse,
    summary="Obter detalhes da mesa",
)
def obter_mesa(
    idMesa: UUID,
    db: Session = Depends(get_db),
):
    mesa = Mesa.get_by_id(db, idMesa)
    if not mesa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mesa não encontrada.",
        )
    return mesa


@router.put(
    "/{idMesa}",
    response_model=MesaResponse,
    summary="Atualizar dados da mesa",
)
def atualizar_mesa(
    idMesa: UUID,
    dados: MesaUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
):
    mesa = Mesa.get_by_id(db, idMesa)
    if not mesa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mesa não encontrada.",
        )
    if dados.numero is not None and dados.numero != mesa.numero:
        existente = Mesa.get_by_number(db, mesa.idRestaurante, dados.numero)
        if existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Mesa número {dados.numero} já existe neste restaurante.",
            )
    mesa.update(db, numero=dados.numero, status=dados.status)
    return mesa


@router.delete(
    "/{idMesa}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir mesa",
)
def excluir_mesa(
    idMesa: UUID,
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
):
    mesa = Mesa.get_by_id(db, idMesa)
    if not mesa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mesa não encontrada.",
        )
    mesa.delete(db)


@router.get(
    "/{idMesa}/qrcode",
    summary="Gerar QR Code da mesa",
    description="Retorna uma imagem PNG com a URL de autoatendimento da mesa.",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Imagem do QR Code.",
        },
        404: {"description": "Mesa não encontrada."},
    },
)
def gerar_qrcode_mesa(
    idMesa: UUID,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
):
    arquivo = QrCodeService(db).gerar_qrcode(idMesa)

    return StreamingResponse(
        arquivo,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="mesa-{idMesa}-qrcode.png"'
        },
    )


@router.post("/{idMesa}/abrir")
def abrir_mesa(
    idMesa: UUID,
    db: Session = Depends(get_db),
):
    sessao = SessaoService.abrir_mesa(db, idMesa)
    mesa = Mesa.get_by_id(db, idMesa)
    pedido_ativo = Pedido.get_active_for_table(db, idMesa) if mesa else None

    return {
        "idMesa": str(sessao.idMesa),
        "idSessao": str(sessao.idSessao),
        "status": sessao.status,
        "idRestaurante": str(mesa.idRestaurante) if mesa else None,
        "numero": mesa.numero if mesa else None,
        "idPedidoAtivo": str(pedido_ativo.idPedido) if pedido_ativo else None,
    }


@router.post("/sessoes/expirar-inativas")
def expirar_sessoes_inativas(
    limite_minutos: int = Query(default=10, ge=1, le=1440),
    db: Session = Depends(get_db),
):
    expiradas = SessaoService.expirar_sessoes_inativas(db, limite_minutos)
    return {
        "message": f"{len(expiradas)} sessões inativas expiradas com sucesso.",
        "totalExpiradas": len(expiradas),
        "sessoes": [str(s.idSessao) for s in expiradas],
    }