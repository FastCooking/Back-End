import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from src.database.connection import Base


class Sessao(Base):
    __tablename__ = "Sessao"

    idSessao = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    idMesa = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "Mesa.idMesa",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    status = Column(
        String(20),
        nullable=False,
        default="Ativa",
        server_default=text("'Ativa'"),
    )

    dataAbertura = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    dataEncerramento = Column(
        DateTime,
        nullable=True,
    )

    __table_args__ = (
        Index(
            "uq_sessao_ativa_por_mesa",
            "idMesa",
            unique=True,
            postgresql_where=text("status = 'Ativa'"),
            sqlite_where=text('"status" = \'Ativa\''),
        ),
    )