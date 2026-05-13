from __future__ import annotations

import re
from datetime import datetime

from receipt_sorter.models import (
    DocumentResult,
    NeedsReviewDocument,
    ProcessedDocument,
    ProcessingOutcome,
)

CATEGORY_SLUGS = {
    "Transport & Travel": "Transport",
    "Meals & Entertainment": "Meals",
    "Software & Subscriptions": "Software",
    "Banking & Finance": "Banking",
    "Salaries & Payroll": "Payroll",
    "Government & Statutory": "Government",
    "Marketing & Advertising": "Marketing",
    "Training & Development": "Training",
    "Equipment & Hardware": "Equipment",
    "Office Supplies": "Office",
}

LEGAL_SUFFIX_PATTERN = re.compile(
    r"\b(?:sdn\.?\s*bhd\.?|bhd\.?|inc\.?|pte\.?\s*ltd\.?|ltd\.?|llc)\b",
    re.IGNORECASE,
)


def normalize_supplier_for_filename(supplier: str) -> str:
    supplier = LEGAL_SUFFIX_PATTERN.sub("", supplier)
    supplier = re.sub(r"[^A-Za-z0-9]+", "", supplier)
    return supplier or "Unknown"


def category_slug(category: str) -> str:
    return CATEGORY_SLUGS.get(category, re.sub(r"[^A-Za-z0-9]+", "", category))


def parse_document_date(document_date: str) -> datetime:
    try:
        return datetime.strptime(document_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Document date must be YYYY-MM-DD: {document_date}") from exc


def build_safe_filename(result: DocumentResult) -> str:
    parsed_date = parse_document_date(result.date)
    supplier = normalize_supplier_for_filename(result.supplier)
    category = category_slug(result.category)
    return f"{supplier}_{category}_{parsed_date:%Y%m%d}.pdf"


def build_available_filename(base_name: str, existing_names: set[str]) -> str:
    if base_name not in existing_names:
        return base_name
    stem, dot, suffix = base_name.rpartition(".")
    if not dot:
        stem = base_name
        suffix = ""
    for counter in range(2, 10_000):
        candidate = f"{stem}-{counter}.{suffix}" if suffix else f"{stem}-{counter}"
        if candidate not in existing_names:
            return candidate
    raise RuntimeError(f"Could not find available filename for {base_name}")


def build_destination_path(result: DocumentResult) -> tuple[str, str]:
    parsed_date = parse_document_date(result.date)
    return parsed_date.strftime("%Y"), parsed_date.strftime("%m-%b")


def display_category(category: str) -> str:
    return CATEGORY_SLUGS.get(category, category)


def format_amount(amount: float | None, currency: str) -> str:
    if amount is None:
        return "-"
    return f"{currency} {amount:,.2f}"


def format_batch_summary(processed_documents: list[ProcessingOutcome]) -> str:
    if not processed_documents:
        return "No documents processed."

    filed_documents = [
        processed for processed in processed_documents if isinstance(processed, ProcessedDocument)
    ]
    review_documents = [
        processed for processed in processed_documents if isinstance(processed, NeedsReviewDocument)
    ]
    if review_documents and not filed_documents:
        return format_needs_review_summary(review_documents)
    if filed_documents and review_documents:
        return format_mixed_batch_summary(filed_documents, review_documents)
    return format_filed_summary(filed_documents)


def format_filed_summary(processed_documents: list[ProcessedDocument]) -> str:
    first = processed_documents[0]
    count = len(processed_documents)
    noun = "document" if count == 1 else "documents"
    lines = [
        f"PROCESSED {count} {noun.upper()}",
        f"Filed to: {first.destination_year}/{first.destination_month}/",
        "",
    ]
    for processed in processed_documents:
        result = processed.result
        category = display_category(result.category)
        amount = format_amount(result.amount, result.currency)
        flag = "  CHECK" if result.confidence < 0.6 else ""
        lines.append(f"{result.supplier:<14} | {category:<14} | {amount}{flag}")
        lines.append(f"-> {processed.new_name}")
    return "\n".join(lines)


def format_needs_review_summary(review_documents: list[NeedsReviewDocument]) -> str:
    count = len(review_documents)
    noun = "document" if count == 1 else "documents"
    first = review_documents[0]
    lines = [
        f"NEEDS REVIEW {count} {noun.upper()}",
        f"Filed to: {first.review_folder_name}/",
        "",
    ]
    for review_document in review_documents:
        lines.append(review_document.original_name)
        lines.append(f"Reason: {review_document.reason}")
    return "\n".join(lines)


def format_mixed_batch_summary(
    filed_documents: list[ProcessedDocument],
    review_documents: list[NeedsReviewDocument],
) -> str:
    count = len(filed_documents) + len(review_documents)
    noun = "document" if count == 1 else "documents"
    lines = [f"PROCESSED {count} {noun.upper()}", ""]
    if filed_documents:
        lines.append(format_filed_summary(filed_documents))
    if review_documents:
        if filed_documents:
            lines.append("")
        lines.append(format_needs_review_summary(review_documents))
    return "\n".join(lines)
