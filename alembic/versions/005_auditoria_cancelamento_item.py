"""Cria auditoria persistente para cancelamento de itens.

Revision ID: 005_auditoria_cancelamento_item
Revises: 004_entregas_concorrencia
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "005_auditoria_cancelamento_item"
down_revision = "004_entregas_concorrencia"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "AuditoriaCancelamentoItem",
        sa.Column(
            "idAuditoria",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "idItemPedido",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "ItemPedido.idItemPedido",
                onupdate="CASCADE",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "idPedido",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "Pedido.idPedido",
                onupdate="CASCADE",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "idMesa",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "Mesa.idMesa",
                onupdate="CASCADE",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("sessao_id", sa.String(length=100), nullable=True),
        sa.Column("origem", sa.String(length=20), nullable=False),
        sa.Column("idUsuario", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column(
            "dataHora",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            '"origem" IN (\'CLIENTE\', \'GARCOM\', \'GERENTE\', \'ADM\')',
            name="ck_auditoria_cancelamento_origem",
        ),
        sa.CheckConstraint(
            (
                '("origem" = \'CLIENTE\' AND "idUsuario" IS NULL AND "motivo" IS NULL) '
                "OR "
                '("origem" IN (\'GARCOM\', \'GERENTE\', \'ADM\') '
                'AND "idUsuario" IS NOT NULL AND "motivo" IS NOT NULL '
                'AND length(trim("motivo")) > 0)'
            ),
            name="ck_auditoria_cancelamento_responsavel_motivo",
        ),
    )
    op.create_index(
        "ix_auditoria_cancelamento_item",
        "AuditoriaCancelamentoItem",
        ["idItemPedido"],
    )
    op.create_index(
        "ix_auditoria_cancelamento_pedido",
        "AuditoriaCancelamentoItem",
        ["idPedido"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auditoria_cancelamento_pedido",
        table_name="AuditoriaCancelamentoItem",
    )
    op.drop_index(
        "ix_auditoria_cancelamento_item",
        table_name="AuditoriaCancelamentoItem",
    )
    op.drop_table("AuditoriaCancelamentoItem")
