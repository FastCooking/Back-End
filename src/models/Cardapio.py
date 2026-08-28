from typing import List, Optional
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship, Session
from src.database.connection import Base


class Cardapio(Base):
    __tablename__ = "Cardapio"

    idCardapio : int = Column(Integer, primary_key=True, autoincrement=True)
    idRestaurante : int = Column(Integer, ForeignKey("Restaurante.idRestaurante", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    nome : str = Column(String(150), nullable=False)
    pathImage : str = Column(Text, nullable=True)
    descricao : str = Column(Text, nullable=True)
    preco : float = Column(Numeric(10, 2), nullable=False)
    categoria : str = Column(String(100), nullable=False)
    status : bool = Column(Boolean, nullable=False, default=True)

    # Relacionamentos
    restaurante = relationship("Restaurante", back_populates="cardapio")
    itens_pedido = relationship("ItemPedido", back_populates="cardapio")
    fichas_tecnicas = relationship("FichaTecnica", back_populates="cardapio", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Cardapio(id={self.idCardapio}, nome='{self.nome}', pathImage='{self.pathImage}', preco={self.preco}, status={self.status})>"

    @classmethod
    def create(cls, db: Session, idRestaurante: int, nome: str, preco: float, categoria: str, pathImage: str, descricao: Optional[str] = None, status: bool = True) -> "Cardapio":
        """Cria um novo item de cardápio."""
        item = cls(
            idRestaurante=idRestaurante,
            nome=nome,
            preco=preco,
            categoria=categoria,
            pathImage=pathImage,
            descricao=descricao,
            status=status
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @classmethod
    def get_by_id(cls, db: Session, idCardapio: int) -> Optional["Cardapio"]:
        """Busca item do cardápio pelo ID."""
        return db.query(cls).filter(cls.idCardapio == idCardapio).first()

    @classmethod
    def get_all_by_restaurante(cls, db: Session, idRestaurante: int, apenas_ativos: bool = False, categoria: Optional[str] = None) -> List["Cardapio"]:
        """Lista itens do cardápio de um restaurante com filtros opcionais."""
        query = db.query(cls).filter(cls.idRestaurante == idRestaurante)
        if apenas_ativos:
            query = query.filter(cls.status == True)
        if categoria:
            query = query.filter(cls.categoria == categoria)
        return query.order_by(cls.categoria, cls.nome).all()

    def update( self, db: Session, nome: Optional[str] = None, pathImage: Optional[str] = None, descricao: Optional[str] = None, preco: Optional[float] = None, categoria: Optional[str] = None, status: Optional[bool] = None) -> "Cardapio":
        """Atualiza os dados de um item do cardápio."""
        if nome is not None:
            self.nome = nome
        if pathImage is not None:
            self.descricao = descricao
        if descricao is not None:
            self.pathImage = pathImage
        if preco is not None:
            self.preco = preco
        if categoria is not None:
            self.categoria = categoria
        if status is not None:
            self.status = status

        db.commit()
        db.refresh(self)
        return self

    def disable(self, db: Session) -> bool:
        """Desativa o item do cardápio do banco de dados."""
        self.status = False
        db.commit()
        db.refresh(self)
        return True

    def able(self, db: Session) -> bool:
        """Desativa o item do cardápio do banco de dados."""
        self.status = True
        db.commit()
        db.refresh(self)
        return True

    def delete(self, db: Session) -> bool:
        """Remove o item do cardápio do banco de dados."""
        db.delete(self)
        db.commit()
        return True