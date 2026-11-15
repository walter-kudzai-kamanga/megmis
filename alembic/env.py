from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from megmis.config import get_settings
from megmis.db.base import Base
from megmis.db import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# PostGIS ships tiger/topology helper tables — ignore for alembic check/autogenerate.
_IGNORE_SCHEMAS = {"tiger", "tiger_data", "topology"}
_IGNORE_TABLES = {
    "spatial_ref_sys",
    "geography_columns",
    "geometry_columns",
    "raster_columns",
    "raster_overviews",
}


def include_object(object, name, type_, reflected, compare_to) -> bool:
    if type_ == "table":
        schema = getattr(object, "schema", None)
        if schema in _IGNORE_SCHEMAS:
            return False
        if name in _IGNORE_TABLES:
            return False
    return True


def get_url() -> str:
    return os.getenv("DATABASE_URL") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        include_schemas=False,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            include_schemas=False,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
