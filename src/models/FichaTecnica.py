import uuid
from typing import Optional

from sqlalchemy import Column, ForeignKey, Numeric, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, relationship

from src.database.connection import Base


class FichaTecnica(Base):
    __tablename__ = "FichaTecnica"

    idFichaTecnica: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    idCardapio: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("Cardapio.idCardapio", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    idEstoque: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("Estoque.idEstoque", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    quantidadeNecessaria: float = Column(Numeric(10, 3), nullable=False)

    __table_args__ = (
        UniqueConstraint("idCardapio", "idEstoque", name="uq_ficha_cardapio_estoque"),
    )

    # Relacionamentos
    cardapio = relationship("Cardapio", back_populates="fichas_tecnicas")
    estoque = relationship("Estoque", back_populates="fichas_tecnicas")

    def __repr__(self):
        return f"<FichaTecnica(id={self.idFichaTecnica}, idCardapio={self.idCardapio}, idEstoque={self.idEstoque}, qtd={self.quantidadeNecessaria})>"

    @classmethod
    def create(
        cls,
        db: Session,
        idCardapio: uuid.UUID | str,
        idEstoque: uuid.UUID | str,
        quantidadeNecessaria: float,
    ) -> "FichaTecnica":
        """Cria e persiste uma nova relação de ficha técnica."""
        ficha = cls(
            idCardapio=idCardapio,
            idEstoque=idEstoque,
            quantidadeNecessaria=quantidadeNecessaria,
        )
        db.add(ficha)
        db.commit()
        db.refresh(ficha)
        return ficha

    @classmethod
    def get_by_id(cls, db: Session, idFichaTecnica: uuid.UUID | str) -> Optional["FichaTecnica"]:
        """Busca registro de ficha técnica pelo ID."""
        return db.query(cls).filter(cls.idFichaTecnica == idFichaTecnica).first()

    @classmethod
    def get_by_menu(cls, db: Session, idCardapio: uuid.UUID | str) -> list["FichaTecnica"]:
        """Lista todos os insumos e proporções associados a um item do cardápio."""
        return db.query(cls).filter(cls.idCardapio == idCardapio).all()

    @classmethod
    def get_by_menu_storage(
        cls, db: Session, idCardapio: uuid.UUID | str, idEstoque: uuid.UUID | str
    ) -> Optional["FichaTecnica"]:
        """Busca o vínculo específico entre um item do cardápio e um insumo."""
        return db.query(cls).filter(
            cls.idCardapio == idCardapio,
            cls.idEstoque == idEstoque,
        ).first()

    def update(self, db: Session, quantidadeNecessaria: float) -> "FichaTecnica":
        """Atualiza a quantidade necessária do insumo."""
        self.quantidadeNecessaria = quantidadeNecessaria
        db.commit()
        db.refresh(self)
        return self

    def delete(self, db: Session) -> bool:
        """Remove o registro de ficha técnica."""
        db.delete(self)
        db.commit()
        return True
