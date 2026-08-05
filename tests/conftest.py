"""Shared pytest fixtures.

Tests run against the real Postgres and Redis containers — the point is to
exercise the actual stack, so no SQLite substitution. Each test gets a fresh
schema in a dedicated database and a flushed cache DB.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import redis as redis_lib
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import create_engine, text

from app import create_app
from app.config import Settings, get_settings
from app.extensions import cache, db

TEST_DB_SUFFIX = "_test"
TEST_CACHE_DB = 15


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Base settings, redirected at throwaway Postgres and Redis databases."""
    base = get_settings()
    computed = {
        "SQLALCHEMY_DATABASE_URI",
        "REDIS_CACHE_URL",
        "REDIS_LIMITER_URL",
        "REDIS_SESSION_URL",
    }
    return Settings(
        **{
            **base.model_dump(exclude=computed),
            "ENV": "testing",
            "DEBUG": False,
            "POSTGRES_DB": f"{base.POSTGRES_DB}{TEST_DB_SUFFIX}",
            "REDIS_DB_CACHE": TEST_CACHE_DB,
            "LOG_LEVEL": "WARNING",
            "LOG_JSON": False,
        }
    )


@pytest.fixture(scope="session")
def _create_test_database(settings: Settings) -> Iterator[None]:
    """Create the test database once per session, drop it at the end."""
    admin_url = settings.SQLALCHEMY_DATABASE_URI.replace(f"/{settings.POSTGRES_DB}", "/postgres")

    def _recreate(drop_only: bool = False) -> None:
        engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{settings.POSTGRES_DB}" WITH (FORCE)'))
            if not drop_only:
                conn.execute(text(f'CREATE DATABASE "{settings.POSTGRES_DB}"'))
        engine.dispose()

    _recreate()
    yield
    _recreate(drop_only=True)


@pytest.fixture(scope="session")
def app(settings: Settings, _create_test_database: None) -> Iterator[Flask]:
    """The application under test.

    Deliberately does NOT hold an app context open across tests. Flask reuses
    an already-pushed app context for incoming test-client requests instead of
    pushing its own, which means teardown_appcontext never fires and the
    request's SQLAlchemy session lingers `idle in transaction` — holding an
    AccessShareLock that makes the inter-test TRUNCATE block forever.
    """
    application = create_app(settings)

    with application.app_context():
        db.create_all()
        db.session.remove()

    yield application

    with application.app_context():
        db.drop_all()
        db.session.remove()


@pytest.fixture(autouse=True)
def _clean_state(app: Flask) -> Iterator[None]:
    """Truncate every table and flush the cache between tests."""
    yield
    with app.app_context():
        db.session.rollback()
        tables = ", ".join(f'"{t.name}"' for t in reversed(db.metadata.sorted_tables))
        if tables:
            # Fail fast rather than hang if some connection leaked a transaction.
            db.session.execute(text("SET LOCAL lock_timeout = '10s'"))
            db.session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
            db.session.commit()
        db.session.remove()
        cache.clear()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def redis_client(settings: Settings) -> Iterator[redis_lib.Redis]:
    conn = redis_lib.Redis.from_url(settings.REDIS_CACHE_URL, decode_responses=True)
    yield conn
    conn.close()


@pytest.fixture
def session(app: Flask) -> Iterator:
    """A database session bound to its own app context."""
    with app.app_context():
        yield db.session
        db.session.remove()
