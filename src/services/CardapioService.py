import io
import os
import uuid
from pathlib import Path
from PIL import Image
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.models.Cardapio import Cardapio
from src.models.FichaTecnica import FichaTecnica
from src.models.Usuario import Usuario
from src.schemas.CardapioSchema import CardapioCreate, CardapioUpdate


class CardapioService:

    def __init__(self, db: Session | None = None):
        self.db = db

    async def salvar_e_comprimir_imagem(self, file: UploadFile) -> str:
        filename_lower = (file.filename or "").lower()
        ext_valida = any(filename_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"])
        is_image_type = bool(file.content_type and file.content_type.startswith("image/"))

        if not (is_image_type or ext_valida):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O arquivo enviado não é uma imagem válida.",
            )

        try:
            conteudo = await file.read()
            img = Image.open(io.BytesIO(conteudo))

            orig_w, orig_h = img.size
            new_w = max(1, int(orig_w * 0.60))
            new_h = max(1, int(orig_h * 0.60))

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            img_comprimida = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            filename = f"cardapio_{uuid.uuid4().hex[:12]}.jpg"
            uploads_dir = Path(__file__).resolve().parents[2] / "uploads" / "cardapio"
            os.makedirs(uploads_dir, exist_ok=True)

            caminho_absoluto = uploads_dir / filename
            img_comprimida.save(caminho_absoluto, "JPEG", quality=85)

            return f"/uploads/cardapio/{filename}"
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao processar imagem: {exc!s}",
            ) from exc

    def _remover_arquivo_imagem(self, path_image: str | None) -> None:
        if not path_image or not path_image.startswith("/uploads/"):
            return
        try:
            relative_path = path_image.lstrip("/")
            uploads_dir = Path(__file__).resolve().parents[2]
            caminho_arquivo = uploads_dir / relative_path
            if os.path.exists(caminho_arquivo):
                os.remove(caminho_arquivo)
        except Exception as err:
            print(f"[AVISO] Não foi possível remover foto antiga: {err}")

    def criar(
        self,
        dados: CardapioCreate,
        usuario: Usuario | None = None,
    ) -> Cardapio:
        id_restaurante = dados.idRestaurante or (usuario.idRestaurante if usuario else 1)

        item = Cardapio.create(
            db=self.db,
            idRestaurante=id_restaurante,
            nome=dados.nome,
            preco=float(dados.preco),
            categoria=dados.categoria,
            pathImage=dados.pathImage,
            descricao=dados.descricao,
        )

        return item

    def listar(
        self,
        idRestaurante: int | None = None,
    ) -> list[Cardapio]:
        if idRestaurante is None:
            idRestaurante = 1

        return Cardapio.get_all_by_restaurante(
            db=self.db,
            idRestaurante=idRestaurante,
        )

    def buscar_por_id(
        self,
        idCardapio: int,
    ) -> Cardapio:
        item = Cardapio.get_by_id(
            db=self.db,
            idCardapio=idCardapio,
        )

        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item do cardápio não encontrado.",
            )

        return item

    def editar(
        self,
        idCardapio: int,
        dados: CardapioUpdate,
        usuario: Usuario | None = None,
    ) -> Cardapio:
        item = self.buscar_por_id(idCardapio)

        if usuario and item.idRestaurante != usuario.idRestaurante:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item do cardápio não encontrado.",
            )

        # Se houver uma nova foto e ela for diferente da antiga, apaga a foto antiga do servidor
        if dados.pathImage is not None and dados.pathImage != item.pathImage:
            self._remover_arquivo_imagem(item.pathImage)

        return item.update(
            db=self.db,
            nome=dados.nome,
            preco=float(dados.preco) if dados.preco is not None else None,
            categoria=dados.categoria,
            pathImage=dados.pathImage,
            descricao=dados.descricao,
        )

    def excluir(
        self,
        idCardapio: int,
        usuario: Usuario | None = None,
    ) -> bool:
        item = self.buscar_por_id(idCardapio)

        if usuario and item.idRestaurante != usuario.idRestaurante:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item do cardápio não encontrado.",
            )

        # Remove as relações na FichaTecnica associadas a este item do cardápio (sem deletar o insumo no estoque)
        if self.db:
            self.db.query(FichaTecnica).filter(FichaTecnica.idCardapio == idCardapio).delete()

        # Remove o arquivo de imagem do disco se existir
        if item.pathImage:
            self._remover_arquivo_imagem(item.pathImage)

        # Exclusão lógica: desativa o item.
        return item.disable(self.db)