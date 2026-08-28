from typing import List, Optional
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship, Session
import bcrypt
from src.database.connection import Base


class Usuario(Base):
    """
    Representa a tabela 'Usuarios' (Garçom, Cozinheiro, Gerente, Adm).
    """
    __tablename__ = "Usuarios"

    idUsuario : int = Column(Integer, primary_key=True, autoincrement=True)
    idRestaurante : int = Column(Integer, ForeignKey("Restaurante.idRestaurante", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    nome : str = Column(String(255), nullable=False)
    cpf : str = Column(String(14), unique=True, nullable=False)
    email : str = Column(String(255), unique=True, nullable=False)
    senha : str = Column(String(255), nullable=False)
    funcao : str = Column(String(50), nullable=False)
    status : bool = Column(Boolean, nullable=False, default=True )

    restaurante = relationship("Restaurante", back_populates="usuarios")
    pedidos_atendidos = relationship("Pedido", back_populates="garcom", foreign_keys="Pedido.idGarcom")

    def __repr__(self):
        return f"<Usuario(id={self.idUsuario}, nome='{self.nome}', funcao='{self.funcao}')>"

    @classmethod
    def create(cls, db: Session, idRestaurante: int, nome: str, cpf: str, email: str, senha: str, funcao: str) -> "Usuario":
        """Cria e persiste um novo funcionário/usuário."""
        usuario = cls(
            idRestaurante=idRestaurante,
            nome=nome,
            cpf=cpf,
            email=email,
            senha=senha,
            funcao=funcao
        )
        
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        
        return usuario

    @classmethod
    def get_by_id(cls, db: Session, idUsuario: int) -> Optional["Usuario"]:
        """Busca funcionário por ID."""
        return db.query(cls).filter(cls.idUsuario == idUsuario).first()

    @classmethod
    def get_by_email(cls, db: Session, email: str) -> Optional["Usuario"]:
        """Busca funcionário por e-mail único."""
        return db.query(cls).filter(cls.idUsuario != None, cls.email == email).first()

    @classmethod
    def get_all_by_restaurante(cls, db: Session, idRestaurante: int, funcao: Optional[str] = None) -> List["Usuario"]:
        """Lista funcionários de um restaurante, opcionalmente filtrados por função."""
        query = db.query(cls).filter(cls.idRestaurante == idRestaurante)
        if funcao:
            query = query.filter(cls.funcao == funcao)
        return query.all()

    def update(self, db: Session, nome: Optional[str] = None,  cpf: Optional[str] = None, email: Optional[str] = None, senha: Optional[str] = None, funcao: Optional[str] = None) -> "Usuario":
        """Atualiza os dados de um funcionário."""
        if nome is not None:
            self.nome = nome
        if cpf is not None:
            self.cpf = cpf
        if email is not None:
            self.email = email
        if senha is not None:
            self.senha = senha
        if funcao is not None:
            self.funcao = funcao
            
        db.commit()
        db.refresh(self)
        return self

    def disable(self, db: Session):
        self.status = False
        db.commit()
        db.refresh(self)
        return True

    def able(self, db: Session):
        self.status = False
        db.commit()
        db.refresh(self)
        return True

    def delete(self, db: Session) -> bool:
        """Remove o funcionário do banco de dados."""
        self.nome = "USUARIO REMOVIDO"
        self.cpf = "000.000.000-00"
        self.email = "USUARIO REMOVIDO"
        self.senha = "" #substituir por senha padrao placeholder
            
        db.commit()
        db.refresh(self)
        return self

def cript_pass(senha:str, salt: int):
    salt = bcrypt.gensalt()
    senha = bcrypt.hashpw(senha.encode("utf-8"), salt).decode("utf-8")