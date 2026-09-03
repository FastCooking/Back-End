from typing import Optional

from sqlalchemy import Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Session, relationship

from src.database.connection import Base


class Estoque(Base):
    __tablename__ = "Estoque"

    idEstoque : int = Column(Integer, primary_key=True, autoincrement=True)
    idRestaurante : int = Column(Integer, ForeignKey("Restaurante.idRestaurante", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    nome : str = Column(String(150), nullable=False)
    pathImage : str | None = Column(String(150), nullable=True)
    unidadeMedida : str = Column(String(20), nullable=False)
    quantidadeEstoque : float = Column(Numeric(10, 3), nullable=False, default=0.000)
    quantidadeMinima : float = Column(Numeric(10, 3), nullable=False, default=0.000)

    # Relacionamentos
    restaurante = relationship("Restaurante", back_populates="estoque")
    fichas_tecnicas = relationship("FichaTecnica", back_populates="estoque", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Estoque(id={self.idEstoque}, nome='{self.nome}', saldo={self.quantidadeEstoque} {self.unidadeMedida})>"

    @classmethod
    def create(cls, db: Session, idRestaurante: int, nome: str, unidadeMedida: str, quantidadeEstoque: float = 0.0, quantidadeMinima: float = 0.0) -> "Estoque":
        """Cria e persiste um novo insumo de estoque."""
        insumo = cls(
            idRestaurante=idRestaurante,
            nome=nome,
            unidadeMedida=unidadeMedida,
            quantidadeEstoque=quantidadeEstoque,
            quantidadeMinima=quantidadeMinima
        )
        db.add(insumo)
        db.commit()
        db.refresh(insumo)
        return insumo

    @classmethod
    def get_by_id(cls, db: Session, idEstoque: int) -> Optional["Estoque"]:
        """Busca insumo pelo ID."""
        return db.query(cls).filter(cls.idEstoque == idEstoque).first()

    @classmethod
    def get_all_by_restaurant(cls, db: Session, idRestaurante: int) -> list["Estoque"]:
        """Lista todos os insumos de um restaurante."""
        return db.query(cls).filter(cls.idRestaurante == idRestaurante).order_by(cls.nome).all()

    @classmethod
    def get_less_than_min(cls, db: Session, idRestaurante: int) -> list["Estoque"]:
        """Lista insumos cujo saldo atual está igual ou abaixo do estoque mínimo."""
        return db.query(cls).filter(
            cls.idRestaurante == idRestaurante,
            cls.quantidadeEstoque <= cls.quantidadeMinima
        ).all()

    def update_balance(self, db: Session, nova_quantidade: float) -> "Estoque":
        """Atualiza a quantidade em estoque e persiste a alteração."""
        self.quantidadeEstoque = nova_quantidade
        db.commit()
        db.refresh(self)
        return self

    def update(self, db: Session, nome: str | None = None, quantidadeEstoque: float | None = None, unidadeMedida: str | None = None, quantidadeMinima: float | None = None) -> "Estoque":
        """Atualiza os dados cadastrais do item."""
        if nome is not None:
            self.nome = nome
        if quantidadeEstoque is not None:
            self.quantidadeEstoque = quantidadeEstoque
        if unidadeMedida is not None:
            self.unidadeMedida = unidadeMedida
        if quantidadeMinima is not None:
            self.quantidadeMinima = quantidadeMinima

        db.commit()
        db.refresh(self)
        return self

    def delete(self, db: Session) -> bool:
        """Remove o item do estoque."""
        db.delete(self)
        db.commit()
        return True