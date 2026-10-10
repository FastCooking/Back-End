import os
import sys

# Adiciona o diretório principal no PYTHONPATH para encontrar a pasta "src"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.app import app
from src.database.connection import Base, SessionLocal, get_db


@event.listens_for(Base.metadata, "before_create")
def _strip_server_defaults_for_sqlite(target, connection, **kw):
    if connection.dialect.name == "sqlite":
        for table in target.tables.values():
            for col in table.columns:
                if col.server_default is not None:
                    col.server_default = None

# 1. Cria um banco SQLite em memória apenas para testes (super rápido e não afeta o fastcooking.db real)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal.configure(bind=engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function", autouse=True)
def setup_teardown_db():
    """
    Roda antes e depois de CADA teste.
    Cria as tabelas antes e as destrói logo depois.
    Isso garante que um teste nunca interfira no outro e o CI não quebre.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session():
    """Fornece a sessão do banco para testes que precisarem."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(db_session):
    """
    Fornece o TestClient com a dependência de banco substituída.
    Qualquer rota que use `Depends(get_db)` vai usar o banco em memória.
    """
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
