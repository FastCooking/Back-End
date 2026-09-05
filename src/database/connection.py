import os

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fastcooking.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Importa os modelos para registrar as tabelas no metadata do SQLAlchemy.
from src.models.Cardapio import Cardapio  # noqa: F401
from src.models.Estoque import Estoque  # noqa: F401
from src.models.FichaTecnica import FichaTecnica  # noqa: F401
from src.models.ItemPedido import ItemPedido  # noqa: F401
from src.models.Mesa import Mesa  # noqa: F401
from src.models.Pagamento import Pagamento  # noqa: F401
from src.models.Pedido import Pedido  # noqa: F401
from src.models.Restaurante import Restaurante  # noqa: F401
from src.models.Usuario import Usuario  # noqa: F401


class Database:
    def __init__(self, database_url: str | None = None):
        url = database_url or DATABASE_URL

        if not url:
            raise ValueError("DATABASE_URL não encontrada.")

        self.engine = create_engine(url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self.Base = Base

    def get_db(self):
        db = self.SessionLocal()

        try:
            yield db
        finally:
            db.close()

    def test_connection(self):
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text("SELECT current_database();"))
                db_name = result.scalar()
                print(f"[OK] Conectado ao banco '{db_name}'")
                return True
        except SQLAlchemyError as e:
            print(f"[ERRO] {e}")
            return False


def init_db():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        from src.models.Restaurante import Restaurante

        restaurante = db.query(Restaurante).first()
        if restaurante is None:
            db.add(
                Restaurante(
                    nome="Restaurante Padrão",
                    cnpj="00.000.000/0001-00",
                    telefone="00000000000",
                    email="padrao@restaurante.local",
                    cep="00000-000",
                    status=True,
                )
            )
            db.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
