from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from receipt_sorter.models import Correction, DocumentResult


@dataclass(frozen=True)
class DocumentInput:
    filename: str
    content: bytes
    mime_type: str


class DocumentClassifier(Protocol):
    async def classify(
        self,
        document: DocumentInput,
        memory_md_content: str,
        default_currency: str,
    ) -> DocumentResult: ...


class CorrectionParser(Protocol):
    async def parse(self, original_summary: str, user_reply: str) -> Correction: ...
