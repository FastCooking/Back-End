from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship, Session
from src.database.connection import Base


class Pedido(Base):
    __tablename__ = "Pedido"

    idPedido : int = Column(Integer, primary_key=True, autoincrement=True)
    idRestaurante : int = Column(Integer, ForeignKey("Restaurante.idRestaurante", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    idMesa : int = Column(Integer, ForeignKey("Mesa.idMesa", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    idGarcom : int = Column(Integer, ForeignKey("Usuarios.idUsuario", onupdate="CASCADE", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), nullable=False, default="Aberto")
    dataAbertura : datetime = Column(DateTime, nullable=False, server_default=func.now())
    dataFechamento : datetime = Column(DateTime, nullable=True)

    # Relacionamentos
    restaurante = relationship("Restaurante", back_populates="pedidos")
    mesa = relationship("Mesa", back_populates="pedidos")
    garcom = relationship("Usuario", back_populates="pedidos_atendidos", foreign_keys=[idGarcom])
    itens = relationship("ItemPedido", back_populates="pedido", cascade="all, delete-orphan")
    pagamentos = relationship("Pagamento", back_populates="pedido", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Pedido(id={self.idPedido}, mesa={self.idMesa}, status='{self.status}')>"

    @classmethod
    def create(cls, db: Session, idRestaurante: int, idMesa: int, idGarcom: Optional[int] = None, status: str = "Aberto") -> "Pedido":
        """Cria e persiste um novo pedido/comanda."""
        pedido = cls(
            idRestaurante=idRestaurante,
            idMesa=idMesa,
            idGarcom=idGarcom,
            status=status
        )
        db.add(pedido)
        db.commit()
        db.refresh(pedido)
        return pedido

    @classmethod
    def get_by_id(cls, db: Session, idPedido: int) -> Optional["Pedido"]:
        """Busca pedido pelo ID."""
        return db.query(cls).filter(cls.idPedido == idPedido).first()

    @classmethod
    def get_active_for_table(cls, db: Session, idMesa: int) -> Optional["Pedido"]:
        """Busca o pedido atualmente aberto/em andamento para uma mesa."""
        return db.query(cls).filter(
            cls.idMesa == idMesa,
            cls.status.notin_(["Fechado", "Cancelado"])
        ).first()

    @classmethod
    def get_all_by_restaurant(cls, db: Session, idRestaurante: int, status: Optional[str] = None) -> List["Pedido"]:
        """Lista pedidos de um restaurante, com filtro opcional de status."""
        query = db.query(cls).filter(cls.idRestaurante == idRestaurante)
        if status:
            query = query.filter(cls.status == status)
        return query.order_by(cls.dataAbertura.desc()).all()

    def update_stats(self, db: Session, novo_status: str, dataFechamento: Optional[datetime] = None) -> "Pedido":
        """Atualiza o status do pedido e opcionalmente a data de fechamento."""
        self.status = novo_status
        if dataFechamento is not None:
            self.dataFechamento = dataFechamento
        elif novo_status in ("Fechado", "Cancelado") and not self.dataFechamento:
            self.dataFechamento = datetime.utcnow()

        db.commit()
        db.refresh(self)
        return self

    def update(self, db: Session, idGarcom: Optional[int] = None, status: Optional[str] = None, dataFechamento: Optional[datetime] = None) -> "Pedido":
        """Atualiza os dados de um pedido."""
        if idGarcom is not None:
            self.idGarcom = idGarcom
        if status is not None:
            self.status = status
        if dataFechamento is not None:
            self.dataFechamento = dataFechamento

        db.commit()
        db.refresh(self)
        return self