import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from src.database.connection import Base


class AuditoriaCancelamentoItem(Base):
    __tablename__ = "AuditoriaCancelamentoItem"

    idAuditoria: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    idItemPedido: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "ItemPedido.idItemPedido",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    idPedido: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("Pedido.idPedido", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    idMesa: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("Mesa.idMesa", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    sessao_id: str | None = Column(String(100), nullable=True)
    origem: str = Column(String(20), nullable=False)
    idUsuario: uuid.UUID | None = Column(UUID(as_uuid=True), nullable=True)
    motivo: str | None = Column(Text, nullable=True)
    dataHora = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            '"origem" IN (\'CLIENTE\', \'GARCOM\', \'GERENTE\', \'ADM\')',
            name="ck_auditoria_cancelamento_origem",
        ),
        CheckConstraint(
            (
                '("origem" = \'CLIENTE\' AND "idUsuario" IS NULL AND "motivo" IS NULL) '
                "OR "
                '("origem" IN (\'GARCOM\', \'GERENTE\', \'ADM\') '
                'AND "idUsuario" IS NOT NULL AND "motivo" IS NOT NULL '
                'AND length(trim("motivo")) > 0)'
            ),
            name="ck_auditoria_cancelamento_responsavel_motivo",
        ),
        Index("ix_auditoria_cancelamento_item", "idItemPedido"),
        Index("ix_auditoria_cancelamento_pedido", "idPedido"),
    )
