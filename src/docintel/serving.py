from __future__ import annotations

import uuid

from fastapi import FastAPI, Header, HTTPException, Request

from docintel.config import Settings, get_settings
from docintel.schemas import SubmitRequest
from docintel.store import JobStore
from docintel.worker import Processor


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    store = JobStore(settings.store_dir)
    processor = Processor(store, settings)
    app = FastAPI(title="docintel")
    app.state.store = store
    app.state.processor = processor

    def _auth(x_api_key: str | None) -> None:
        if settings.api_key and x_api_key != settings.api_key:
            raise HTTPException(401, "invalid api key")

    @app.middleware("http")
    async def rid(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        return {"ready": True, "queued": len(store.queued_ids())}

    @app.post("/v1/documents")
    def submit(body: SubmitRequest, x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        record = store.create(body)
        processor.drain()
        return store.get(record.job_id).model_dump()

    @app.get("/v1/jobs/{job_id}")
    def job(job_id: str, x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        try:
            return store.get(job_id).model_dump()
        except KeyError as exc:
            raise HTTPException(404, "unknown job") from exc

    @app.post("/v1/jobs/{job_id}/review")
    def review(job_id: str, payload: dict, x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        record = store.get(job_id)
        if record.status != "needs_review":
            raise HTTPException(409, "job is not waiting for review")
        if payload.get("decision") == "approve":
            record.fields.update(payload.get("fields") or {})
            store.append_audit(record, "completed", "human_approve")
        else:
            store.dead_letter(record, "human_reject")
        return store.get(job_id).model_dump()

    @app.get("/v1/dead-letter")
    def dlq(x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        return {"jobs": store.dead_letter_ids()}

    @app.post("/v1/worker/drain")
    def drain(x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        return {"processed": processor.drain()}

    return app


app = create_app()
