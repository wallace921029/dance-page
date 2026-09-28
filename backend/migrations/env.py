from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

import app.models  # noqa: F401  注册所有数据表
from app.db import Base, create_db_engine

config = context.config

# 应用启动时以代码方式执行迁移，会传入 configure_logger=False，避免覆盖应用的日志配置
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    from app.config import get_settings

    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_db_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        # render_as_batch：SQLite 不支持大部分 ALTER TABLE，改表时用"建新表 + 复制数据"的方式
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
