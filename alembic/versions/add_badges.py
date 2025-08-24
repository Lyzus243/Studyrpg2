# File: alembic/versions/b4143685ec8b_add_badges.py
"""Add badges

Revision ID: b4143685ec8b
Revises: 5678
Create Date: 2025-08-20 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'b4143685ec8b'
down_revision = '5678'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Create badge table only if it doesn't exist
    if 'badge' not in existing_tables:
        op.create_table('badge',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('icon_url', sa.String(), nullable=True),
            sa.Column('xp_required', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
    
    # Create user_badge association table only if it doesn't exist
    if 'user_badge' not in existing_tables:
        op.create_table('user_badge',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('badge_id', sa.Integer(), nullable=False),
            sa.Column('earned_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
            sa.ForeignKeyConstraint(['badge_id'], ['badge.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'badge_id', name='user_badge_uc')
        )
        
        # Create index on user_badge table
        op.create_index('ix_user_badge_user_id', 'user_badge', ['user_id'], unique=False)


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Drop index if it exists
    if 'user_badge' in existing_tables:
        try:
            op.drop_index('ix_user_badge_user_id', table_name='user_badge')
        except:
            pass  # Index might not exist
    
    # Drop tables if they exist
    if 'user_badge' in existing_tables:
        op.drop_table('user_badge')
    if 'badge' in existing_tables:
        op.drop_table('badge')