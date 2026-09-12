"""merge column casing and existing migration heads

Revision ID: 9f4a6b7c8d9e
Revises: 9d4e6f8a1b2c
Create Date: 2026-09-12

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "9f4a6b7c8d9e"
down_revision: str = "9d4e6f8a1b2c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
