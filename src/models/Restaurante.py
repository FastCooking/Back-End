from typing import List, Optional
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship, Session
from src.database.connection import Base


class Restaurante(Base):
    __tablename__ = "Restaurante"

    idRestaurante : int = Column(Integer, primary_key=True, autoincrement=True)
    nome : str = Column(String(255), nullable=False)
    cnpj : str = Column(String(18), unique=True, nullable=False)
    telefone : str = Column(String(15), nullable=False)
    email : str = Column(String(255), unique=True, nullable=False)
    cep : str =  Column(String(9), nullable=False)
    status : bool =  Column(Boolean, nullable=False, default=True)

    # Relacionamentos
    usuarios = relationship("Usuario", back_populates="restaurante", cascade="all, delete-orphan")
    mesas = relationship("Mesa", back_populates="restaurante", cascade="all, delete-orphan")
    pedidos = relationship("Pedido", back_populates="restaurante", cascade="all, delete-orphan")
    cardapio = relationship("Cardapio", back_populates="restaurante", cascade="all, delete-orphan")
    estoque = relationship("Estoque", back_populates="restaurante", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Restaurante(id={self.idRestaurante}, nome='{self.nome}')>"

    @classmethod
    def create(cls, db: Session, nome: str, cnpj: str, telefone: str, email: str, cep: str, status: bool) -> "Restaurante":
        """Cria e persiste um novo restaurante."""
        restaurante = cls(
            nome = nome,
            cnpj = cnpj,
            telefone = telefone,
            email = email,
            cep = cep,
            status = status
        )
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

    def update(self, db: Session, nome: str = None, cnpj: str = None, telefone: str = None, email: str = None, cep: str = None, status: bool = None) -> "Restaurante":
        """Atualiza os dados do restaurante."""
        if nome is not None:
            self.nome = nome
        if cnpj is not None:
            self.cnpj = cnpj
        if telefone is not None:
            self.telefone = telefone
        if email is not None:
            self.email = email
        if cep is not None:
            self.cep = cep
        if status is not None:
            self.status = status

        db.commit()
        db.refresh(self)
        return self
    
    def able(self, db: Session) -> "Restaurante":
        """Atualiza os dados do restaurante."""
        self.status = True
        db.commit()
        db.refresh(self)
        return self

    def disable(self, db: Session) -> "Restaurante":
        """Atualiza os dados do restaurante."""
        self.status = False
        db.commit()
        db.refresh(self)
        return self