import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL não encontrada.")

if make_url(DATABASE_URL).drivername == "postgresql":
    DATABASE_URL = make_url(DATABASE_URL).set(drivername="postgresql+psycopg").render_as_string(
        hide_password=False
    )

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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


def get_db() -> Generator[Session, None, None]:
    """Dependência oficial do FastAPI para injeção de sessão de banco de dados."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> bool:
    """Testa se a conexão com o banco de dados está ativa."""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT current_database();"))
            db_name = result.scalar()
            print(f"[OK] Conectado ao banco '{db_name}'")
            return True
    except SQLAlchemyError as e:
        print(f"[ERRO] {e}")
        return False
