"""Adiciona dados para prioridade dinâmica e liberação de preparo.

Revision ID: 003_prioridade_dinamica_kds
Revises: cf5c21fd3dca
"""

import sqlalchemy as sa

from alembic import op

revision = "003_prioridade_dinamica_kds"
down_revision = "cf5c21fd3dca"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ItemPedido",
        sa.Column("dataCriacao", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "ItemPedido",
        sa.Column(
            "liberadoParaPreparo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.execute(
        'UPDATE "ItemPedido" '
        'SET "dataCriacao" = CURRENT_TIMESTAMP '
        'WHERE "dataCriacao" IS NULL'
    )

    op.alter_column(
        "ItemPedido",
        "dataCriacao",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )

    op.alter_column(
        "ItemPedido",
        "liberadoParaPreparo",
        existing_type=sa.Boolean(),
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("ItemPedido", "liberadoParaPreparo")
    op.drop_column("ItemPedido", "dataCriacao")