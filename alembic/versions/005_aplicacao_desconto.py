"""Cria tabela LogDesconto e colunas de controle de desconto no Pedido.

Revision ID: 005_aplicacao_desconto
Revises: 004_entregas_concorrencia
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "005_aplicacao_desconto"
down_revision = "004_entregas_concorrencia"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Colunas de desconto na tabela Pedido
    op.add_column(
        "Pedido",
        sa.Column(
            "desconto",
            sa.Numeric(10, 2),
            nullable=False,
            server_default=sa.text("0.0"),
        ),
    )
    op.add_column(
        "Pedido",
        sa.Column("tipoDesconto", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "Pedido",
        sa.Column("valorDescontoInformado", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "Pedido",
        sa.Column("motivoDesconto", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "Pedido",
        sa.Column(
            "idGerenteDesconto",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "Usuarios.idUsuario", onupdate="CASCADE", ondelete="SET NULL"
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "Pedido",
        sa.Column("dataDesconto", sa.DateTime(), nullable=True),
    )

    # 2. Tabela LogDesconto para auditoria de concessão e tentativas
    op.create_table(
        "LogDesconto",
        sa.Column(
            "idLogDesconto",
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
            sa.ForeignKey(
                "Pedido.idPedido", onupdate="CASCADE", ondelete="CASCADE"
            ),
            nullable=True,
        ),
        sa.Column(
            "idUsuario",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "Usuarios.idUsuario", onupdate="CASCADE", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column("usuario", sa.String(length=255), nullable=False),
        sa.Column("funcaoUsuario", sa.String(length=50), nullable=True),
        sa.Column(
            "valorDesconto",
            sa.Numeric(10, 2),
            nullable=False,
            server_default=sa.text("0.0"),
        ),
        sa.Column("tipoDesconto", sa.String(length=20), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column(
            "sucesso",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("motivoFalha", sa.String(length=255), nullable=True),
        sa.Column(
            "dataHora",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_index(
        "idx_LogDesconto_Pedido",
        "LogDesconto",
        ["idPedido"],
    )
    op.create_index(
        "idx_LogDesconto_Restaurante",
        "LogDesconto",
        ["idRestaurante"],
    )


def downgrade() -> None:
    op.drop_index("idx_LogDesconto_Restaurante", table_name="LogDesconto")
    op.drop_index("idx_LogDesconto_Pedido", table_name="LogDesconto")
    op.drop_table("LogDesconto")

    op.drop_column("Pedido", "dataDesconto")
    op.drop_column("Pedido", "idGerenteDesconto")
    op.drop_column("Pedido", "motivoDesconto")
    op.drop_column("Pedido", "valorDescontoInformado")
    op.drop_column("Pedido", "tipoDesconto")
    op.drop_column("Pedido", "desconto")
