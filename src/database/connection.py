import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Carrega as variáveis do arquivo .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("A variável de ambiente 'DATABASE_URL' não foi encontrada. Verifique o seu arquivo .env.")

# Criação da engine de conexão
engine = create_engine(DATABASE_URL)

# Criador de sessões
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para os modelos declarativos
Base = declarative_base()


def get_db():
    """Dependency para obter a sessão do banco de dados (útil em rotas FastAPI)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection():
    """Testa a conexão com o PostgreSQL."""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT current_database();"))
            db_name = result.scalar()
            print(f"[OK] Conexao bem-sucedida com o banco de dados PostgreSQL: '{db_name}'!")
            return True
    except Exception as e:
        print(f"[ERRO] Falha ao conectar ao banco de dados: {e}")
        return False


if __name__ == "__main__":
    test_connection()
