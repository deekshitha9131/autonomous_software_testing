"""Shared test fixtures for API workflow tests."""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Must set before any app import touches database.py
os.environ["DATABASE_URL"] = "sqlite://"

from app.core import database as db_module
from app.persistence.workflow_run_model import WorkflowRun


def _build_test_engine():
    """Build a single shared in-memory SQLite engine using StaticPool."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


# Replace the app's engine and SessionLocal before any test runs.
_test_engine = _build_test_engine()
db_module.engine = _test_engine
db_module.SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=_test_engine
)


@pytest.fixture(autouse=True)
def _setup_test_db():
    """Create tables before each test and drop them after."""
    db_module.Base.metadata.create_all(_test_engine)
    yield
    db_module.Base.metadata.drop_all(_test_engine)
