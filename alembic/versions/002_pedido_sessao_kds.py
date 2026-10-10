"""Add session and KDS metadata to orders.

Revision ID: 002_pedido_sessao_kds
Revises: 001_initial_uuid_schema
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002_pedido_sessao_kds"
down_revision: str | Sequence[str] | None = "001_initial_uuid_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "Pedido", sa.Column("sessao_id", sa.String(length=100), nullable=True)
    )
    op.create_index("ix_Pedido_sessao_id", "Pedido", ["sessao_id"], unique=False)
    op.add_column(
        "ItemPedido", sa.Column("categoria", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "ItemPedido",
        sa.Column(
            "prioridade", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
    )
    op.alter_column("ItemPedido", "prioridade", server_default=None)


def downgrade() -> None:
    op.drop_column("ItemPedido", "prioridade")
    op.drop_column("ItemPedido", "categoria")
    op.drop_index("ix_Pedido_sessao_id", table_name="Pedido")
    op.drop_column("Pedido", "sessao_id")
