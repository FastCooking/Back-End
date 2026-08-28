from typing import Optional

from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Session, relationship

from src.database.connection import Base


class ItemPedido(Base):
    __tablename__ = "ItemPedido"

    idItemPedido : int = Column(Integer, primary_key=True, autoincrement=True)
    idPedido : int = Column(Integer, ForeignKey("Pedido.idPedido", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    idCardapio : int = Column(Integer, ForeignKey("Cardapio.idCardapio", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    quantidade : int = Column(Integer, nullable=False, default=1)
    precoUnitario : float = Column(Numeric(10, 2), nullable=False)
    status : str = Column(String(30), nullable=False, default="Pendente")
    observacao : str = Column(Text, nullable=True)

    # Relacionamentos
    pedido = relationship("Pedido", back_populates="itens")
    cardapio = relationship("Cardapio", back_populates="itens_pedido")

    def __repr__(self):
        return f"<ItemPedido(id={self.idItemPedido}, pedido={self.idPedido}, cardapio={self.idCardapio}, status='{self.status}')>"

    @classmethod
    def create(cls, db: Session, idPedido: int, idCardapio: int, quantidade: int, precoUnitario: float, observacao: str | None = None, status: str = "Pendente") -> "ItemPedido":
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
    def get_by_pedido(cls, db: Session, idPedido: int) -> list["ItemPedido"]:
        """Lista todos os itens de um pedido."""
        return db.query(cls).filter(cls.idPedido == idPedido).all()

    @classmethod
    def get_pendents_kitchen(cls, db: Session, idRestaurante: int) -> list["ItemPedido"]:
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

    def update(self, db: Session, quantidade: int | None = None, precoUnitario: float | None = None, status: str | None = None, observacao: str | None = None,) -> "ItemPedido":
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