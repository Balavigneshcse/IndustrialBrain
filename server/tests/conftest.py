"""Test setup: a freshly created and migrated PostgreSQL database (indusmind_test) on the compose
database container, a temporary upload folder, and one user per role.

Start the database first:  docker compose up -d db
"""
import asyncio
import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="indusmind-tests-"))
os.environ.update({
    "INDUSMIND_ENV": "test",
    "UPLOAD_DIR": str(_TMP / "uploads"),
    "SECRET_KEY": "test-only-secret-key-0123456789abcdef",
    "LOGIN_RATE_PER_MINUTE": "1000",
    "CHAT_RATE_PER_MINUTE": "1000",
    "UPLOAD_RATE_PER_MINUTE": "1000",
    "REDIS_URL": "",  # no broker: documents are processed inline, rate limits stay in memory
})

from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from server.app.core.config import get_settings  # noqa: E402

TEST_DB = "indusmind_test"
os.environ["DATABASE_URL"] = make_url(get_settings().sqlalchemy_url).set(database=TEST_DB).render_as_string(hide_password=False)
get_settings.cache_clear()

SAMPLE_DATA = Path(__file__).resolve().parents[2] / "sample-data"
# Test-only credentials for the users created below.
PASSWORDS = {
    "admin": "Admin-Test-Pass-1", "engineer": "Engineer-Test-Pass-1", "engineer2": "Engineer2-Test-Pass-1",
    "viewer": "Viewer-Test-Pass-1", "locktest": "Locktest-Pass-1", "rotator": "Rotator-Pass-1",
    "changer": "Changer-Pass-1",
}
ROLES = {"admin": "admin", "engineer": "engineer", "engineer2": "engineer", "viewer": "viewer",
         "locktest": "viewer", "rotator": "viewer", "changer": "viewer"}


async def _recreate_database() -> None:
    admin = create_async_engine(make_url(get_settings().sqlalchemy_url).set(database="postgres"),
                                isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    finally:
        await admin.dispose()


async def _create_users() -> None:
    from server.app.db.session import dispose_engine, get_sessionmaker
    from server.app.services.users import create_user

    async with get_sessionmaker()() as session:
        for username, password in PASSWORDS.items():
            await create_user(session, username, username.title(), ROLES[username], password)
        await session.commit()
    await dispose_engine()


@pytest.fixture(scope="session")
def database() -> str:
    try:
        asyncio.run(_recreate_database())
    except Exception as exc:
        pytest.exit(f"PostgreSQL is not reachable ({type(exc).__name__}: {exc}). "
                    "Start it with: docker compose up -d db", returncode=2)
    from server.app.cli import migrate
    migrate(get_settings().sqlalchemy_url)
    asyncio.run(_create_users())
    return get_settings().sqlalchemy_url


@pytest.fixture(scope="session")
def app(database):
    from server.app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture(scope="session")
def login():
    def _login(client, username: str, password: str | None = None) -> dict:
        resp = client.post("/api/v1/auth/login", json={"username": username, "password": password or PASSWORDS[username]})
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['token']}"}
    return _login


@pytest.fixture(scope="session")
def client(app, login):
    """Admin-authenticated client with the sample corpus uploaded."""
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        test_client.headers.update(login(test_client, "admin"))
        for path in sorted(p for p in SAMPLE_DATA.iterdir() if p.is_file()):
            up = test_client.post("/api/v1/documents/upload", files={"file": (path.name, path.read_bytes())})
            assert up.status_code == 202 and up.json()["status"] == "ready", (path.name, up.text)
        yield test_client


@pytest.fixture
def fresh_client(app):
    """Unauthenticated client with its own cookie jar."""
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def upload_dir() -> Path:
    return get_settings().upload_path


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from server.app.core.ratelimit import limiter
    limiter.reset()
    yield
    limiter.reset()
