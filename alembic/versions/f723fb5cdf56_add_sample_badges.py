"""Add sample badges

Revision ID: e9f0a1b2c3d4
Revises: 5678  # This should be the revision ID of your last existing migration
Create Date: 2025-08-20 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import table, column
from sqlalchemy import String, Integer

# revision identifiers, used by Alembic.
revision = 'e9f0a1b2c3d4'
down_revision = '5678'  # Change this to match your last existing migration
branch_labels = None
depends_on = None


def upgrade():
    # Check if badge table exists first
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'badge' not in existing_tables:
        # Create badge table if it doesn't exist
        op.create_table('badge',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('icon_url', sa.String(), nullable=True),
            sa.Column('xp_required', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
    
    # Create a table object for the badge table
    badge_table = table('badge',
        column('id', Integer),
        column('name', String),
        column('description', String),
        column('icon_url', String),
        column('xp_required', Integer),
        column('created_at', sa.DateTime)
    )
    
    # Insert sample badges
    op.bulk_insert(badge_table,
        [
            {
                "name": "First Login",
                "description": "Successfully logged in for the first time",
                "icon_url": "https://cdn-icons-png.flaticon.com/512/1828/1828884.png",
                "xp_required": 0
            },
            {
                "name": "Quest Master",
                "description": "Completed your first quest",
                "icon_url": "https://cdn-icons-png.flaticon.com/512/616/616408.png",
                "xp_required": 100
            },
            {
                "name": "Study Streak",
                "description": "Maintained a 7-day study streak",
                "icon_url": "https://cdn-icons-png.flaticon.com/512/3135/3135715.png",
                "xp_required": 500
            },
            {
                "name": "Boss Slayer",
                "description": "Defeated your first boss",
                "icon_url": "https://cdn-icons-png.flaticon.com/512/3474/3474365.png",
                "xp_required": 300
            },
            {
                "name": "Flashcard Master",
                "description": "Mastered 50 flashcards",
                "icon_url": "https://cdn-icons-png.flaticon.com/512/2997/2997890.png",
                "xp_required": 200
            }
        ]
    )


def downgrade():
    # Delete the sample badges
    op.execute("DELETE FROM badge WHERE name IN ('First Login', 'Quest Master', 'Study Streak', 'Boss Slayer', 'Flashcard Master')")
    
    # Optional: Drop the badge table if you want to completely remove it
    # conn = op.get_bind()
    # inspector = sa.inspect(conn)
    # if 'badge' in inspector.get_table_names():
    #     op.drop_table('badge')