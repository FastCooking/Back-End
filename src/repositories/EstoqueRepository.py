import uuid

from sqlalchemy.orm import Session

from src.models.Estoque import Estoque


class EstoqueRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        nome: str,
        quantidadeEmEstoque: float,
        quantidadeMinima: float,
        idRestaurante: uuid.UUID | str,
        unidadeMedida: str = "UN",
        pathImage: str | None = None,
    ) -> Estoque:
        insumo = Estoque(
            idRestaurante=idRestaurante,
            nome=nome,
            unidadeMedida=unidadeMedida,
            pathImage=pathImage,
            quantidadeEstoque=quantidadeEmEstoque,
            quantidadeMinima=quantidadeMinima,
        )
        self.db.add(insumo)
        self.db.commit()
        self.db.refresh(insumo)
        return insumo

    def get_by_id(self, idEstoque: uuid.UUID | str) -> Estoque | None:
        return self.db.query(Estoque).filter(Estoque.idEstoque == idEstoque).first()

    def list_all(self, idRestaurante: uuid.UUID | str | None = None) -> list[Estoque]:
        query = self.db.query(Estoque)
        if idRestaurante is not None:
            query = query.filter(Estoque.idRestaurante == idRestaurante)
        return query.order_by(Estoque.nome.asc()).all()
