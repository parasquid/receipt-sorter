import asyncio
from typing import Any

from receipt_sorter.ai import DocumentInput
from receipt_sorter.config import Config
from receipt_sorter.models import DocumentResult, NeedsReviewDocument, ProcessedDocument
from receipt_sorter.processor import process_file


class FakeClassifier:
    def __init__(self, result: DocumentResult):
        self.result = result
        self.seen_document: DocumentInput | None = None

    async def classify(
        self,
        document: DocumentInput,
        memory_md_content: str,
        default_currency: str,
    ) -> DocumentResult:
        self.seen_document = document
        return self.result


class FakeDriveClient:
    def __init__(self, sidecar_error: Exception | None = None):
        self.folders: list[tuple[str, str]] = []
        self.moves: list[tuple[str, str, str, str]] = []
        self.sidecars: list[tuple[str, str, dict[str, Any]]] = []
        self.files_by_folder: dict[str, list[str]] = {}
        self.sidecar_error = sidecar_error

    async def list_inbox_pdfs(self, inbox_folder_id: str) -> list[dict[str, str]]:
        return []

    async def list_file_names(self, parent_id: str) -> set[str]:
        return set(self.files_by_folder.get(parent_id, []))

    async def download_pdf(self, file_id: str) -> bytes:
        return b"%PDF bytes"

    async def ensure_child_folder(self, parent_id: str, name: str) -> str:
        self.folders.append((parent_id, name))
        return f"{name}-id"

    async def move_and_rename_file(
        self,
        file_id: str,
        old_parent_id: str,
        new_parent_id: str,
        new_name: str,
    ) -> None:
        self.moves.append((file_id, old_parent_id, new_parent_id, new_name))

    async def create_json_file(
        self,
        parent_id: str,
        filename: str,
        payload: dict[str, Any],
    ) -> dict[str, str]:
        if self.sidecar_error:
            raise self.sidecar_error
        self.sidecars.append((parent_id, filename, payload))
        return {"id": "sidecar-id", "name": filename}

    async def upload_pdf_to_drive_inbox(
        self,
        inbox_folder_id: str,
        filename: str,
        pdf_bytes: bytes,
    ) -> dict[str, str]:
        return {"id": "uploaded-id", "name": filename, "mimeType": "application/pdf"}


def test_process_file_routes_invalid_classification_to_needs_review(monkeypatch):
    drive_client = FakeDriveClient()

    monkeypatch.setattr("receipt_sorter.processor.read_memory", lambda path: "memory text")
    monkeypatch.setattr(
        "receipt_sorter.processor.review_timestamp",
        lambda: "2026-05-12T00:00:00+00:00",
    )

    classifier = FakeClassifier(
        DocumentResult(
            supplier="Vendor",
            category="Office Supplies",
            date="05/12/2026",
            amount=42.0,
            currency="USD",
            confidence=0.8,
        )
    )
    config = Config(accounting_folder_id="accounting-id", inbox_folder_id="inbox-id")

    outcome = asyncio.run(
        process_file(
            drive_client=drive_client,
            config=config,
            file={"id": "file-id", "name": "receipt.pdf", "mimeType": "application/pdf"},
            classifier=classifier,
        )
    )

    assert isinstance(outcome, NeedsReviewDocument)
    assert outcome.original_name == "receipt.pdf"
    assert "YYYY-MM-DD" in outcome.reason
    assert drive_client.folders == [("accounting-id", "Needs Review")]
    assert drive_client.moves == [("file-id", "inbox-id", "Needs Review-id", "receipt.pdf")]
    assert drive_client.sidecars == [
        (
            "Needs Review-id",
            "receipt.pdf.review.json",
            {
                "original_name": "receipt.pdf",
                "original_file_id": "file-id",
                "review_folder": "Needs Review",
                "reason": "Document date must be YYYY-MM-DD: 05/12/2026",
                "stage": "classification_validation",
                "created_at": "2026-05-12T00:00:00+00:00",
                "mime_type": "application/pdf",
            },
        )
    ]
    assert classifier.seen_document is not None
    assert classifier.seen_document.filename == "receipt.pdf"
    assert classifier.seen_document.mime_type == "application/pdf"


def test_process_file_valid_classification_files_document(monkeypatch):
    drive_client = FakeDriveClient()

    monkeypatch.setattr("receipt_sorter.processor.read_memory", lambda path: "memory text")

    classifier = FakeClassifier(
        DocumentResult(
            supplier="Office Shop",
            category="Office Supplies",
            date="2026-05-12",
            amount=42.0,
            currency="USD",
            confidence=0.8,
        )
    )
    config = Config(accounting_folder_id="accounting-id", inbox_folder_id="inbox-id")

    outcome = asyncio.run(
        process_file(
            drive_client=drive_client,
            config=config,
            file={"id": "file-id", "name": "receipt.pdf", "mimeType": "application/pdf"},
            classifier=classifier,
        )
    )

    assert isinstance(outcome, ProcessedDocument)
    assert drive_client.folders == [("accounting-id", "2026"), ("2026-id", "05-May")]
    assert drive_client.moves == [
        ("file-id", "inbox-id", "05-May-id", "OfficeShop_Office_20260512.pdf")
    ]


def test_process_file_suffixes_filename_when_destination_name_exists(monkeypatch):
    drive_client = FakeDriveClient()
    drive_client.files_by_folder["05-May-id"] = [
        "OfficeShop_Office_20260512.pdf",
        "OfficeShop_Office_20260512-2.pdf",
    ]

    monkeypatch.setattr("receipt_sorter.processor.read_memory", lambda path: "memory text")

    classifier = FakeClassifier(
        DocumentResult(
            supplier="Office Shop",
            category="Office Supplies",
            date="2026-05-12",
            amount=42.0,
            currency="USD",
            confidence=0.8,
        )
    )
    config = Config(accounting_folder_id="accounting-id", inbox_folder_id="inbox-id")

    outcome = asyncio.run(
        process_file(
            drive_client=drive_client,
            config=config,
            file={"id": "file-id", "name": "receipt.pdf", "mimeType": "application/pdf"},
            classifier=classifier,
        )
    )

    assert isinstance(outcome, ProcessedDocument)
    assert outcome.new_name == "OfficeShop_Office_20260512-3.pdf"
    assert drive_client.moves == [
        ("file-id", "inbox-id", "05-May-id", "OfficeShop_Office_20260512-3.pdf")
    ]


def test_process_file_keeps_needs_review_outcome_when_sidecar_fails(monkeypatch, capsys):
    drive_client = FakeDriveClient(sidecar_error=RuntimeError("sidecar failed"))
    monkeypatch.setattr("receipt_sorter.processor.read_memory", lambda path: "memory text")

    classifier = FakeClassifier(
        DocumentResult(
            supplier="Vendor",
            category="Office Supplies",
            date="05/12/2026",
            amount=42.0,
            currency="USD",
            confidence=0.8,
        )
    )
    config = Config(accounting_folder_id="accounting-id", inbox_folder_id="inbox-id")

    outcome = asyncio.run(
        process_file(
            drive_client=drive_client,
            config=config,
            file={"id": "file-id", "name": "receipt.pdf", "mimeType": "application/pdf"},
            classifier=classifier,
        )
    )

    assert isinstance(outcome, NeedsReviewDocument)
    assert drive_client.moves == [("file-id", "inbox-id", "Needs Review-id", "receipt.pdf")]
    assert "Failed to create review sidecar" in capsys.readouterr().out
