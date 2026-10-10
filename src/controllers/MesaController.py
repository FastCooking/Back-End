from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from uuid import UUID

from src.core.security import exigir_funcao
from src.database.connection import get_db
from src.models.Usuario import Usuario
from src.services.QrCodeService import QrCodeService
from src.services.SessaoService import SessaoService

router = APIRouter(prefix="/mesas", tags=["Mesas"])


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
    idMesa: int,
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

    return {
        "idMesa": str(sessao.idMesa),
        "idSessao": str(sessao.idSessao),
        "status": sessao.status,
    }