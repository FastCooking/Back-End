from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.Cardapio import Cardapio
from src.models.Usuario import Usuario
from src.schemas.CardapioSchema import CardapioCreate, CardapioUpdate


class CardapioService:

    def __init__(self, db: Session):
        self.db = db

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

        # Exclusão lógica: desativa o item.
        return item.disable(self.db)