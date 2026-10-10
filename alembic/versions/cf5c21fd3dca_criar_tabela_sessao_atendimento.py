"""criar tabela sessao atendimento

Revision ID: cf5c21fd3dca
Revises: 002_pedido_sessao_kds
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "cf5c21fd3dca"
down_revision = "002_pedido_sessao_kds"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "Sessao",
        sa.Column(
            "idSessao",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "idMesa",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'Ativa'"),
            nullable=False,
        ),
        sa.Column(
            "dataAbertura",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "dataEncerramento",
            sa.DateTime(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["idMesa"],
            ["Mesa.idMesa"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("idSessao"),
    )

    op.create_index(
        "ix_Sessao_idMesa",
        "Sessao",
        ["idMesa"],
    )

    op.create_index(
        "uq_sessao_ativa_por_mesa",
        "Sessao",
        ["idMesa"],
        unique=True,
        postgresql_where=sa.text("status = 'Ativa'"),
        sqlite_where=sa.text('"status" = \'Ativa\''),
    )


def downgrade():
    op.drop_index(
        "uq_sessao_ativa_por_mesa",
        table_name="Sessao",
    )
    op.drop_index(
        "ix_Sessao_idMesa",
        table_name="Sessao",
    )
    op.drop_table("Sessao")