import os
import uuid
from io import BytesIO

import qrcode
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.Mesa import Mesa


class QrCodeService:
    def __init__(self, db: Session):
        self.db = db

    def gerar_qrcode(self, idMesa: uuid.UUID | str, origin: str | None = None) -> BytesIO:
        mesa = Mesa.get_by_id(self.db, idMesa)

        if mesa is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mesa com ID {idMesa} não encontrada.",
            )

        base_url = (
            origin
            or os.getenv(
                "FRONTEND_BASE_URL",
                "https://fastcooking-front-end.vercel.app",
            )
        ).rstrip("/")

        url = f"{base_url}/cardapio?idMesa={mesa.idMesa}&idRestaurante={mesa.idRestaurante}&mesa={mesa.numero}"

        imagem = qrcode.make(url)
        arquivo = BytesIO()
        imagem.save(arquivo, format="PNG")
        arquivo.seek(0)

        return arquivo