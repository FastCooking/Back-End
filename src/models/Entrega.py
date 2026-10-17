import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.database.connection import Base
from src.schemas.DeliverySchema import DeliveryState


class Entrega(Base):
    """
    Entidade transacional de controle de entrega de itens prontos no salão.
    Garante unicidade física por ItemPedido (1 item = no máximo 1 entrega)
    e suporta fila FIFO (WAITING_DELIVERY_PICKUP -> IN_DELIVERY -> DELIVERED).
    """

    __tablename__ = "Entrega"
    __table_args__ = (
        UniqueConstraint("idItemPedido", name="uq_entrega_item_pedido"),
        Index("ix_entrega_fila_fifo", "idRestaurante", "status", "dataCriacao"),
        Index("ix_entrega_garcom_status", "idGarcom", "status"),
    )

    idEntrega: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    idRestaurante: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("Restaurante.idRestaurante", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    idPedido: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("Pedido.idPedido", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    idItemPedido: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("ItemPedido.idItemPedido", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    idGarcom: uuid.UUID | None = Column(
        UUID(as_uuid=True),
        ForeignKey("Usuarios.idUsuario", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
    )
    status: str = Column(
        String(40),
        nullable=False,
        default=DeliveryState.WAITING_DELIVERY_PICKUP.value,
    )
    dataCriacao: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    claimedAt: datetime | None = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    deliveredAt: datetime | None = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    item_pedido = relationship("ItemPedido", back_populates="entrega")
    pedido = relationship("Pedido")
    garcom = relationship("Usuario", foreign_keys=[idGarcom])

    def __repr__(self) -> str:
        return (
            f"<Entrega(id={self.idEntrega}, item={self.idItemPedido}, "
            f"garcom={self.idGarcom}, status='{self.status}')>"
        )

