"""
Shared pytest fixtures for backend integration tests.

Uses TEST_DATABASE_URL (defaults to promptlens_test DB) so tests never touch
the production database.  Each test module gets a fresh schema via the
module-scoped setup_db fixture.
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.client import Base, get_db
from app.main import app

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://promptlens:promptlens@localhost:5432/promptlens_test",
)

_engine = create_engine(TEST_DATABASE_URL)
_TestSession = sessionmaker(bind=_engine)


@pytest.fixture(scope="module")
def db_engine():
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Provide a clean DB session; rolls back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = _TestSession(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="module", autouse=True)
def override_db(db_engine):
    """Wire the FastAPI app to use the test DB for the entire module."""

    def _get_test_db():
        db = _TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)
