"""Add UserActivity model

Revision ID: 5678
Revises: 1234
Create Date: 2023-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '5678'
down_revision = '1234'
branch_labels = None
depends_on = None

def upgrade():
    # Check if table already exists
    conn = op.get_bind()
    inspector = inspect(conn)
    
    if 'user_activity' not in inspector.get_table_names():
        op.create_table('user_activity',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('activity_type', sa.String(length=50), nullable=False),
            sa.Column('details', sa.Text(), nullable=True),  # Use Text instead of JSON for SQLite
            sa.Column('timestamp', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Add foreign key index
        op.create_index(op.f('ix_user_activity_user_id'), 'user_activity', ['user_id'], unique=False)

def downgrade():
    # Check if table exists before dropping
    conn = op.get_bind()
    inspector = inspect(conn)
    
    if 'user_activity' in inspector.get_table_names():
        op.drop_index(op.f('ix_user_activity_user_id'), table_name='user_activity')
        op.drop_table('user_activity')