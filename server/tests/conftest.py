"""Point the server at a throwaway database, upload folder and vector store.

This must run before any `server.*` import: server.config reads the environment at import
time and server.services.rag_service opens the Chroma store on import.
"""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="indusmind-tests-"))
os.environ["DATABASE_URL"] = "sqlite:///" + (_TMP / "test.db").as_posix()
os.environ["UPLOAD_DIR"] = str(_TMP / "uploads")
os.environ["CHROMA_PATH"] = str(_TMP / "chroma")
os.environ.setdefault("SECRET_KEY", "test-only-secret")

import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DATA = ROOT / "sample-data"


@pytest.fixture(scope="session")
def upload_dir() -> Path:
    return Path(os.environ["UPLOAD_DIR"])


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from server.main import app

    with TestClient(app) as test_client:
        # Demo users come from the seed in server/database.py.
        resp = test_client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
        assert resp.status_code == 200, resp.text
        test_client.headers["Authorization"] = f"Bearer {resp.json()['token']}"
        for path in sorted(p for p in SAMPLE_DATA.iterdir() if p.is_file()):
            up = test_client.post("/api/documents/upload", files={"file": (path.name, path.read_bytes())})
            assert up.status_code == 200 and up.json()["status"] == "ready", (path.name, up.text)
        yield test_client
