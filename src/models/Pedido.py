import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, relationship

from src.database.connection import Base


class Pedido(Base):
    __tablename__ = "Pedido"
    __table_args__ = (
        Index("ix_pedido_restaurante_status", "idRestaurante", "status"),
        Index("ix_pedido_mesa_status", "idMesa", "status"),
        Index("ix_pedido_data_abertura", "dataAbertura"),
        Index(
            "uq_pedido_ativo_por_mesa",
            "idMesa",
            unique=True,
            postgresql_where=text("status NOT IN ('Fechado', 'Cancelado')"),
            sqlite_where=text('"status" NOT IN (\'Fechado\', \'Cancelado\')'),
        ),
    )

    idPedido: uuid.UUID = Column(
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
    idMesa: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("Mesa.idMesa", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    idGarcom: uuid.UUID | None = Column(
        UUID(as_uuid=True),
        ForeignKey("Usuarios.idUsuario", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
    )
    sessao_id: str | None = Column(String(100), index=True, nullable=True)
    status: str = Column(String(30), nullable=False, default="Aberto")
    dataAbertura: datetime = Column(
        DateTime, nullable=False, default=datetime.now, server_default=func.now()
    )
    dataFechamento: datetime | None = Column(DateTime, nullable=True)
    idUsuarioFechamento: uuid.UUID | None = Column(
        UUID(as_uuid=True),
        ForeignKey("Usuarios.idUsuario", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
    )

    # Relacionamentos
    restaurante = relationship("Restaurante", back_populates="pedidos")
    mesa = relationship("Mesa", back_populates="pedidos")
    garcom = relationship(
        "Usuario", back_populates="pedidos_atendidos", foreign_keys=[idGarcom]
    )
    usuario_fechamento = relationship(
        "Usuario", foreign_keys=[idUsuarioFechamento]
    )
    itens = relationship(
        "ItemPedido", back_populates="pedido", cascade="all, delete-orphan"
    )
    pagamentos = relationship(
        "Pagamento", back_populates="pedido", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<Pedido(id={self.idPedido}, mesa={self.idMesa}, status='{self.status}')>"
        )

    @classmethod
    def get_by_id(cls, db: Session, idPedido: uuid.UUID | str) -> Optional["Pedido"]:
        return db.query(cls).filter(cls.idPedido == idPedido).first()

    @classmethod
    def get_active_for_table(
        cls, db: Session, idMesa: uuid.UUID | str
    ) -> Optional["Pedido"]:
        return (
            db.query(cls)
            .filter(
                cls.idMesa == idMesa,
                cls.status.notin_(["Fechado", "Cancelado"]),
            )
            .first()
        )

    @classmethod
    def get_all_by_restaurante(
        cls,
        db: Session,
        idRestaurante: uuid.UUID | str,
        status: str | None = None,
        apenas_ativos: bool = False,
    ) -> list["Pedido"]:
        query = db.query(cls).filter(cls.idRestaurante == idRestaurante)
        if status:
            query = query.filter(cls.status == status)
        elif apenas_ativos:
            query = query.filter(cls.status.notin_(["Fechado", "Cancelado"]))
        return query.order_by(cls.dataAbertura.desc()).all()

    @classmethod
    def create(
        cls,
        db: Session,
        idRestaurante: uuid.UUID | str,
        idMesa: uuid.UUID | str,
        idGarcom: uuid.UUID | str | None = None,
        sessao_id: str | None = None,
        status: str = "Aberto",
        commit: bool = True,
    ) -> "Pedido":
        pedido = cls(
            idRestaurante=idRestaurante,
            idMesa=idMesa,
            idGarcom=idGarcom,
            sessao_id=sessao_id,
            status=status,
            dataAbertura=datetime.now(),
        )
        db.add(pedido)
        if commit:
            db.commit()
            db.refresh(pedido)
        return pedido

    def update_stats(self, db: Session, status: str, commit: bool = True) -> "Pedido":
        self.status = status
        if status in ("Fechado", "Cancelado") and not self.dataFechamento:
            self.dataFechamento = datetime.now()
        if commit:
            db.commit()
            db.refresh(self)
        return self

    def close(self, db: Session, commit: bool = True) -> "Pedido":
        return self.update_stats(db, "Fechado", commit=commit)

    def cancel(self, db: Session, commit: bool = True) -> "Pedido":
        return self.update_stats(db, "Cancelado", commit=commit)
