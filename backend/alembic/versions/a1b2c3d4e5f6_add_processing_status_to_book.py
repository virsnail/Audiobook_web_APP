"""add_processing_status_to_book

Revision ID: a1b2c3d4e5f6
Revises: 01437ac187e7
Create Date: 2026-02-06 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '01437ac187e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add processing_status column with default 'ready'
    op.add_column('books', sa.Column('processing_status', sa.String(20), nullable=True, server_default='ready'))
    op.add_column('books', sa.Column('processing_error', sa.Text(), nullable=True))
    
    # Update existing rows to have 'ready' status
    op.execute("UPDATE books SET processing_status = 'ready' WHERE processing_status IS NULL")


def downgrade() -> None:
    op.drop_column('books', 'processing_error')
    op.drop_column('books', 'processing_status')
