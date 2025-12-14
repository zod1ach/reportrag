"""Pytest configuration and fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base


@pytest.fixture(scope="function")
def test_db():
    """Create a test database for each test."""
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    yield db

    db.close()
