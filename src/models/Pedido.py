import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, relationship

from src.database.connection import Base


class Pedido(Base):
    __tablename__ = "Pedido"

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
    desconto: float = Column(Numeric(10, 2), nullable=False, default=0.0)
    tipoDesconto: str | None = Column(String(20), nullable=True)
    valorDescontoInformado: float | None = Column(Numeric(10, 2), nullable=True)
    motivoDesconto: str | None = Column(String(255), nullable=True)
    idGerenteDesconto: uuid.UUID | None = Column(
        UUID(as_uuid=True),
        ForeignKey("Usuarios.idUsuario", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
    )
    dataDesconto: datetime | None = Column(DateTime, nullable=True)

    # Relacionamentos
    restaurante = relationship("Restaurante", back_populates="pedidos")
    mesa = relationship("Mesa", back_populates="pedidos")
    garcom = relationship(
        "Usuario", back_populates="pedidos_atendidos", foreign_keys=[idGarcom]
    )
    usuario_fechamento = relationship(
        "Usuario", foreign_keys=[idUsuarioFechamento]
    )
    gerente_desconto = relationship(
        "Usuario", foreign_keys=[idGerenteDesconto]
    )
    itens = relationship(
        "ItemPedido", back_populates="pedido", cascade="all, delete-orphan"
    )
    pagamentos = relationship(
        "Pagamento", back_populates="pedido", cascade="all, delete-orphan"
    )
    logs_desconto = relationship(
        "LogDesconto", back_populates="pedido", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<Pedido(id={self.idPedido}, mesa={self.idMesa}, status='{self.status}')>"
        )

    @classmethod
    def create(
        cls,
        db: Session,
        idRestaurante: uuid.UUID | str,
        idMesa: uuid.UUID | str,
        idGarcom: uuid.UUID | str | None = None,
        sessao_id: str | None = None,
        status: str = "Aberto",
        desconto: float = 0.0,
        tipoDesconto: str | None = None,
        motivoDesconto: str | None = None,
        commit: bool = True,
    ) -> "Pedido":
        """Cria e persiste um novo pedido/comanda."""
        pedido = cls(
            idRestaurante=idRestaurante,
            idMesa=idMesa,
            idGarcom=idGarcom,
            sessao_id=sessao_id,
            status=status,
            desconto=desconto,
            tipoDesconto=tipoDesconto,
            motivoDesconto=motivoDesconto,
        )
        db.add(pedido)
        if commit:
            db.commit()
            db.refresh(pedido)
        else:
            db.flush()
        return pedido

    @classmethod
    def get_by_id(cls, db: Session, idPedido: uuid.UUID | str) -> Optional["Pedido"]:
        """Busca pedido pelo ID."""
        return db.query(cls).filter(cls.idPedido == idPedido).first()

    @classmethod
    def get_active_for_table(
        cls, db: Session, idMesa: uuid.UUID | str
    ) -> Optional["Pedido"]:
        """Busca o pedido atualmente aberto/em andamento para uma mesa."""
        return (
            db.query(cls)
            .filter(
                cls.idMesa == idMesa,
                cls.status.notin_(["Fechado", "Cancelado"]),
            )
            .first()
        )

    @classmethod
    def get_all_by_restaurant(
        cls, db: Session, idRestaurante: uuid.UUID | str, status: str | None = None
    ) -> list["Pedido"]:
        """Lista pedidos de um restaurante, com filtro opcional de status."""
        query = db.query(cls).filter(cls.idRestaurante == idRestaurante)
        if status:
            query = query.filter(cls.status == status)
        return query.order_by(cls.dataAbertura.desc()).all()

    def update_stats(
        self,
        db: Session,
        novo_status: str,
        dataFechamento: datetime | None = None,
        commit: bool = True,
    ) -> "Pedido":
        """Atualiza o status do pedido e opcionalmente a data de fechamento."""
        self.status = novo_status
        if dataFechamento is not None:
            self.dataFechamento = dataFechamento
        elif novo_status in ("Fechado", "Cancelado") and not self.dataFechamento:
            self.dataFechamento = datetime.now(UTC)

        if commit:
            db.commit()
            db.refresh(self)
        else:
            db.flush()
        return self

    def update(
        self,
        db: Session,
        idGarcom: uuid.UUID | str | None = None,
        status: str | None = None,
        dataFechamento: datetime | None = None,
        desconto: float | None = None,
        tipoDesconto: str | None = None,
        valorDescontoInformado: float | None = None,
        motivoDesconto: str | None = None,
        idGerenteDesconto: uuid.UUID | str | None = None,
        dataDesconto: datetime | None = None,
    ) -> "Pedido":
        """Atualiza os dados de um pedido."""
        if idGarcom is not None:
            self.idGarcom = idGarcom
        if status is not None:
            self.status = status
        if dataFechamento is not None:
            self.dataFechamento = dataFechamento
        if desconto is not None:
            self.desconto = desconto
        if tipoDesconto is not None:
            self.tipoDesconto = tipoDesconto
        if valorDescontoInformado is not None:
            self.valorDescontoInformado = valorDescontoInformado
        if motivoDesconto is not None:
            self.motivoDesconto = motivoDesconto
        if idGerenteDesconto is not None:
            self.idGerenteDesconto = idGerenteDesconto
        if dataDesconto is not None:
            self.dataDesconto = dataDesconto

        db.commit()
        db.refresh(self)
        return self
