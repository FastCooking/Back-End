import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, relationship

from src.database.connection import Base


class Pagamento(Base):
    __tablename__ = "Pagamento"

    idPagamento: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    idPedido: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("Pedido.idPedido", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    formaPagamento: str = Column(String(30), nullable=False)
    valor: float = Column(Numeric(10, 2), nullable=False)
    dataPagamento: datetime = Column(DateTime, nullable=False, server_default=func.now())

    # Relacionamentos
    pedido = relationship("Pedido", back_populates="pagamentos")

    def __repr__(self):
        return f"<Pagamento(id={self.idPagamento}, pedido={self.idPedido}, forma='{self.formaPagamento}', valor={self.valor})>"

    @classmethod
    def create(
        cls, db: Session, idPedido: uuid.UUID | str, formaPagamento: str, valor: float
    ) -> "Pagamento":
        """Cria e persiste um novo pagamento."""
        pagamento = cls(
            idPedido=idPedido,
            formaPagamento=formaPagamento,
            valor=valor,
        )
        db.add(pagamento)
        db.commit()
        db.refresh(pagamento)
        return pagamento

    @classmethod
    def get_by_id(cls, db: Session, idPagamento: uuid.UUID | str) -> Optional["Pagamento"]:
        """Busca pagamento por ID."""
        return db.query(cls).filter(cls.idPagamento == idPagamento).first()

    @classmethod
    def get_by_pedido(cls, db: Session, idPedido: uuid.UUID | str) -> list["Pagamento"]:
        """Lista todos os pagamentos vinculados a um pedido."""
        return db.query(cls).filter(cls.idPedido == idPedido).order_by(cls.dataPagamento.asc()).all()