import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, relationship

from src.database.connection import Base


class LogDesconto(Base):
    __tablename__ = "LogDesconto"

    idLogDesconto: uuid.UUID = Column(
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
    idPedido: uuid.UUID | None = Column(
        UUID(as_uuid=True),
        ForeignKey("Pedido.idPedido", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=True,
    )
    idUsuario: uuid.UUID | None = Column(
        UUID(as_uuid=True),
        ForeignKey("Usuarios.idUsuario", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
    )
    usuario: str = Column(String(255), nullable=False)
    funcaoUsuario: str | None = Column(String(50), nullable=True)
    valorDesconto: float = Column(Numeric(10, 2), nullable=False, default=0.0)
    tipoDesconto: str | None = Column(String(20), nullable=True)
    motivo: str | None = Column(Text, nullable=True)
    sucesso: bool = Column(Boolean, nullable=False, default=True)
    motivoFalha: str | None = Column(String(255), nullable=True)
    dataHora: datetime = Column(
        DateTime, nullable=False, default=datetime.now, server_default=func.now()
    )

    # Relacionamentos
    pedido = relationship("Pedido", back_populates="logs_desconto")
    restaurante = relationship("Restaurante")
    usuario_rel = relationship("Usuario", foreign_keys=[idUsuario])

    def __repr__(self):
        return (
            f"<LogDesconto(id={self.idLogDesconto}, usuario='{self.usuario}', "
            f"valor={self.valorDesconto}, sucesso={self.sucesso})>"
        )

    @classmethod
    def create(
        cls,
        db: Session,
        idRestaurante: uuid.UUID | str,
        usuario: str,
        valorDesconto: float,
        idPedido: uuid.UUID | str | None = None,
        idUsuario: uuid.UUID | str | None = None,
        funcaoUsuario: str | None = None,
        tipoDesconto: str | None = None,
        motivo: str | None = None,
        sucesso: bool = True,
        motivoFalha: str | None = None,
        dataHora: datetime | None = None,
        commit: bool = True,
    ) -> "LogDesconto":
        """Registra uma entrada de log para concessão ou tentativa de desconto."""
        log = cls(
            idRestaurante=idRestaurante,
            idPedido=idPedido,
            idUsuario=idUsuario,
            usuario=usuario,
            funcaoUsuario=funcaoUsuario,
            valorDesconto=valorDesconto,
            tipoDesconto=tipoDesconto,
            motivo=motivo,
            sucesso=sucesso,
            motivoFalha=motivoFalha,
            dataHora=dataHora or datetime.now(),
        )
        db.add(log)
        if commit:
            db.commit()
            db.refresh(log)
        else:
            db.flush()
        return log

    @classmethod
    def get_by_pedido(
        cls, db: Session, idPedido: uuid.UUID | str
    ) -> list["LogDesconto"]:
        """Lista histórico de logs de desconto vinculados a um pedido."""
        return (
            db.query(cls)
            .filter(cls.idPedido == idPedido)
            .order_by(cls.dataHora.desc())
            .all()
        )

    @classmethod
    def get_by_restaurante(
        cls, db: Session, idRestaurante: uuid.UUID | str
    ) -> list["LogDesconto"]:
        """Lista histórico de logs de desconto de um restaurante."""
        return (
            db.query(cls)
            .filter(cls.idRestaurante == idRestaurante)
            .order_by(cls.dataHora.desc())
            .all()
        )
