"""empty message

Revision ID: c03bd2cdee43
Revises: 74153c1ecc31
Create Date: 2026-05-03 17:21:06.526230

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c03bd2cdee43'
down_revision: Union[str, Sequence[str], None] = '74153c1ecc31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
