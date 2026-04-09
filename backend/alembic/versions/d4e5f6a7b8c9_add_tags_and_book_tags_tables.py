"""add tags and book_tags tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-09 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 tags 表
    op.create_table(
        'tags',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, index=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True),
                   sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('name', 'owner_id', name='uq_tag_name_owner'),
    )

    # 创建 book_tags 关联表
    op.create_table(
        'book_tags',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('book_id', postgresql.UUID(as_uuid=True),
                   sa.ForeignKey('books.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('tag_id', postgresql.UUID(as_uuid=True),
                   sa.ForeignKey('tags.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('book_id', 'tag_id', name='uq_book_tag'),
    )


def downgrade() -> None:
    op.drop_table('book_tags')
    op.drop_table('tags')
