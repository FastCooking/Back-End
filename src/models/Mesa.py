from typing import List, Optional
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, Session
from src.database.connection import Base


class Mesa(Base):
    __tablename__ = "Mesa"

    idMesa = Column(Integer, primary_key=True, autoincrement=True)
    idRestaurante = Column(Integer, ForeignKey("Restaurante.idRestaurante", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    numero = Column(Integer, nullable=False)
    capacidade = Column(Integer, nullable=False, default=4)
    status = Column(String(20), nullable=False, default="livre")

    __table_args__ = (
        UniqueConstraint("idRestaurante", "numero", name="uq_restaurante_mesa"),
    )

    # Relacionamentos
    restaurante = relationship("Restaurante", back_populates="mesas")
    pedidos = relationship("Pedido", back_populates="mesa", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Mesa(id={self.idMesa}, numero={self.numero}, status='{self.status}')>"

    # =====================================================================
    # Operações com o Banco de Dados (CRUD / Acesso a Dados)
    # =====================================================================

    @classmethod
    def create(
        cls,
        db: Session,
        idRestaurante: int,
        numero: int,
        capacidade: int = 4,
        status: str = "livre"
    ) -> "Mesa":
        """Cria e persiste uma nova mesa."""
        mesa = cls(
            idRestaurante=idRestaurante,
            numero=numero,
            capacidade=capacidade,
            status=status
        )
        db.add(mesa)
        db.commit()
        db.refresh(mesa)
        return mesa

    @classmethod
    def get_by_id(cls, db: Session, idMesa: int) -> Optional["Mesa"]:
        """Busca mesa pelo ID."""
        return db.query(cls).filter(cls.idMesa == idMesa).first()

    @classmethod
    def get_by_numero(cls, db: Session, idRestaurante: int, numero: int) -> Optional["Mesa"]:
        """Busca uma mesa específica pelo seu número dentro do restaurante."""
        return db.query(cls).filter(
            cls.idRestaurante == idRestaurante,
            cls.numero == numero
        ).first()

    @classmethod
    def get_all_by_restaurante(
        cls,
        db: Session,
        idRestaurante: int,
        status: Optional[str] = None
    ) -> List["Mesa"]:
        """Lista todas as mesas do restaurante, com filtro opcional por status ('livre' / 'ocupada')."""
        query = db.query(cls).filter(cls.idRestaurante == idRestaurante)
        if status:
            query = query.filter(cls.status == status)
        return query.order_by(cls.numero).all()

    def update_status(self, db: Session, novo_status: str) -> "Mesa":
        """Atualiza apenas o status da mesa ('livre' ou 'ocupada')."""
        self.status = novo_status
        db.commit()
        db.refresh(self)
        return self

    def update(
        self,
        db: Session,
        numero: Optional[int] = None,
        capacidade: Optional[int] = None,
        status: Optional[str] = None
    ) -> "Mesa":
        """Atualiza os dados cadastrais da mesa."""
        if numero is not None:
            self.numero = numero
        if capacidade is not None:
            self.capacidade = capacidade
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
