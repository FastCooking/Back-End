import os
from io import BytesIO

import qrcode
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.Mesa import Mesa


class QrCodeService:
    def __init__(self, db: Session):
        self.db = db

    def gerar_qrcode(self, idMesa: int) -> BytesIO:
        mesa = Mesa.get_by_id(self.db, idMesa)

        if mesa is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mesa com ID {idMesa} não encontrada.",
            )

        base_url = os.getenv(
            "FRONTEND_BASE_URL",
            "http://localhost:5173",
        ).rstrip("/")

        url = f"{base_url}/autoatendimento/mesa/{mesa.idMesa}"

        imagem = qrcode.make(url)
        arquivo = BytesIO()
        imagem.save(arquivo, format="PNG")
        arquivo.seek(0)

        return arquivo