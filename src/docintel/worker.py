from __future__ import annotations

from docintel.config import Settings
from docintel.extract import should_review
from docintel.extractors import get_extractor
from docintel.store import JobStore


class Processor:
    def __init__(self, store: JobStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings
        self.extractor = get_extractor("local")

    def process_one(self, job_id: str) -> None:
        record = self.store.get(job_id)
        record.attempts += 1
        self.store.append_audit(record, "running", f"attempt {record.attempts}")
        try:
            text = self.store.load_blob(job_id)
            if not text.strip():
                raise ValueError("empty_document")
            classification, confidence = self.extractor.classify(text)
            fields = self.extractor.extract_fields(text, classification)
            record.classification = classification
            record.confidence = confidence
            record.fields = fields
            if should_review(confidence, self.settings.review_confidence, classification):
                self.store.append_audit(record, "needs_review", "confidence")
                return
            self.store.append_audit(record, "completed")
        except Exception as exc:  # noqa: BLE001 — job boundary
            if record.attempts >= self.settings.max_attempts:
                self.store.dead_letter(record, str(exc))
            else:
                record.error = str(exc)
                self.store.append_audit(record, "queued", str(exc))

    def drain(self, limit: int = 32) -> int:
        processed = 0
        for job_id in self.store.queued_ids()[:limit]:
            self.process_one(job_id)
            processed += 1
        return processed
