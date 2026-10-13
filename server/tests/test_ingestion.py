"""Phase 2: background processing, upload validation, registry, events and evidence-based answers."""
import uuid

V1 = "/api/v1"


def upload(client, name: str, body: bytes):
    return client.post(f"{V1}/documents/upload", files={"file": (name, body)})


def test_upload_returns_202_with_a_job_that_finishes(client):
    resp = upload(client, "pump-note.txt", f"12-Feb-2026 Pump P-101 inspected. {uuid.uuid4()}".encode())
    assert resp.status_code == 202
    body = resp.json()
    job = client.get(f"{V1}/jobs/{body['jobId']}").json()
    assert job["status"] == "succeeded" and job["progress"] == 100 and job["documentId"] == body["id"]
    assert client.get(f"{V1}/documents/{body['id']}").json()["status"] == "ready"
    client.delete(f"{V1}/documents/{body['id']}")


def test_event_stream_reports_the_final_status(client):
    body = upload(client, "stream-note.txt", f"Valve V-310 calibrated. {uuid.uuid4()}".encode()).json()
    with client.stream("GET", f"{V1}/documents/{body['id']}/events") as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        text = "".join(stream.iter_text())
    assert 'event: status' in text and '"status": "ready"' in text
    client.delete(f"{V1}/documents/{body['id']}")


def test_duplicate_upload_is_rejected(client):
    content = f"Compressor C-555 tested. {uuid.uuid4()}".encode()
    first = upload(client, "first.txt", content).json()
    second = upload(client, "second.txt", content)
    assert second.status_code == 409 and second.json()["documentId"] == first["id"]
    assert "first.txt" in second.json()["detail"]
    client.delete(f"{V1}/documents/{first['id']}")


def test_disallowed_or_disguised_files_are_rejected(client):
    assert upload(client, "tool.exe", b"MZ\x90\x00").status_code == 415
    disguised = upload(client, "report.pdf", b"MZ\x90\x00 not a pdf")
    assert disguised.status_code == 415 and "does not match" in disguised.json()["detail"]


def test_reindex_runs_a_new_job(client):
    doc = next(d for d in client.get(f"{V1}/documents").json() if d["filename"] == "safety-sop.txt")
    resp = client.post(f"{V1}/documents/{doc['id']}/reindex")
    assert resp.status_code == 202 and resp.json()["status"] == "ready"
    assert client.get(f"{V1}/jobs/{resp.json()['jobId']}").json()["kind"] == "reindex"


def test_registry_import_and_listing(client, login):
    csv = b"tag,name,class,location,criticality\nP-101,Boiler feed pump,Centrifugal pump,Boiler Feed A,A\nBAD TAG,x,y,z,A\n"
    engineer = login(client, "engineer")
    assert client.post(f"{V1}/assets/import", headers=engineer,
                       files={"file": ("assets.csv", csv)}).status_code == 403
    result = client.post(f"{V1}/assets/import", files={"file": ("assets.csv", csv)}).json()
    assert result["created"] + result["updated"] == 1 and len(result["skipped"]) == 1
    assets = {a["tag"]: a for a in client.get(f"{V1}/assets").json()}
    assert assets["P-101"]["inRegistry"] and assets["P-101"]["criticality"] == "high"
    assert assets["P-101"]["failureEvents"] > 0 and assets["P-101"]["lastEventDate"] >= "2025-11-22"
    assert not assets["C-201"]["inRegistry"]  # discovered in documents only
    detail = client.get(f"{V1}/assets/P-101").json()
    assert detail["name"] == "Boiler feed pump" and detail["inRegistry"]
    bad = client.post(f"{V1}/assets/import", files={"file": ("x.csv", b"name,class\nfoo,bar\n")})
    assert bad.status_code == 422


def test_analytics_counts_events_not_mentions(client):
    body = client.get(f"{V1}/analytics").json()
    ranked = {a["assetTag"]: a for a in body["assetsRankedByRisk"]}
    assert "P-100" not in ranked  # "P-100 series" is no longer an asset
    assert ranked["C-201"]["topFailure"] == "motor trip"
    assert all(f["failure"] != "cavitation" for f in body["topFailureModes"])  # manual text is not an event


def test_out_of_corpus_question_is_refused(client):
    body = client.post(f"{V1}/chat/query", json={"question": "Get me the CGPA in the resume"}).json()
    assert "could not find sufficient evidence" in body["answer"] and body["citations"] == []


def test_citation_relevance_is_the_reranker_probability(client):
    body = client.post(f"{V1}/chat/query", json={"question": "What did the lubricant sample show?"}).json()
    assert body["citations"][0]["filename"] == "pump-p101-inspection-report.txt"
    scores = [c["relevance"] for c in body["citations"]]
    assert scores == sorted(scores, reverse=True) and 0 <= scores[-1] <= scores[0] <= 1
