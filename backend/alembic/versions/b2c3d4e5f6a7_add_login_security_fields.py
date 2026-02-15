"""add login security fields

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 登录错误次数限制
    op.add_column('users', sa.Column('failed_login_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('failed_login_date', sa.Date(), nullable=True))
    # 找回密码每日次数限制
    op.add_column('users', sa.Column('forgot_password_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('forgot_password_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'forgot_password_date')
    op.drop_column('users', 'forgot_password_count')
    op.drop_column('users', 'failed_login_date')
    op.drop_column('users', 'failed_login_count')
