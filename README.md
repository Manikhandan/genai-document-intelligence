# GenAI Document Intelligence

Document workloads are not request/response. Classification and field extraction take longer than an HTTP timeout budget, fail in messy ways, and sometimes need a human.

This service accepts a document as text (the extraction boundary), enqueues a job, processes it with retries, and either completes, waits for review, or lands in a dead-letter queue. Idempotency keys make submit retries safe. An API key header is the auth contract.

`DocumentExtractor` is a Protocol: `local` (lexical/schema, used in CI) and `remote` (OCR/LLM adapter that raises `NotImplementedError`). This repository does not run OCR.

## Why asynchronous

A 40-page PDF cannot share a latency SLO with a scoring API. The client stores `job_id`, polls `/v1/jobs/{id}`, and a reviewer hits `/v1/jobs/{id}/review` when confidence is low.

```
Client ─ POST /v1/documents (idempotency-key)
            → JobStore (queued) + blob
            → Processor → DocumentExtractor (local default)
                 classify → field extract → schema
                 ├ completed
                 ├ needs_review → human approve/reject
                 └ retry → dead_letter
```

## Local setup

```bash
pip install -e ".[dev]"
cp .env.example .env
uvicorn docintel.serving:app --port 8000
```

## Tests

```bash
ruff check src tests
pytest -q
```

## Security

Set `DOCINTEL_API_KEY` in any shared environment. Blobs stay on local disk under `var/store/blobs`. This is not a multi-tenant document store.

## Trade-offs

- In-process drain on submit keeps tests deterministic. A separate worker Deployment is the production split; `/v1/worker/drain` is the seam.
- Regex extractors stand in for an LLM structured-output call so CI stays offline. The schema (`InvoiceFields`) is the real contract.

## What I would improve next

- Object storage for blobs and a queue with leases (SQS/PubSub as an adapter, not this default).
- An implementation of `RemoteExtractor` that actually calls OCR or an LLM — still behind the same Protocol.
- Exactly-once processing with a lease on each job.
