"""Contract, legacy alias, health, metrics, headers, upload limits and migration drift."""
import re

V1 = "/api/v1"


def test_every_v1_operation_declares_its_response_schema(client):
    spec = client.get(f"{V1}/openapi.json").json()
    assert spec["paths"], "no paths in the OpenAPI document"
    for path, operations in spec["paths"].items():
        assert path.startswith(V1), f"{path} leaked into the public contract"
        for method, operation in operations.items():
            success = {code: r for code, r in operation["responses"].items() if code.startswith("2")}
            assert success, f"{method.upper()} {path} has no 2xx response"
            for code, response in success.items():
                assert code == "204" or "content" in response, f"{method.upper()} {path} {code} has no schema"


def test_legacy_api_alias_still_serves_the_current_ui(client):
    legacy = client.get("/api/dashboard")
    assert legacy.status_code == 200
    assert legacy.json().keys() == client.get(f"{V1}/dashboard").json().keys()


def test_health_endpoints(client):
    assert client.get("/api/health").json() == {"status": "ok", "service": "indusmind-ai", "version": "3.0.0"}
    assert client.get(f"{V1}/health/live").status_code == 200
    ready = client.get(f"{V1}/health/ready")
    assert ready.status_code == 200
    checks = ready.json()["checks"]
    assert {name: check["status"] for name, check in checks.items()} == {
        "database": "ok", "pgvector": "ok", "uploads": "ok", "models": "ok", "redis": "ok", "worker": "ok", "llm": "ok"}
    assert "inline" in checks["worker"]["detail"]  # tests run without Redis
    assert "LLM_ENABLED=false" in checks["llm"]["detail"]  # and without the language model


def test_metrics_include_language_model_calls(client):
    assert "indusmind_llm_calls_total" in client.get("/metrics").text


def test_metrics_are_exposed(client):
    client.get(f"{V1}/health/live")
    metrics = client.get("/metrics")
    assert metrics.status_code == 200 and "http_request" in metrics.text


def test_request_id_and_security_headers(client):
    resp = client.get(f"{V1}/health/live")
    assert re.fullmatch(r"[0-9a-f]{32}", resp.headers["x-request-id"])
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["cache-control"] == "no-store"
    echoed = client.get(f"{V1}/health/live", headers={"X-Request-ID": "trace-abc-123"})
    assert echoed.headers["x-request-id"] == "trace-abc-123"


def test_errors_are_problem_json(client, fresh_client):
    missing = client.get(f"{V1}/no-such-endpoint")
    assert missing.status_code == 404 and missing.headers["content-type"].startswith("application/problem+json")
    unauthenticated = fresh_client.get(f"{V1}/documents")
    assert unauthenticated.status_code == 401 and unauthenticated.headers["www-authenticate"] == "Bearer"
    invalid = client.post(f"{V1}/chat/query", json={"question": ""})
    assert invalid.status_code == 422 and invalid.json()["errors"]


def test_upload_size_limit_rejects_and_cleans_up(client, settings, monkeypatch, upload_dir):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    before = set(upload_dir.iterdir())
    resp = client.post(f"{V1}/documents/upload", files={"file": ("big.txt", b"x" * (1024 * 1024 + 10))})
    assert resp.status_code == 413 and "1 MB" in resp.json()["detail"]
    assert set(upload_dir.iterdir()) == before


def test_models_and_migrations_are_in_sync(database):
    from alembic import command
    from alembic.config import Config

    from server.app.core.config import REPO_ROOT

    config = Config(str(REPO_ROOT / "server" / "alembic.ini"))
    config.attributes.update(configure_logger=False, sqlalchemy_url=database)
    command.check(config)  # raises if the models have changes no migration covers
