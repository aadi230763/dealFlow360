"""Shared test fixtures.

Two DB strategies are used deliberately:
- `sqlite_session` (in test_notification_rules.py) -- a two-table in-memory SQLite DB,
  for pure unit tests of core/notifications.py that don't need the rest of the schema.
- `db_session`/`client` here -- a real Postgres database (a dedicated `dealflow_test`
  database on the same server the app already talks to), for API-level tests that need
  the full app wired up. Every test runs inside a SAVEPOINT that's rolled back afterwards,
  so tests never leave data behind even though the endpoints under test call db.commit().
"""

import os
import uuid

# Must happen before any `app.*` import: app.core.config.Settings() reads this env var
# once, at import time.
os.environ["DATABASE_URL"] = "postgresql+psycopg2://dealflow:dealflow@db:5432/dealflow_test"

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2 import errors as pg_errors
from sqlalchemy import event

from app.core.config import settings


def _ensure_test_database() -> None:
    # Can't CREATE DATABASE while connected to the DB being created, so connect to the
    # ordinary dev database just to issue that one statement.
    admin_url = settings.database_url.rsplit("/", 1)[0] + "/dealflow"
    conn = psycopg2.connect(admin_url.replace("postgresql+psycopg2://", "postgresql://"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE DATABASE dealflow_test")
    except pg_errors.DuplicateDatabase:
        pass
    finally:
        conn.close()


_ensure_test_database()

from app.core.deps import get_current_user, get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402 -- imports after the test DB exists so create_all lands there
from app.models.base import SessionLocal, engine  # noqa: E402
from app.models.user import Role, User  # noqa: E402


@pytest.fixture()
def db_session():
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = SessionLocal(bind=connection)
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture()
def make_user(db_session):
    def _make(role: Role, email: str, name: str | None = None) -> User:
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=hash_password("password123"),
            name=name or email,
            role=role,
        )
        db_session.add(user)
        db_session.flush()
        return user

    return _make


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def as_user(client):
    """`as_user(some_user).get(...)` -- returns the shared TestClient with
    get_current_user overridden to that user for this call. Because dependency_overrides
    is a plain dict, this can be called again with a different user mid-test to simulate
    a second actor (e.g. a manager acting on a rep's quotation)."""

    def _as(user: User) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: user
        return client

    return _as
