from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from docintel.schemas import JobRecord, JobStatus, SubmitRequest


class JobStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "jobs.json"
        if not self.path.exists():
            self._write({"jobs": {}, "idempotency": {}, "dead_letter": []})

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text())

    def _write(self, payload: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(self.path)

    def create(self, request: SubmitRequest) -> JobRecord:
        data = self._read()
        if request.idempotency_key and request.idempotency_key in data["idempotency"]:
            job_id = data["idempotency"][request.idempotency_key]
            return JobRecord.model_validate(data["jobs"][job_id])
        job_id = uuid4().hex[:16]
        record = JobRecord(
            job_id=job_id,
            document_id=request.document_id,
            filename=request.filename,
            status="queued",
            audit=[self._event("queued")],
        )
        data["jobs"][job_id] = record.model_dump()
        if request.idempotency_key:
            data["idempotency"][request.idempotency_key] = job_id
        self._write(data)
        self._save_blob(job_id, request.text)
        return record

    def _save_blob(self, job_id: str, text: str) -> None:
        blob = self.root / "blobs" / f"{job_id}.txt"
        blob.parent.mkdir(parents=True, exist_ok=True)
        blob.write_text(text)

    def load_blob(self, job_id: str) -> str:
        return (self.root / "blobs" / f"{job_id}.txt").read_text()

    def get(self, job_id: str) -> JobRecord:
        data = self._read()
        if job_id not in data["jobs"]:
            raise KeyError(job_id)
        return JobRecord.model_validate(data["jobs"][job_id])

    def update(self, record: JobRecord) -> JobRecord:
        data = self._read()
        data["jobs"][record.job_id] = record.model_dump()
        self._write(data)
        return record

    def append_audit(self, record: JobRecord, status: JobStatus, detail: str = "") -> JobRecord:
        record.status = status
        record.audit.append(self._event(status, detail))
        return self.update(record)

    def dead_letter(self, record: JobRecord, error: str) -> JobRecord:
        record.error = error
        record.status = "dead_letter"
        record.audit.append(self._event("dead_letter", error))
        data = self._read()
        data["jobs"][record.job_id] = record.model_dump()
        data["dead_letter"].append(record.job_id)
        self._write(data)
        return record

    def queued_ids(self) -> list[str]:
        data = self._read()
        return [job_id for job_id, item in data["jobs"].items() if item["status"] == "queued"]

    def dead_letter_ids(self) -> list[str]:
        return list(self._read()["dead_letter"])

    @staticmethod
    def _event(status: str, detail: str = "") -> dict[str, str]:
        return {"at": datetime.now(timezone.utc).isoformat(), "status": status, "detail": detail}
