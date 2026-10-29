import os
from urllib.parse import quote_plus, urlparse, urlunparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        parsed = urlparse(database_url)

        if parsed.scheme in ("postgres", "postgresql"):
            parsed = parsed._replace(scheme="postgresql")

        return urlunparse(parsed)

    return (
        f"postgresql://{settings.POSTGRES_USER}:"
        f"{quote_plus(settings.POSTGRES_PASSWORD)}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}"
        f"/{settings.POSTGRES_DB}"
    )

SQLALCHEMY_DATABASE_URL = get_database_url()

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()