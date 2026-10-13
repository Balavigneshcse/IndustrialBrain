"""API-level checks for the Phase 0 fixes (now on PostgreSQL), run against the sample corpus."""


def ask(client, question: str, **extra) -> dict:
    resp = client.post("/api/v1/chat/query", json={"question": question, **extra})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_asset_360_finds_evidence_with_exact_tag(client):
    resp = client.get("/api/v1/assets/P-101")
    assert resp.status_code == 200
    body = resp.json()
    assert body["evidenceChunks"] > 0
    assert "pump-p101-maintenance-history.txt" in body["sources"]


def test_partial_tag_is_not_matched(client):
    assert client.get("/api/v1/assets/P-10").status_code == 404


def test_rca_has_evidence_based_causes(client):
    body = client.post("/api/v1/rca/P-101").json()
    assert body["assetTag"] == "P-101"
    assert "bearing wear" in body["probableCauses"]
    assert not any("insufficient" in cause.lower() for cause in body["probableCauses"])


def test_rca_docx_export(client):
    resp = client.get("/api/v1/rca/export/P-101")
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"  # .docx is a zip container


def test_unknown_asset_question_is_refused(client):
    body = ask(client, "Identify risks for compressor C-300")
    assert "No indexed documents mention C-300" in body["answer"]
    assert body["citations"] == []


def test_answers_are_labelled_extractive_not_local_model(client):
    body = ask(client, "Why did Pump P-101 fail repeatedly in 2025?")
    assert body["mode"] == "extractive"
    assert body["citations"]


def test_no_canned_compiler_design_answer(client):
    # Excel rows are flattened to "Column: value", so any sheet with a "Unit" column used to
    # contain "unit:" and trigger a hard-coded Compiler Design answer.
    upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("readings.txt", b"Tag: P-101 | Parameter: Discharge pressure | Value: 15 | Unit: bar\n")},
    )
    assert upload.json()["status"] == "ready"
    body = ask(client, "Tell me about readings.txt")
    assert "Compiler" not in body["answer"] and "Unit 3" not in body["answer"]
    client.delete(f"/api/v1/documents/{upload.json()['id']}")


def test_short_filename_does_not_hijack_retrieval(client):
    upload = client.post("/api/v1/documents/upload", files={"file": ("pump.txt", b"Canteen menu: rice, dal, curd.")})
    body = ask(client, "What safety steps apply before pump maintenance?")
    assert all(c["filename"] != "pump.txt" for c in body["citations"])
    client.delete(f"/api/v1/documents/{upload.json()['id']}")


def test_failed_extraction_is_marked_failed(client):
    resp = client.post("/api/v1/documents/upload", files={"file": ("scan.docx", b"not really a docx")})
    body = resp.json()
    assert body["status"] == "failed"
    assert "DOCX extraction failed" in body["errorMessage"]
    client.delete(f"/api/v1/documents/{body['id']}")


def test_delete_removes_uploaded_file(client, upload_dir):
    body = client.post("/api/v1/documents/upload", files={"file": ("temp-note.txt", b"Valve V-900 inspected.")}).json()
    stored = upload_dir / f"{body['documentId']}.txt"
    assert stored.exists()
    assert client.delete(f"/api/v1/documents/{body['id']}").status_code == 200
    assert not stored.exists()
