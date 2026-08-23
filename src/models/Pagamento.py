from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship, Session
from src.database.connection import Base


class Pagamento(Base):
    """
    Representa o pagamento de um pedido/comanda.
    Contém os mapeamentos ORM e as operações de banco de dados.
    """
    __tablename__ = "Pagamento"

    idPagamento = Column(Integer, primary_key=True, autoincrement=True)
    idPedido = Column(Integer, ForeignKey("Pedido.idPedido", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    formaPagamento = Column(String(30), nullable=False)
    valor = Column(Numeric(10, 2), nullable=False)
    dataPagamento = Column(DateTime, nullable=False, server_default=func.now())

    # Relacionamentos
    pedido = relationship("Pedido", back_populates="pagamentos")

    def __repr__(self):
        return f"<Pagamento(id={self.idPagamento}, pedido={self.idPedido}, forma='{self.formaPagamento}', valor={self.valor})>"

    # =====================================================================
    # Operações com o Banco de Dados (CRUD / Acesso a Dados)
    # =====================================================================

    @classmethod
    def create(
        cls,
        db: Session,
        idPedido: int,
        formaPagamento: str,
        valor: float
    ) -> "Pagamento":
        """Cria e persiste um novo pagamento."""
        pagamento = cls(
            idPedido=idPedido,
            formaPagamento=formaPagamento,
            valor=valor
        )
        db.add(pagamento)
        db.commit()
        db.refresh(pagamento)
        return pagamento

    @classmethod
    def get_by_id(cls, db: Session, idPagamento: int) -> Optional["Pagamento"]:
        """Busca pagamento por ID."""
        return db.query(cls).filter(cls.idPagamento == idPagamento).first()

    @classmethod
    def get_by_pedido(cls, db: Session, idPedido: int) -> List["Pagamento"]:
        """Lista todos os pagamentos vinculados a um pedido."""
        return db.query(cls).filter(cls.idPedido == idPedido).order_by(cls.dataPagamento.asc()).all()

    def delete(self, db: Session) -> bool:
        """Remove o pagamento do banco de dados."""
        db.delete(self)
        db.commit()
        return True
