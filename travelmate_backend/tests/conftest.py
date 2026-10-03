"""
Shared test fixtures.

Uses an in-memory SQLite database (rather than requiring a live Postgres
instance) so these tests can run anywhere, including CI without a database
service. This is test-only infrastructure -- it does not change how the app
connects to Postgres in dev/production (see app/database.py).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
# Import all models so their tables are registered on Base.metadata
from app.models import user, favorites, destination, conversation, refresh_token, password_reset_token  # noqa: F401


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
