import sqlite3
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

engine = sa.create_engine("sqlite:///test_migr.db")
metadata = sa.MetaData()
mesa = sa.Table("Mesa", metadata,
    sa.Column("idMesa", UUID(as_uuid=True), primary_key=True),
    sa.Column("numero", sa.Integer)
)
sessao = sa.Table("Sessao", metadata,
    sa.Column("idSessao", UUID(as_uuid=True), primary_key=True),
    sa.Column("idMesa", UUID(as_uuid=True), sa.ForeignKey("Mesa.idMesa"))
)
metadata.create_all(engine)
print("Sucesso!")
