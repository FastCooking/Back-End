from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker


class Database:
    def __init__(self, database_url: str):
        
        if not database_url:
            raise ValueError("DATABASE_URL não encontrada.")
        
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        self.Base = declarative_base()

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
        except Exception as e:
            print(f"[ERRO] {e}")
            return False