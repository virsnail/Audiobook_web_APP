from logging.config import fileConfig
import os
import sys
from pathlib import Path

from sqlalchemy import engine_from_config, create_engine
from sqlalchemy import pool

from alembic import context

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 只导入模型元数据，不导入异步引擎
from app.database import Base

# 导入所有模型（确保它们被注册到 Base.metadata）
from app.models import user, book

# 导入配置（获取数据库 URL）
from app.config import settings

# this is the Alembic Config object
config = context.config

# 将异步 URL 转换为同步 URL（用于 Alembic）
def get_sync_url():
    """将 asyncpg URL 转换为 psycopg2 URL"""
    url = settings.DATABASE_URL
    # 替换 asyncpg 为 psycopg2（或移除驱动让 SQLAlchemy 自动选择）
    if '+asyncpg' in url:
        url = url.replace('+asyncpg', '')
    return url

# 设置数据库 URL（同步版本）
config.set_main_option('sqlalchemy.url', get_sync_url())

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置目标元数据
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # 创建同步引擎（不使用 NullPool，使用标准连接池）
    connectable = create_engine(
        get_sync_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            compare_type=True,  # 比较列类型
            compare_server_default=True,  # 比较默认值
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

