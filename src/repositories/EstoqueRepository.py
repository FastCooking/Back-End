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

    def update(
        self,
        idEstoque: int,
        nome: str | None = None,
        quantidadeEmEstoque: float | None = None,
        quantidadeMinima: float | None = None,
        idRestaurante: int | None = None,
        unidadeMedida: str | None = None,
        pathImage: str | None = None,
    ) -> Estoque | None:
        insumo = self.get_by_id(idEstoque)
        if not insumo:
            return None
        if nome is not None:
            insumo.nome = nome
        if quantidadeEmEstoque is not None:
            insumo.quantidadeEstoque = quantidadeEmEstoque
        if quantidadeMinima is not None:
            insumo.quantidadeMinima = quantidadeMinima
        if idRestaurante is not None:
            insumo.idRestaurante = idRestaurante
        if unidadeMedida is not None:
            insumo.unidadeMedida = unidadeMedida
        if pathImage is not None:
            insumo.pathImage = pathImage

        self.db.commit()
        self.db.refresh(insumo)
        return insumo

    def delete(self, idEstoque: int) -> bool:
        insumo = self.get_by_id(idEstoque)
        if not insumo:
            return False
        self.db.delete(insumo)
        self.db.commit()
        return True
