"""add best_price_seats_left to subscriptions

Revision ID: 1d7cda3b1998
Revises: f0d8daf8ab0b
Create Date: 2026-05-27 19:57:52.912043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d7cda3b1998'
down_revision: Union[str, None] = 'f0d8daf8ab0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('subscriptions', sa.Column('best_price_seats_left', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('subscriptions', 'best_price_seats_left')
