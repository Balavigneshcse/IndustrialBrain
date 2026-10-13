"""Sign-in, lockout, rate limiting, refresh-token rotation and reuse detection, logout, password change."""
from datetime import datetime, timedelta, timezone

import jwt

from conftest import PASSWORDS

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
COOKIE = "indusmind_refresh"


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def refresh_with(client, cookie_value: str):
    client.cookies.clear()
    return client.post(REFRESH, headers={"Cookie": f"{COOKIE}={cookie_value}"})


def test_login_returns_access_token_and_httponly_refresh_cookie(fresh_client):
    resp = fresh_client.post(LOGIN, json={"username": "viewer", "password": PASSWORDS["viewer"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tokenType"] == "bearer" and body["role"] == "viewer" and body["expiresIn"] == 15 * 60
    cookie = resp.headers["set-cookie"].lower()
    assert f"{COOKIE}=" in cookie and "httponly" in cookie and "path=/api" in cookie and "samesite=strict" in cookie
    assert fresh_client.get("/api/v1/auth/me", headers=bearer(body["token"])).json()["username"] == "viewer"


def test_wrong_password_returns_problem_json(fresh_client):
    resp = fresh_client.post(LOGIN, json={"username": "viewer", "password": "wrong-password"})
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 401 and body["detail"] == "Incorrect username or password" and body["requestId"]


def test_unknown_user_gets_the_same_message(fresh_client):
    resp = fresh_client.post(LOGIN, json={"username": "no-such-user", "password": "whatever-123"})
    assert resp.status_code == 401 and resp.json()["detail"] == "Incorrect username or password"


def test_lockout_after_repeated_failures_until_admin_reset(fresh_client, client, settings):
    for _ in range(settings.max_failed_logins):
        assert fresh_client.post(LOGIN, json={"username": "locktest", "password": "bad-guess-1"}).status_code == 401
    locked = fresh_client.post(LOGIN, json={"username": "locktest", "password": PASSWORDS["locktest"]})
    assert locked.status_code == 423 and "locked" in locked.json()["detail"]

    user_id = next(u["id"] for u in client.get("/api/v1/users").json() if u["username"] == "locktest")
    assert client.post(f"/api/v1/users/{user_id}/reset-password", json={"newPassword": "Locktest-Pass-2"}).status_code == 200
    assert fresh_client.post(LOGIN, json={"username": "locktest", "password": "Locktest-Pass-2"}).status_code == 200


def test_login_rate_limit_per_ip(fresh_client, settings, monkeypatch):
    monkeypatch.setattr(settings, "login_rate_per_minute", 3)
    responses = [fresh_client.post(LOGIN, json={"username": "nobody", "password": "x"}) for _ in range(4)]
    assert [r.status_code for r in responses] == [401, 401, 401, 429]
    assert int(responses[-1].headers["retry-after"]) >= 1


def test_refresh_rotates_and_reuse_of_an_old_token_ends_all_sessions(fresh_client, monkeypatch):
    import server.app.api.v1.auth as auth_module

    assert fresh_client.post(LOGIN, json={"username": "rotator", "password": PASSWORDS["rotator"]}).status_code == 200
    first = fresh_client.cookies.get(COOKIE)
    rotated = fresh_client.post(REFRESH)
    assert rotated.status_code == 200 and fresh_client.get("/api/v1/auth/me", headers=bearer(rotated.json()["token"])).status_code == 200
    second = fresh_client.cookies.get(COOKIE)
    assert second and second != first

    monkeypatch.setattr(auth_module, "REUSE_GRACE", timedelta(0))
    assert refresh_with(fresh_client, first).status_code == 401   # replay of a rotated token
    assert refresh_with(fresh_client, second).status_code == 401  # ...revoked the whole family


def test_parallel_refresh_within_grace_window_is_not_treated_as_theft(fresh_client):
    assert fresh_client.post(LOGIN, json={"username": "rotator", "password": PASSWORDS["rotator"]}).status_code == 200
    first = fresh_client.cookies.get(COOKIE)
    assert fresh_client.post(REFRESH).status_code == 200
    second = fresh_client.cookies.get(COOKIE)
    assert refresh_with(fresh_client, first).status_code == 401
    assert refresh_with(fresh_client, second).status_code == 200


def test_logout_revokes_the_refresh_token(fresh_client):
    assert fresh_client.post(LOGIN, json={"username": "viewer", "password": PASSWORDS["viewer"]}).status_code == 200
    cookie = fresh_client.cookies.get(COOKIE)
    assert fresh_client.post("/api/v1/auth/logout").status_code == 204
    assert refresh_with(fresh_client, cookie).status_code == 401


def test_expired_tampered_and_wrong_type_tokens_are_rejected(fresh_client, settings):
    secret = settings.secret_key.get_secret_value()
    now = datetime.now(timezone.utc)
    expired = jwt.encode({"sub": "1", "type": "access", "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
                         secret, algorithm="HS256")
    wrong_type = jwt.encode({"sub": "1", "type": "refresh", "iat": now, "exp": now + timedelta(hours=1)}, secret, algorithm="HS256")
    token = fresh_client.post(LOGIN, json={"username": "viewer", "password": PASSWORDS["viewer"]}).json()["token"]
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    for bad in (expired, wrong_type, tampered, "not-a-jwt"):
        resp = fresh_client.get("/api/v1/auth/me", headers=bearer(bad))
        assert resp.status_code == 401 and resp.headers["www-authenticate"] == "Bearer"


def test_change_password_invalidates_old_tokens_and_sessions(fresh_client):
    old = fresh_client.post(LOGIN, json={"username": "changer", "password": PASSWORDS["changer"]})
    old_token, old_cookie = old.json()["token"], fresh_client.cookies.get(COOKIE)
    weak = fresh_client.post("/api/v1/auth/change-password", headers=bearer(old_token),
                             json={"currentPassword": PASSWORDS["changer"], "newPassword": "short"})
    assert weak.status_code == 422
    changed = fresh_client.post("/api/v1/auth/change-password", headers=bearer(old_token),
                                json={"currentPassword": PASSWORDS["changer"], "newPassword": "Changer-New-Pass-2"})
    assert changed.status_code == 200
    assert fresh_client.get("/api/v1/auth/me", headers=bearer(old_token)).status_code == 401
    assert fresh_client.get("/api/v1/auth/me", headers=bearer(changed.json()["token"])).status_code == 200
    assert refresh_with(fresh_client, old_cookie).status_code == 401


def test_disabled_account_cannot_use_its_token(client, fresh_client):
    created = client.post("/api/v1/users", json={"username": "temp-user", "displayName": "Temp", "role": "viewer",
                                                  "password": "Temp-User-Pass-1"})
    assert created.status_code == 201
    token = fresh_client.post(LOGIN, json={"username": "temp-user", "password": "Temp-User-Pass-1"}).json()["token"]
    assert fresh_client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 200
    assert client.patch(f"/api/v1/users/{created.json()['id']}", json={"isActive": False}).status_code == 200
    assert fresh_client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401
