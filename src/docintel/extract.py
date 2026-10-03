from __future__ import annotations

import re

from pydantic import BaseModel, Field, ValidationError


class InvoiceFields(BaseModel):
    invoice_id: str = Field(min_length=3)
    amount: float
    currency: str = Field(min_length=3, max_length=3)


INVOICE_ID = re.compile(r"INV-\d+", re.I)
AMOUNT = re.compile(r"([0-9]+\.[0-9]{2})")
POLICY = re.compile(r"POL-[A-Z0-9]+")


def classify(text: str) -> tuple[str, float]:
    lowered = text.lower()
    if "invoice" in lowered or INVOICE_ID.search(text):
        return "invoice", 0.86
    if "policy" in lowered or POLICY.search(text):
        return "policy", 0.8
    return "unknown", 0.4


def extract_fields(text: str, classification: str) -> dict:
    if classification == "invoice":
        match_id = INVOICE_ID.search(text)
        match_amt = AMOUNT.search(text)
        payload = {
            "invoice_id": match_id.group(0) if match_id else "",
            "amount": float(match_amt.group(1)) if match_amt else 0.0,
            "currency": "USD" if "usd" in text.lower() or "$" in text else "XXX",
        }
        try:
            return InvoiceFields.model_validate(payload).model_dump()
        except ValidationError as exc:
            raise ValueError(f"schema_invalid:{exc.error_count()}") from exc
    if classification == "policy":
        match = POLICY.search(text)
        return {"policy_id": match.group(0) if match else "UNKNOWN"}
    return {}


def should_review(confidence: float, threshold: float, classification: str) -> bool:
    return confidence < threshold or classification == "unknown"
