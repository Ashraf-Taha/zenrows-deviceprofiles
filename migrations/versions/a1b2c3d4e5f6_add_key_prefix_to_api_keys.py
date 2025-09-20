"""add key_prefix to api_keys

Revision ID: a1b2c3d4e5f6
Revises: c20ba405a79e
Create Date: 2025-09-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'c20ba405a79e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('api_keys', sa.Column('key_prefix', sa.String(length=12), nullable=False))
    op.create_index('ix_api_keys_key_prefix', 'api_keys', ['key_prefix'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_api_keys_key_prefix', table_name='api_keys')
    op.drop_column('api_keys', 'key_prefix')
