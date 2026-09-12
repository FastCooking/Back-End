"""merge column casing and existing migration heads

Revision ID: 9f4a6b7c8d9e
Revises: 002_normalize_column_casing, 7c8e4f1a2b3c
Create Date: 2026-09-12

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "9f4a6b7c8d9e"
down_revision: tuple[str, str] = ("002_normalize_column_casing", "7c8e4f1a2b3c")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
