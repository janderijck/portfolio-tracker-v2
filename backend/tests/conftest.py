"""
Shared fixtures for API integration tests.

Overrides the database module's DATABASE_PATH so every call to get_db() /
get_connection() within the FastAPI routers uses a temporary SQLite file that
is torn down after each test.
"""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _test_database(tmp_path, monkeypatch):
    """
    Redirect the database module to a fresh temporary SQLite file for each
    test.  Because get_connection() reads DATABASE_PATH on every call, we
    only need to patch the module-level variable.
    """
    db_file = tmp_path / "test_portfolio.db"

    import app.services.database as db_mod

    monkeypatch.setattr(db_mod, "DATABASE_PATH", db_file)

    # Eagerly create tables so the first request doesn't fail.
    conn = db_mod.get_connection()
    conn.close()

    yield


@pytest.fixture()
def client():
    """
    Return a synchronous TestClient that talks to the FastAPI app.

    We import the app *inside* the fixture so that the DATABASE_PATH
    monkeypatch (autouse) is already active.  The app's lifespan context
    manager (APScheduler) is handled by TestClient automatically.
    """
    from app.main import app

    with TestClient(app) as c:
        yield c
