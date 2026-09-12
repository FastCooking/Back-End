"""merge all migration heads

Revision ID: 9d4e6f8a1b2c
Revises: 002_normalize_column_casing, 7c8e4f1a2b3c
Create Date: 2026-09-12

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "9d4e6f8a1b2c"
down_revision: tuple[str, str] = (
    "002_normalize_column_casing",
    "7c8e4f1a2b3c",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
