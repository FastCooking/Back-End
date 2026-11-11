import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, relationship

from src.database.connection import Base


class ItemPedido(Base):
    __tablename__ = "ItemPedido"
    __table_args__ = (
        Index("ix_item_pedido_kds", "idPedido", "status", "liberadoParaPreparo"),
        Index("ix_item_pedido_status", "status"),
        Index("ix_item_pedido_delivery", "deliveryStatus", "claimedByWaiterId"),
        Index("ix_item_pedido_data_criacao", "dataCriacao"),
        Index("ix_item_pedido_cardapio", "idCardapio"),
    )

    idItemPedido: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    idPedido: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("Pedido.idPedido", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    idCardapio: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("Cardapio.idCardapio", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    quantidade: int = Column(Integer, nullable=False, default=1)
    precoUnitario: float = Column(Numeric(10, 2), nullable=False)
    observacao: str | None = Column(Text, nullable=True)
    status: str = Column(String(30), nullable=False, default="Pendente")
    categoria: str | None = Column(String(50), nullable=True)
    prioridade: int = Column(Integer, nullable=False, default=1)
    dataCriacao: datetime = Column(
        DateTime, nullable=False, default=datetime.now, server_default=func.now()
    )
    liberadoParaPreparo: bool = Column(
        Boolean,
        nullable=False,
        default=True,
    )
    deliveryStatus: str | None = Column(
        String(40),
        nullable=True,
        default=None,
    )
    claimedByWaiterId: uuid.UUID | None = Column(
        UUID(as_uuid=True),
        ForeignKey("Usuarios.idUsuario", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
    )
    claimedAt: datetime | None = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    deliveredAt: datetime | None = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relacionamentos
    pedido = relationship("Pedido", back_populates="itens")
    cardapio = relationship("Cardapio", back_populates="itens_pedido")
    entrega = relationship(
        "Entrega",
        back_populates="item_pedido",
        uselist=False,
        cascade="all, delete-orphan",
    )

    origem: str = Column(
        String(20),
        nullable=False,
        default="CLIENTE",
        server_default=text("'CLIENTE'"),
    )

    def __repr__(self):
        return (
            f"<ItemPedido(id={self.idItemPedido}, pedido={self.idPedido}, "
            f"cardapio={self.idCardapio}, qtd={self.quantidade}, status='{self.status}')>"
        )

    @classmethod
    def create(
        cls,
        db: Session,
        idPedido: uuid.UUID | str,
        idCardapio: uuid.UUID | str,
        quantidade: int,
        precoUnitario: float,
        observacao: str | None = None,
        status: str = "Pendente",
        categoria: str | None = None,
        prioridade: int = 1,
        liberadoParaPreparo: bool = True,
        origem: str = "CLIENTE",
        commit: bool = True,
    ) -> "ItemPedido":
        """Cria e persiste um novo item de pedido."""
        item = cls(
            idItemPedido=uuid.uuid4(),
            idPedido=idPedido,
            idCardapio=idCardapio,
            quantidade=quantidade,
            precoUnitario=precoUnitario,
            observacao=observacao,
            status=status,
            categoria=categoria,
            prioridade=prioridade,
            liberadoParaPreparo=liberadoParaPreparo,
            origem=origem,
        )
        db.add(item)
        if commit:
            db.commit()
            db.refresh(item)
        else:
            db.flush()
        return item

    @classmethod
    def get_by_id(
        cls, db: Session, idItemPedido: uuid.UUID | str
    ) -> Optional["ItemPedido"]:
        return db.query(cls).filter(cls.idItemPedido == idItemPedido).first()

    @classmethod
    def get_by_pedido(
        cls, db: Session, idPedido: uuid.UUID | str
    ) -> list["ItemPedido"]:
        return db.query(cls).filter(cls.idPedido == idPedido).all()

    def update_stats(
        self, db: Session, status: str, commit: bool = True
    ) -> "ItemPedido":
        self.status = status
        if commit:
            db.commit()
            db.refresh(self)
        return self
