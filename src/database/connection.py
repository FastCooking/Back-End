import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL não encontrada.")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


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
