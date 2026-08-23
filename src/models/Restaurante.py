from typing import List, Optional
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, Session
from src.database.connection import Base


class Restaurante(Base):
    __tablename__ = "Restaurante"

    idRestaurante = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(255), nullable=False)

    # Relacionamentos
    usuarios = relationship("Funcionario", back_populates="restaurante", cascade="all, delete-orphan")
    mesas = relationship("Mesa", back_populates="restaurante", cascade="all, delete-orphan")
    pedidos = relationship("Pedido", back_populates="restaurante", cascade="all, delete-orphan")
    cardapio = relationship("ItemCardapio", back_populates="restaurante", cascade="all, delete-orphan")
    estoque = relationship("Insumo", back_populates="restaurante", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Restaurante(id={self.idRestaurante}, nome='{self.nome}')>"

    # =====================================================================
    # Operações com o Banco de Dados (CRUD / Acesso a Dados)
    # =====================================================================

    @classmethod
    def create(cls, db: Session, nome: str) -> "Restaurante":
        """Cria e persiste um novo restaurante."""
        restaurante = cls(nome=nome)
        db.add(restaurante)
        db.commit()
        db.refresh(restaurante)
        return restaurante

    @classmethod
    def get_by_id(cls, db: Session, idRestaurante: int) -> Optional["Restaurante"]:
        """Busca um restaurante pelo ID."""
        return db.query(cls).filter(cls.idRestaurante == idRestaurante).first()

    @classmethod
    def get_all(cls, db: Session) -> List["Restaurante"]:
        """Retorna todos os restaurantes cadastrados."""
        return db.query(cls).all()

    def update(self, db: Session, nome: str = None) -> "Restaurante":
        """Atualiza os dados do restaurante."""
        if nome is not None:
            self.nome = nome
        db.commit()
        db.refresh(self)
        return self

    def delete(self, db: Session) -> bool:
        """Remove o restaurante do banco de dados."""
        db.delete(self)
        db.commit()
        return True
