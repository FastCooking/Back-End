from typing import List, Optional
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Session
import bcrypt
from src.database.connection import Base


class Usuario(Base):
    """
    Representa a tabela 'Usuarios' (Garçom, Cozinheiro, Gerente, Adm).
    """
    __tablename__ = "Usuarios"

    idFuncionario = Column(Integer, primary_key=True, autoincrement=True)
    idRestaurante = Column(Integer, ForeignKey("Restaurante.idRestaurante", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    nome = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    senha = Column(String(255), nullable=False)
    funcao = Column(String(50), nullable=False)

    restaurante = relationship("Restaurante", back_populates="usuarios")
    pedidos_atendidos = relationship("Pedido", back_populates="garcom", foreign_keys="Pedido.idGarcom")
    itens_preparados = relationship("ItemPedido", back_populates="cozinheiro", foreign_keys="ItemPedido.idCozinheiro")

    def __repr__(self):
        return f"<Funcionario(id={self.idFuncionario}, nome='{self.nome}', funcao='{self.funcao}')>"

    @classmethod
    def create(cls, db: Session, idRestaurante: int, nome: str, email: str, senha: str, funcao: str, gerar_hash: bool = True) -> "Usuario":
        """Cria e persiste um novo funcionário/usuário."""
        if gerar_hash:
            salt = bcrypt.gensalt()
            senha = bcrypt.hashpw(senha.encode("utf-8"), salt).decode("utf-8")

        funcionario = cls(
            idRestaurante=idRestaurante,
            nome=nome,
            email=email,
            senha=senha,
            funcao=funcao
        )
        
        db.add(funcionario)
        db.commit()
        db.refresh(funcionario)
        
        return funcionario

    @classmethod
    def get_by_id(cls, db: Session, idFuncionario: int) -> Optional["Usuario"]:
        """Busca funcionário por ID."""
        return db.query(cls).filter(cls.idFuncionario == idFuncionario).first()

    @classmethod
    def get_by_email(cls, db: Session, email: str) -> Optional["Usuario"]:
        """Busca funcionário por e-mail único."""
        return db.query(cls).filter(cls.idFuncionario != None, cls.email == email).first()

    @classmethod
    def get_all_by_restaurante(cls, db: Session, idRestaurante: int, funcao: Optional[str] = None) -> List["Usuario"]:
        """Lista funcionários de um restaurante, opcionalmente filtrados por função."""
        query = db.query(cls).filter(cls.idRestaurante == idRestaurante)
        if funcao:
            query = query.filter(cls.funcao == funcao)
        return query.all()

    def update(self, db: Session, nome: Optional[str] = None, email: Optional[str] = None, senha: Optional[str] = None, funcao: Optional[str] = None, gerar_hash: bool = True) -> "Usuario":
        """Atualiza os dados de um funcionário."""
        if nome is not None:
            self.nome = nome
        if email is not None:
            self.email = email
        if funcao is not None:
            self.funcao = funcao
        if senha is not None:
            if gerar_hash:
                salt = bcrypt.gensalt()
                self.senha = bcrypt.hashpw(senha.encode("utf-8"), salt).decode("utf-8")
            else:
                self.senha = senha

        db.commit()
        db.refresh(self)
        return self

    def delete(self, db: Session) -> bool:
        """Remove o funcionário do banco de dados."""
        db.delete(self)
        db.commit()
        return True
