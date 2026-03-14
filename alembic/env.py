from __future__ import with_statement

from logging.config import fileConfig
import logging
import os
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

config = context.config

# Guard fileConfig to handle missing logging sections
try:
    if config.config_file_name:
        fileConfig(config.config_file_name)
except Exception:
    pass

logger = logging.getLogger("alembic.env")

target_metadata = None

def get_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        url = "postgresql://vibe:vibe@db:5432/vibe_context"
    # Normalize postgres:// -> postgresql:// for SQLAlchemy
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

def run_migrations_offline():
    url = get_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        url=get_url(),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
