from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

JobStatus = Literal["queued", "running", "needs_review", "completed", "failed", "dead_letter"]


class SubmitRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=80)
    filename: str = Field(..., min_length=1, max_length=120)
    text: str = Field(..., min_length=1, max_length=20_000)
    content_type: str = "text/plain"
    idempotency_key: str | None = None


class JobRecord(BaseModel):
    job_id: str
    document_id: str
    filename: str
    status: JobStatus
    attempts: int = 0
    classification: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    error: str | None = None
    audit: list[dict[str, Any]] = Field(default_factory=list)
