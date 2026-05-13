from __future__ import annotations

from receipt_sorter.formatting import parse_document_date
from receipt_sorter.models import CATEGORY_NAMES, DocumentResult


class InvalidClassificationError(ValueError):
    """Raised when a model response is structurally valid JSON but not fileable."""


def validate_document_result(result: DocumentResult) -> DocumentResult:
    if result.category not in CATEGORY_NAMES:
        raise InvalidClassificationError(f"Unknown category: {result.category}")
    if not result.supplier.strip():
        raise InvalidClassificationError("Supplier is blank")
    if not result.currency.strip():
        raise InvalidClassificationError("Currency is blank")
    try:
        parse_document_date(result.date)
    except ValueError as exc:
        raise InvalidClassificationError(str(exc)) from exc
    return result
