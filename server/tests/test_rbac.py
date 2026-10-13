"""Role-based access: viewer reads, engineer uploads and deletes own documents, admin manages users."""
import uuid

import pytest

V1 = "/api/v1"


@pytest.fixture(scope="module")
def as_user(client, login):
    return {name: login(client, name) for name in ("viewer", "engineer", "engineer2")}


def upload(client, headers, name="note.txt", body: bytes | None = None):
    # Unique content per call: identical files are rejected as duplicates.
    body = body or f"Valve V-901 inspected and tested. Ref {uuid.uuid4().hex}".encode()
    return client.post(f"{V1}/documents/upload", headers=headers, files={"file": (name, body)})


@pytest.mark.parametrize("method,path", [
    ("get", "/documents"), ("get", "/dashboard"), ("get", "/analytics"), ("get", "/assets/P-101"),
])
def test_viewer_can_read(client, as_user, method, path):
    assert getattr(client, method)(f"{V1}{path}", headers=as_user["viewer"]).status_code == 200


def test_viewer_can_ask_questions(client, as_user):
    resp = client.post(f"{V1}/chat/query", headers=as_user["viewer"], json={"question": "What did the lubricant sample show?"})
    assert resp.status_code == 200


@pytest.mark.parametrize("method,path", [
    ("post", "/rca/P-101"), ("get", "/rca/export/P-101"), ("get", "/users"),
])
def test_viewer_cannot_write_or_manage(client, as_user, method, path):
    resp = getattr(client, method)(f"{V1}{path}", headers=as_user["viewer"])
    assert resp.status_code == 403 and "requires" in resp.json()["detail"]


def test_viewer_cannot_upload(client, as_user):
    assert upload(client, as_user["viewer"]).status_code == 403


def test_engineer_deletes_own_documents_only(client, as_user):
    own = upload(client, as_user["engineer"]).json()
    assert own["uploadedBy"] == "engineer"
    assert client.delete(f"{V1}/documents/{own['id']}", headers=as_user["engineer2"]).status_code == 403
    assert client.delete(f"{V1}/documents/{own['id']}", headers=as_user["viewer"]).status_code == 403
    assert client.delete(f"{V1}/documents/{own['id']}", headers=as_user["engineer"]).status_code == 200

    admins = upload(client, {}).json()  # the session client is the admin
    assert client.delete(f"{V1}/documents/{admins['id']}", headers=as_user["engineer"]).status_code == 403
    assert client.delete(f"{V1}/documents/{admins['id']}").status_code == 200


def test_engineer_can_generate_rca_but_not_manage_users(client, as_user):
    assert client.post(f"{V1}/rca/P-101", headers=as_user["engineer"]).status_code == 200
    assert client.get(f"{V1}/users", headers=as_user["engineer"]).status_code == 403


def test_admin_user_management_rules(client):
    created = client.post(f"{V1}/users", json={"username": "new.engineer", "displayName": "New Engineer",
                                               "role": "engineer", "password": "New-Engineer-1"})
    assert created.status_code == 201 and created.json()["role"] == "engineer"
    duplicate = client.post(f"{V1}/users", json={"username": "new.engineer", "displayName": "X", "role": "viewer",
                                                 "password": "Another-Pass-1"})
    assert duplicate.status_code == 409
    weak = client.post(f"{V1}/users", json={"username": "weakling", "displayName": "W", "role": "viewer", "password": "abc"})
    assert weak.status_code == 422 and "at least" in weak.json()["detail"]
    bad_role = client.post(f"{V1}/users", json={"username": "boss", "displayName": "B", "role": "superuser",
                                                "password": "Boss-Pass-1234"})
    assert bad_role.status_code == 422

    admin_id = next(u["id"] for u in client.get(f"{V1}/users").json() if u["username"] == "admin")
    assert client.patch(f"{V1}/users/{admin_id}", json={"role": "viewer"}).status_code == 409  # last active admin


def test_feedback_only_on_your_own_answers(client, as_user):
    mine = client.post(f"{V1}/chat/query", headers=as_user["viewer"], json={"question": "What safety steps apply?"}).json()
    admins = client.post(f"{V1}/chat/query", json={"question": "What safety steps apply?"}).json()
    assert client.patch(f"{V1}/chat/{mine['queryId']}/feedback", headers=as_user["viewer"], json={"feedback": 1}).status_code == 200
    assert client.patch(f"{V1}/chat/{admins['queryId']}/feedback", headers=as_user["viewer"], json={"feedback": -1}).status_code == 403
    assert client.patch(f"{V1}/chat/999999/feedback", headers=as_user["viewer"], json={"feedback": 1}).status_code == 404
