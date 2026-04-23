"""
Guía de migraciones con Alembic
================================

1. Inicializar Alembic (solo la primera vez):
   alembic init alembic

2. Editar alembic/env.py para usar modelos y DATABASE_URL de tu app:

   from app.config import settings
   from app.database import Base
   from app.models import *   # importar todos los modelos

   config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
   target_metadata = Base.metadata

   # Para soporte async en env.py:
   from sqlalchemy.ext.asyncio import async_engine_from_config
   ...

3. Crear una migración después de cambiar modelos:
   alembic revision --autogenerate -m "descripcion del cambio"

4. Aplicar migraciones:
   alembic upgrade head

5. Revertir la última migración:
   alembic downgrade -1

6. Ver historial:
   alembic history --verbose

---------------------------------------------------------------
alembic/env.py mínimo para async + pydantic-settings:
---------------------------------------------------------------

import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from alembic import context

from app.config import settings
from app.database import Base
from app.models import *  # noqa — necesario para que autogenerate detecte los modelos

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""

# Este archivo es solo documentación — guarda el contenido de arriba
# en alembic/env.py después de ejecutar `alembic init alembic`
