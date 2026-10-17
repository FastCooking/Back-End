"""Cria tabela Entrega e colunas de controle transacional de entregas no ItemPedido.

Revision ID: 004_controle_entregas_concorrencia
Revises: 003_prioridade_dinamica_kds
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "004_controle_entregas_concorrencia"
down_revision = "003_prioridade_dinamica_kds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ItemPedido",
        sa.Column("deliveryStatus", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "ItemPedido",
        sa.Column(
            "claimedByWaiterId",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "Usuarios.idUsuario", onupdate="CASCADE", ondelete="SET NULL"
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "ItemPedido",
        sa.Column("claimedAt", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ItemPedido",
        sa.Column("deliveredAt", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "Entrega",
        sa.Column(
            "idEntrega",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "idRestaurante",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "Restaurante.idRestaurante", onupdate="CASCADE", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "idPedido",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("Pedido.idPedido", onupdate="CASCADE", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "idItemPedido",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "ItemPedido.idItemPedido", onupdate="CASCADE", ondelete="CASCADE"
            ),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "idGarcom",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "Usuarios.idUsuario", onupdate="CASCADE", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=40),
            nullable=False,
            server_default="WAITING_DELIVERY_PICKUP",
        ),
        sa.Column(
            "dataCriacao",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("claimedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deliveredAt", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("idItemPedido", name="uq_entrega_item_pedido"),
    )

    op.create_index(
        "ix_entrega_fila_fifo",
        "Entrega",
        ["idRestaurante", "status", "dataCriacao"],
    )
    op.create_index(
        "ix_entrega_garcom_status",
        "Entrega",
        ["idGarcom", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_entrega_garcom_status", table_name="Entrega")
    op.drop_index("ix_entrega_fila_fifo", table_name="Entrega")
    op.drop_table("Entrega")
    op.drop_column("ItemPedido", "deliveredAt")
    op.drop_column("ItemPedido", "claimedAt")
    op.drop_column("ItemPedido", "claimedByWaiterId")
    op.drop_column("ItemPedido", "deliveryStatus")

