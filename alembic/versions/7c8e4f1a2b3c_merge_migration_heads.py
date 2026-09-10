"""merge funcionario and login lock migration heads

Revision ID: 7c8e4f1a2b3c
Revises: 27a339618b8f, dd521f39cdfb
Create Date: 2026-09-10

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "7c8e4f1a2b3c"
down_revision: tuple[str, str] = ("27a339618b8f", "dd521f39cdfb")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
