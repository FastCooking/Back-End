from typing import List, Optional
from sqlalchemy import Column, Integer, String, Numeric, Text, ForeignKey
from sqlalchemy.orm import relationship, Session
from src.database.connection import Base


class ItemPedido(Base):
    """
    Representa um item individual em uma comanda/pedido.
    Contém os mapeamentos ORM e as operações de banco de dados.
    """
    __tablename__ = "ItemPedido"

    idItemPedido = Column(Integer, primary_key=True, autoincrement=True)
    idPedido = Column(Integer, ForeignKey("Pedido.idPedido", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    idCardapio = Column(Integer, ForeignKey("Cardapio.idCardapio", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    quantidade = Column(Integer, nullable=False, default=1)
    precoUnitario = Column(Numeric(10, 2), nullable=False)
    status = Column(String(30), nullable=False, default="Pendente")
    observacao = Column(Text, nullable=True)

    # Relacionamentos
    pedido = relationship("Pedido", back_populates="itens")
    cardapio = relationship("ItemCardapio", back_populates="itens_pedido")

    def __repr__(self):
        return f"<ItemPedido(id={self.idItemPedido}, pedido={self.idPedido}, cardapio={self.idCardapio}, status='{self.status}')>"

    @classmethod
    def create(cls, db: Session, idPedido: int, idCardapio: int, quantidade: int, precoUnitario: float, observacao: Optional[str] = None, status: str = "Pendente") -> "ItemPedido":
        """Cria e persiste um novo item de pedido."""
        item = cls(
            idPedido=idPedido,
            idCardapio=idCardapio,
            quantidade=quantidade,
            precoUnitario=precoUnitario,
            observacao=observacao,
            status=status,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @classmethod
    def get_by_id(cls, db: Session, idItemPedido: int) -> Optional["ItemPedido"]:
        """Busca item pelo ID."""
        return db.query(cls).filter(cls.idItemPedido == idItemPedido).first()

    @classmethod
    def get_by_pedido(cls, db: Session, idPedido: int) -> List["ItemPedido"]:
        """Lista todos os itens de um pedido."""
        return db.query(cls).filter(cls.idPedido == idPedido).all()

    @classmethod
    def get_pendents_kitchen(cls, db: Session, idRestaurante: int) -> List["ItemPedido"]:
        """Lista itens com status 'Pendente' ou 'Em preparo' da cozinha de um restaurante."""
        from src.models.Pedido import Pedido
        return (
            db.query(cls)
            .join(Pedido, cls.idPedido == Pedido.idPedido)
            .filter(
                Pedido.idRestaurante == idRestaurante,
                cls.status.in_(["Pendente", "Em preparo"])
            )
            .order_by(Pedido.dataAbertura.asc(), cls.idItemPedido.asc())
            .all()
        )

    def update_stats(self, db: Session, novo_status: str) -> "ItemPedido":
        """Atualiza o status de preparo/entrega do item"""
        self.status = novo_status
        db.commit()
        db.refresh(self)
        return self

    def update(self, db: Session, quantidade: Optional[int] = None, precoUnitario: Optional[float] = None, status: Optional[str] = None, observacao: Optional[str] = None,) -> "ItemPedido":
        """Atualiza os campos do item do pedido."""
        if quantidade is not None:
            self.quantidade = quantidade
        if precoUnitario is not None:
            self.precoUnitario = precoUnitario
        if status is not None:
            self.status = status
        if observacao is not None:
            self.observacao = observacao
        
        db.commit()
        db.refresh(self)
        return self