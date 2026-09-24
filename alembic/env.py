from __future__ import with_statement
from alembic import context
from sqlalchemy import engine_from_config, create_engine, pool
from logging.config import fileConfig
import logging
import os
import sys


# Add the current directory to the path so we can import our app
sys.path.append(os.getcwd())

# Import our Base
from app.core.database import Base
# Read the database URL from environment variable, fallback to .env file
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('DATABASE_URL='):
                    DATABASE_URL = line.strip().split('=', 1)[1].strip()
                    # Remove quotes if present
                    if DATABASE_URL.startswith('"') and DATABASE_URL.endswith('"'):
                        DATABASE_URL = DATABASE_URL[1:-1]
                    elif DATABASE_URL.startswith("'") and DATABASE_URL.endswith("'"):
                        DATABASE_URL = DATABASE_URL[1:-1]
                    break
    except FileNotFoundError:
        pass

# Import the WorkflowRun model to ensure it is registered with Base
from app.persistence.workflow_run_model import WorkflowRun

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
# Configure logger
logger = logging.getLogger('alembic.env')

# Set the main option for the SQLAlchemy URL
# We use the DATABASE_URL from our app's configuration
if DATABASE_URL:
    config.set_main_option('sqlalchemy.url', DATABASE_URL)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
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


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # this_callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    url = DATABASE_URL
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # trigger the process_revision_directives
            process_revision_directives=process_revision_directives
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()