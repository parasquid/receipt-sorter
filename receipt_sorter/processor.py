from __future__ import annotations

from datetime import UTC, datetime

from receipt_sorter.ai import DocumentClassifier, DocumentInput
from receipt_sorter.classifier import classify_document_with_retry
from receipt_sorter.config import Config
from receipt_sorter.drive import DriveClient
from receipt_sorter.formatting import (
    build_available_filename,
    build_destination_path,
    build_safe_filename,
)
from receipt_sorter.log import log_step
from receipt_sorter.memory import read_memory
from receipt_sorter.models import NeedsReviewDocument, ProcessedDocument, ProcessingOutcome
from receipt_sorter.validation import InvalidClassificationError, validate_document_result

NEEDS_REVIEW_FOLDER_NAME = "Needs Review"
REVIEW_STAGE_CLASSIFICATION = "classification_validation"


async def process_file(
    drive_client: DriveClient,
    config: Config,
    file: dict[str, str],
    classifier: DocumentClassifier,
) -> ProcessingOutcome:
    log_step(f"Processing {file['name']} ({file['id']})...")
    memory_md_content = read_memory(config.memory_path)
    log_step(f"Loaded {config.memory_path} ({len(memory_md_content):,} chars).")
    pdf_bytes = await drive_client.download_pdf(file["id"])
    document = DocumentInput(
        filename=file["name"],
        content=pdf_bytes,
        mime_type=file.get("mimeType", "application/pdf"),
    )
    try:
        result = await classify_document_with_retry(
            classifier,
            document,
            memory_md_content,
            config.default_currency,
        )
        validate_document_result(result)
    except InvalidClassificationError as exc:
        return await move_file_to_needs_review(drive_client, config, file, str(exc))
    log_step(
        "Classification: "
        f"supplier={result.supplier!r}, category={result.category!r}, "
        f"date={result.date}, amount={result.amount}, currency={result.currency}, "
        f"confidence={result.confidence:.2f}"
    )
    destination_year, destination_month = build_destination_path(result)
    log_step(f"Destination path: {destination_year}/{destination_month}/")
    year_folder_id = await drive_client.ensure_child_folder(
        config.accounting_folder_id,
        destination_year,
    )
    month_folder_id = await drive_client.ensure_child_folder(year_folder_id, destination_month)
    base_name = build_safe_filename(result)
    existing_names = await drive_client.list_file_names(month_folder_id)
    new_name = build_available_filename(base_name, existing_names)
    if new_name != base_name:
        log_step(f"Filename already exists; using {new_name}.")
    await drive_client.move_and_rename_file(
        file["id"],
        config.inbox_folder_id,
        month_folder_id,
        new_name,
    )
    log_step(
        f"Filed {file['name']} -> {destination_year}/{destination_month}/{new_name} "
        f"({result.category}, confidence {result.confidence:.2f})"
    )
    return ProcessedDocument(
        original_name=file["name"],
        destination_year=destination_year,
        destination_month=destination_month,
        new_name=new_name,
        result=result,
    )


async def move_file_to_needs_review(
    drive_client: DriveClient,
    config: Config,
    file: dict[str, str],
    reason: str,
) -> NeedsReviewDocument:
    log_step(f"Invalid classification for {file['name']}: {reason}")
    review_folder_id = await drive_client.ensure_child_folder(
        config.accounting_folder_id,
        NEEDS_REVIEW_FOLDER_NAME,
    )
    await drive_client.move_and_rename_file(
        file["id"],
        config.inbox_folder_id,
        review_folder_id,
        file["name"],
    )
    sidecar_payload = build_review_sidecar_payload(file, reason)
    try:
        await drive_client.create_json_file(
            review_folder_id,
            f"{file['name']}.review.json",
            sidecar_payload,
        )
    except Exception as exc:
        log_step(f"Failed to create review sidecar for {file['name']}: {exc}")
    log_step(f"Moved {file['name']} to {NEEDS_REVIEW_FOLDER_NAME}/ for human review.")
    return NeedsReviewDocument(
        original_name=file["name"],
        review_folder_name=NEEDS_REVIEW_FOLDER_NAME,
        reason=reason,
    )


def build_review_sidecar_payload(file: dict[str, str], reason: str) -> dict[str, str]:
    return {
        "original_name": file["name"],
        "original_file_id": file["id"],
        "review_folder": NEEDS_REVIEW_FOLDER_NAME,
        "reason": reason,
        "stage": REVIEW_STAGE_CLASSIFICATION,
        "created_at": review_timestamp(),
        "mime_type": file.get("mimeType", "application/pdf"),
    }


def review_timestamp() -> str:
    return datetime.now(UTC).isoformat()
