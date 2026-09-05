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
        idRestaurante: int = 1,
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

    def get_by_id(self, idEstoque: int) -> Estoque | None:
        return self.db.query(Estoque).filter(Estoque.idEstoque == idEstoque).first()

    def list_all(self) -> list[Estoque]:
        return self.db.query(Estoque).order_by(Estoque.nome.asc()).all()
