from sqlmodel import SQLModel

# Expose SQLModel's metadata as Base for Alembic/database setup
Base = SQLModel.metadata