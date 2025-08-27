# File: alembic/versions/20250814_1234_add_admin_features.py
"""Add admin features

Revision ID: 1234
Revises: 
Create Date: 2025-08-14

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '1234'
down_revision = None  # This is now the first migration
branch_labels = None
depends_on = None


def upgrade():
    # Get database connection
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check existing columns in user table
    existing_columns = [col['name'] for col in inspector.get_columns('user')]
    
    # Add new columns to user table only if they don't exist
    if 'role' not in existing_columns:
        op.add_column('user', sa.Column('role', sa.String(), server_default='user', nullable=False))
    
    if 'is_active' not in existing_columns:
        op.add_column('user', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))
    
    if 'is_banned' not in existing_columns:
        op.add_column('user', sa.Column('is_banned', sa.Boolean(), server_default='false', nullable=False))
    
    # Check existing columns in boss_battle table
    boss_battle_columns = [col['name'] for col in inspector.get_columns('boss_battle')]
    if 'is_active' not in boss_battle_columns:
        op.add_column('boss_battle', sa.Column('is_active', sa.Boolean(), server_default='false', nullable=False))
    
    # Check if tables exist before creating them
    existing_tables = inspector.get_table_names()
    
    # Create group_quest association table
    if 'group_quest' not in existing_tables:
        op.create_table('group_quest',
            sa.Column('group_id', sa.Integer(), nullable=False),
            sa.Column('quest_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
            sa.ForeignKeyConstraint(['quest_id'], ['quest.id'], ),
            sa.PrimaryKeyConstraint('group_id', 'quest_id')
        )
    
    # Create feedback table
    if 'feedback' not in existing_tables:
        op.create_table('feedback',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=True),
            sa.Column('email', sa.String(), nullable=True),
            sa.Column('category', sa.String(), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('resolved', sa.Boolean(), server_default='false', nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
    
    # Create admin user if doesn't exist
    op.execute("""
        INSERT INTO "user" (username, email, hashed_password, role, is_active, xp, skill_points, streak, level, currency)
        SELECT 'Lyzus', 'lyzus@admin.com', '$2b$12$L4sJ9qR3tW8yZ1vX2cY6QeTgH7iK8lM9nO0pA1bC3dE4fG5hI6j', 'admin', true, 0, 0, 0, 1, 100
        WHERE NOT EXISTS (
            SELECT 1 FROM "user" WHERE username = 'Lyzus'
        )
    """)


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'feedback' in existing_tables:
        op.drop_table('feedback')
    if 'group_quest' in existing_tables:
        op.drop_table('group_quest')
    
    # Check existing columns before dropping
    boss_battle_columns = [col['name'] for col in inspector.get_columns('boss_battle')]
    if 'is_active' in boss_battle_columns:
        op.drop_column('boss_battle', 'is_active')
    
    user_columns = [col['name'] for col in inspector.get_columns('user')]
    if 'is_banned' in user_columns:
        op.drop_column('user', 'is_banned')
    if 'is_active' in user_columns:
        op.drop_column('user', 'is_active')
    if 'role' in user_columns:
        op.drop_column('user', 'role')