import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from src.database.connection import Base, get_db
from src.app import app

# 1. Cria um banco SQLite em memória apenas para testes (super rápido e não afeta o fastcooking.db real)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
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
