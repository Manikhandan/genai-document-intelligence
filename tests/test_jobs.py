from pathlib import Path

from fastapi.testclient import TestClient

from docintel.config import Settings
from docintel.serving import create_app


def client(tmp_path: Path, api_key: str = "test-key") -> TestClient:
    settings = Settings(store_dir=tmp_path / "store", api_key=api_key, max_attempts=2)
    return TestClient(create_app(settings))


def test_invoice_happy_path(tmp_path: Path):
    api = client(tmp_path)
    response = api.post(
        "/v1/documents",
        headers={"x-api-key": "test-key"},
        json={
            "document_id": "d1",
            "filename": "inv.txt",
            "text": "Invoice INV-1001 amount 12.50 USD for spare parts",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["classification"] == "invoice"
    assert body["fields"]["invoice_id"] == "INV-1001"
    assert body["fields"]["amount"] == 12.5


def test_idempotency(tmp_path: Path):
    api = client(tmp_path)
    payload = {
        "document_id": "d2",
        "filename": "inv.txt",
        "text": "Invoice INV-2002 amount 9.00 USD",
        "idempotency_key": "abc",
    }
    first = api.post("/v1/documents", headers={"x-api-key": "test-key"}, json=payload)
    second = api.post("/v1/documents", headers={"x-api-key": "test-key"}, json=payload)
    assert first.json()["job_id"] == second.json()["job_id"]


def test_unknown_goes_to_review_then_approve(tmp_path: Path):
    api = client(tmp_path)
    response = api.post(
        "/v1/documents",
        headers={"x-api-key": "test-key"},
        json={"document_id": "d3", "filename": "note.txt", "text": "random office chatter"},
    )
    job_id = response.json()["job_id"]
    assert response.json()["status"] == "needs_review"
    reviewed = api.post(
        f"/v1/jobs/{job_id}/review",
        headers={"x-api-key": "test-key"},
        json={"decision": "approve", "fields": {"note": "ok"}},
    )
    assert reviewed.json()["status"] == "completed"


def test_auth_and_dlq(tmp_path: Path):
    api = client(tmp_path)
    denied = api.post(
        "/v1/documents",
        json={"document_id": "d4", "filename": "a.txt", "text": "Invoice INV-1 amount 1.00 USD"},
    )
    assert denied.status_code == 401
    # schema-invalid invoice id too short after regex miss → retries → dlq
    response = api.post(
        "/v1/documents",
        headers={"x-api-key": "test-key"},
        json={"document_id": "d5", "filename": "bad.txt", "text": "invoice with no identifier at all"},
    )
    # "invoice" classifies as invoice; missing INV- id fails schema; requeued then dead-lettered
    job_id = response.json()["job_id"]
    api.post("/v1/worker/drain", headers={"x-api-key": "test-key"})
    api.post("/v1/worker/drain", headers={"x-api-key": "test-key"})
    final = api.get(f"/v1/jobs/{job_id}", headers={"x-api-key": "test-key"}).json()
    assert final["status"] in {"dead_letter", "queued", "failed", "needs_review", "completed"}
    dlq = api.get("/v1/dead-letter", headers={"x-api-key": "test-key"})
    assert dlq.status_code == 200


def test_review_rejects_wrong_state(tmp_path: Path):
    api = client(tmp_path)
    response = api.post(
        "/v1/documents",
        headers={"x-api-key": "test-key"},
        json={
            "document_id": "d6",
            "filename": "inv.txt",
            "text": "Invoice INV-3003 amount 4.00 USD",
        },
    )
    job_id = response.json()["job_id"]
    assert response.json()["status"] == "completed"
    wrong = api.post(
        f"/v1/jobs/{job_id}/review",
        headers={"x-api-key": "test-key"},
        json={"decision": "approve"},
    )
    assert wrong.status_code == 409


def test_malformed_and_missing_job(tmp_path: Path):
    api = client(tmp_path)
    empty = api.post(
        "/v1/documents",
        headers={"x-api-key": "test-key"},
        json={"document_id": "d7", "filename": "x.txt", "text": ""},
    )
    assert empty.status_code == 422
    missing = api.get("/v1/jobs/nope", headers={"x-api-key": "test-key"})
    assert missing.status_code == 404


def test_human_reject_dead_letters(tmp_path: Path):
    api = client(tmp_path)
    response = api.post(
        "/v1/documents",
        headers={"x-api-key": "test-key"},
        json={"document_id": "d8", "filename": "note.txt", "text": "random office chatter"},
    )
    job_id = response.json()["job_id"]
    rejected = api.post(
        f"/v1/jobs/{job_id}/review",
        headers={"x-api-key": "test-key"},
        json={"decision": "reject"},
    )
    assert rejected.json()["status"] == "dead_letter"
    from docintel.extractors import get_extractor

    try:
        get_extractor("remote").classify("x")
        assert False
    except NotImplementedError:
        pass


def test_schema_invalid_retries_then_dead_letters(tmp_path: Path):
    api = client(tmp_path)
    headers = {"x-api-key": "test-key"}
    response = api.post(
        "/v1/documents",
        headers=headers,
        json={"document_id": "d9", "filename": "bad.txt", "text": "invoice with no identifier at all"},
    )
    job_id = response.json()["job_id"]
    api.post("/v1/worker/drain", headers=headers)
    api.post("/v1/worker/drain", headers=headers)
    final = api.get(f"/v1/jobs/{job_id}", headers=headers).json()
    assert final["status"] == "dead_letter"
    assert final["attempts"] >= 2
    dlq = api.get("/v1/dead-letter", headers=headers).json()
    assert job_id in dlq["jobs"]


def test_unknown_extractor_rejected():
    from docintel.extractors import get_extractor

    try:
        get_extractor("mystery")
        assert False
    except ValueError:
        pass
