import uuid
from typing import Optional

from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, relationship

from src.database.connection import Base


class Mesa(Base):
    __tablename__ = "Mesa"

    idMesa: uuid.UUID = Column(
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
    numero: int = Column(Integer, nullable=False)
    status: str = Column(String(20), nullable=False, default="Disponivel")

    __table_args__ = (
        UniqueConstraint("idRestaurante", "numero", name="uq_restaurante_mesa"),
    )

    # Relacionamentos
    restaurante = relationship("Restaurante", back_populates="mesas")
    pedidos = relationship("Pedido", back_populates="mesa", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Mesa(id={self.idMesa}, numero={self.numero}, status='{self.status}')>"

    @classmethod
    def create(
        cls, db: Session, idRestaurante: uuid.UUID | str, numero: int, status: str = "Disponivel"
    ) -> "Mesa":
        """Cria e persiste uma nova mesa."""
        mesa = cls(
            idRestaurante=idRestaurante,
            numero=numero,
            status=status,
        )
        
        db.add(mesa)
        db.commit()
        db.refresh(mesa)
        return mesa

    @classmethod
    def get_by_id(cls, db: Session, idMesa: uuid.UUID | str) -> Optional["Mesa"]:
        """Busca mesa pelo ID."""
        return db.query(cls).filter(cls.idMesa == idMesa).first()

    @classmethod
    def get_by_number(cls, db: Session, idRestaurante: uuid.UUID | str, numero: int) -> Optional["Mesa"]:
        """Busca uma mesa específica pelo seu número dentro do restaurante."""
        return db.query(cls).filter(
            cls.idRestaurante == idRestaurante,
            cls.numero == numero,
        ).first()

    @classmethod
    def get_all_by_restaurant(
        cls, db: Session, idRestaurante: uuid.UUID | str, status: str | None = None
    ) -> list["Mesa"]:
        """Lista todas as mesas do restaurante, com filtro opcional por status ('Disponivel' / 'Indisponivel')."""
        query = db.query(cls).filter(cls.idRestaurante == idRestaurante)
        if status:
            query = query.filter(cls.status == status)
        return query.order_by(cls.numero).all()

    def update_stats(self, db: Session, novo_status: str) -> "Mesa":
        """Atualiza apenas o status da mesa ('livre' ou 'ocupada')."""
        self.status = novo_status
        db.commit()
        db.refresh(self)
        return self

    def update(self, db: Session, numero: int | None = None, status: str | None = None) -> "Mesa":
        """Atualiza os dados cadastrais da mesa."""
        if numero is not None:
            self.numero = numero
        if status is not None:
            self.status = status
        db.commit()
        db.refresh(self)
        return self

    def delete(self, db: Session) -> bool:
        """Remove a mesa do banco de dados."""
        db.delete(self)
        db.commit()
        return True
