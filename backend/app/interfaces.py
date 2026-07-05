"""Injection seams. Every 'starting out' component implements one of these
Protocols so it can be swapped (local disk → S3, stub extractor → LLM,
console sender → real email, inline runner → job queue) without touching the
workflow services."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class FieldExtraction:
    """One extracted field with its own confidence (FR-12)."""

    name: str
    label: str
    value: str
    confidence: float
    note: str | None = None
    suggestion: str | None = None

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "value": self.value,
            "confidence": self.confidence,
            "note": self.note,
            "suggestion": self.suggestion,
        }


@dataclass
class ExtractionResult:
    doc_type: str
    doc_type_confidence: float
    fields: list[FieldExtraction] = field(default_factory=list)
    model_version: str = ""
    prompt_version: str = ""


class DocumentExtractor(Protocol):
    """FR-10/11/12: classify a document and extract per-field values+confidence."""

    def extract(self, *, filename: str, content: bytes, sender: str) -> ExtractionResult: ...


class FileStorage(Protocol):
    """Raw, immutable attachment storage (FR-05). Save-once; no update method on
    purpose — raw items are never modified."""

    def save(self, org_id: str, filename: str, content: bytes) -> str: ...

    def load(self, storage_key: str) -> bytes: ...


class MessageSender(Protocol):
    """Outbound client communication. Only ever invoked after explicit human
    approval (FR-31) — callers must go through followup.approve_and_send()."""

    def send(self, *, channel: str, recipient: str, subject: str, body: str) -> str: ...


class TaskRunner(Protocol):
    """Pipeline execution seam: inline today, job queue later."""

    def submit(self, fn: Callable[[], None]) -> None: ...


class Drafter(Protocol):
    """Drafts outbound/office text (document requests, opdrachtbrief, deadline
    reminders). Template-based today, LLM-backed later. Output is always a
    draft — the FR-31 human-approval gate in the service layer is what turns a
    draft into something sent."""

    def draft(self, kind: str, context: dict) -> str: ...
