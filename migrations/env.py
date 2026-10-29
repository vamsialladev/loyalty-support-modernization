"""Alembic environment for the app's database. Business tables arrive in Milestone 6 (spec B.11)."""

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
url = config.get_main_option("sqlalchemy.url") or os.environ["DATABASE_URL"]
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
