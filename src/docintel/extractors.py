from __future__ import annotations

from typing import Protocol

from docintel.extract import classify, extract_fields


class DocumentExtractor(Protocol):
    name: str

    def classify(self, text: str) -> tuple[str, float]: ...

    def extract_fields(self, text: str, classification: str) -> dict: ...


class LocalExtractor:
    """Deterministic lexical extractor used in CI. No OCR, no remote LLM."""

    name = "local"

    def classify(self, text: str) -> tuple[str, float]:
        return classify(text)

    def extract_fields(self, text: str, classification: str) -> dict:
        return extract_fields(text, classification)


class RemoteExtractor:
    """Boundary for an OCR or LLM structured-output adapter.

    Not implemented here. Wire a vendor client and keep LocalExtractor in tests.
    """

    name = "remote"

    def classify(self, text: str) -> tuple[str, float]:
        raise NotImplementedError("OCR/LLM extractor is an adapter, not this default")

    def extract_fields(self, text: str, classification: str) -> dict:
        raise NotImplementedError("OCR/LLM extractor is an adapter, not this default")


def get_extractor(name: str = "local") -> DocumentExtractor:
    if name == "local":
        return LocalExtractor()
    if name == "remote":
        return RemoteExtractor()
    raise ValueError(f"unknown extractor {name}")
