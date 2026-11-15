import os
import sys
from logging.config import fileConfig
from urllib.parse import urlparse, urlunparse

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from app.database import Base, engine, get_database_url

from app.models import (
    user,
    conversation,
    refresh_token,
    password_reset_token,
    hotel,
    booking,
    partner,
    package,
    review,
    destination,
    saved_trip,
)

target_metadata = Base.metadata

def _resolve_db_url():
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme == "postgres":
            parsed = parsed._replace(scheme="postgresql")
        return urlunparse(parsed)

    return engine.url.render_as_string(hide_password=False)

def run_migrations_offline() -> None:
    context.configure(
        url=_resolve_db_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": _resolve_db_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
