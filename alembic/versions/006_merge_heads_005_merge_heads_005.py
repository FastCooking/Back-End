"""merge_heads_005

Revision ID: 006_merge_heads_005
Revises: 005_aplicacao_desconto, 005_auditoria_cancelamento_item, 005_indices_performance_rnf08
Create Date: 2026-11-25 11:49:20.221027

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '006_merge_heads_005'
down_revision: str | Sequence[str] | None = ('005_aplicacao_desconto', '005_auditoria_cancelamento_item', '005_indices_performance_rnf08')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
