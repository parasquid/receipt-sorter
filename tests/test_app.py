import asyncio
from contextlib import suppress
from typing import Any, cast

from receipt_sorter import app
from receipt_sorter.ai import CorrectionParser, DocumentClassifier, DocumentInput
from receipt_sorter.app import poll_drive_once, process_drive_batch
from receipt_sorter.config import Config
from receipt_sorter.drive import DriveClient
from receipt_sorter.models import DocumentResult, ProcessedDocument, SessionState


class FakeClassifier:
    async def classify(
        self,
        document: DocumentInput,
        memory_md_content: str,
        default_currency: str,
    ) -> DocumentResult:
        raise AssertionError("process_file is monkeypatched in these tests")


class FakeDriveClient:
    def __init__(self, files):
        self.files = files

    async def list_inbox_pdfs(self, inbox_folder_id):
        return self.files

    async def list_file_names(self, parent_id: str) -> set[str]:
        return set()

    async def download_pdf(self, file_id: str) -> bytes:
        return b"%PDF"

    async def upload_pdf_to_drive_inbox(
        self,
        inbox_folder_id: str,
        filename: str,
        pdf_bytes: bytes,
    ) -> dict[str, str]:
        return {"id": "uploaded-id", "name": filename, "mimeType": "application/pdf"}

    async def ensure_child_folder(self, parent_id: str, name: str) -> str:
        return f"{name}-id"

    async def move_and_rename_file(
        self,
        file_id: str,
        old_parent_id: str,
        new_parent_id: str,
        new_name: str,
    ) -> None:
        return None

    async def create_json_file(
        self,
        parent_id: str,
        filename: str,
        payload: dict[str, Any],
    ) -> dict[str, str]:
        return {"id": "sidecar-id", "name": filename}


def test_process_drive_batch_processes_files_and_updates_state(monkeypatch):
    config = Config(accounting_folder_id="accounting-id", inbox_folder_id="inbox-id")
    state = SessionState()
    drive_client = FakeDriveClient([{"id": "file-id", "name": "receipt.pdf"}])
    classifier = FakeClassifier()

    async def fake_process_file(seen_drive_client, seen_config, file, seen_classifier):
        assert seen_drive_client is drive_client
        assert seen_config is config
        assert seen_classifier is classifier
        assert file["id"] == "file-id"
        return ProcessedDocument(
            original_name="receipt.pdf",
            destination_year="2026",
            destination_month="05-May",
            new_name="Vendor_Office_20260512.pdf",
            result=DocumentResult(
                supplier="Vendor",
                category="Office Supplies",
                date="2026-05-12",
                amount=42.0,
                currency="USD",
                confidence=0.9,
            ),
        )

    monkeypatch.setattr("receipt_sorter.app.process_file", fake_process_file)

    processed = asyncio.run(process_drive_batch(config, drive_client, classifier, state))

    assert len(processed) == 1
    assert state.processed_count == 1


def test_process_drive_batch_leaves_retryable_failures_in_inbox(monkeypatch, capsys):
    config = Config(accounting_folder_id="accounting-id", inbox_folder_id="inbox-id")
    state = SessionState()
    drive_client = FakeDriveClient([{"id": "file-id", "name": "receipt.pdf"}])

    async def fake_process_file(drive_client, config, file, classifier):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("receipt_sorter.app.process_file", fake_process_file)

    processed = asyncio.run(process_drive_batch(config, drive_client, FakeClassifier(), state))

    assert processed == []
    assert state.processed_count == 0
    output = capsys.readouterr().out
    assert "provider unavailable" in output
    assert "Leaving file in Inbox" in output


def test_poll_drive_logs_degraded_mode_during_loop(monkeypatch, capsys):
    config = Config(accounting_folder_id="accounting-id", inbox_folder_id="inbox-id")
    state = SessionState(telegram_available=False)

    class StopPolling(BaseException):
        pass

    async def fake_poll_drive_once(config, drive_client, classifier, state):
        raise StopPolling()

    monkeypatch.setattr(app, "poll_drive_once", fake_poll_drive_once)

    with suppress(StopPolling):
        asyncio.run(
            app.poll_drive(
                config,
                classifier=cast(DocumentClassifier, "classifier"),
                state=state,
                drive_client=cast(DriveClient, "drive-client"),
            )
        )

    output = capsys.readouterr().out
    assert "Drive-only degraded mode is active; Telegram is disabled until restart." in output


def test_poll_drive_once_sends_notification_for_processed_batch(monkeypatch):
    config = Config(
        accounting_folder_id="accounting-id",
        inbox_folder_id="inbox-id",
        telegram_bot_token="token",
        telegram_chat_id="12345",
    )
    state = SessionState()
    drive_client = FakeDriveClient([])
    classifier = FakeClassifier()
    processed = [
        ProcessedDocument(
            original_name="receipt.pdf",
            destination_year="2026",
            destination_month="05-May",
            new_name="Vendor_Office_20260512.pdf",
            result=DocumentResult(
                supplier="Vendor",
                category="Office Supplies",
                date="2026-05-12",
                amount=42.0,
                currency="USD",
                confidence=0.9,
            ),
        )
    ]
    sent = []

    async def fake_process_drive_batch(config, drive_client, classifier, state):
        return processed

    async def fake_send_telegram_summary(config, processed_documents):
        sent.append((config.telegram_chat_id, processed_documents))

    monkeypatch.setattr("receipt_sorter.app.process_drive_batch", fake_process_drive_batch)
    monkeypatch.setattr("receipt_sorter.app.send_telegram_summary", fake_send_telegram_summary)

    result = asyncio.run(poll_drive_once(config, drive_client, classifier, state))

    assert result == processed
    assert sent == [("12345", processed)]


def test_poll_drive_once_skips_notification_when_telegram_degraded(monkeypatch, capsys):
    config = Config(
        accounting_folder_id="accounting-id",
        inbox_folder_id="inbox-id",
        telegram_bot_token="token",
        telegram_chat_id="12345",
    )
    state = SessionState(telegram_available=False)
    drive_client = FakeDriveClient([])
    classifier = FakeClassifier()
    processed = [
        ProcessedDocument(
            original_name="receipt.pdf",
            destination_year="2026",
            destination_month="05-May",
            new_name="Vendor_Office_20260512.pdf",
            result=DocumentResult(
                supplier="Vendor",
                category="Office Supplies",
                date="2026-05-12",
                amount=42.0,
                currency="USD",
                confidence=0.9,
            ),
        )
    ]
    sent = []

    async def fake_process_drive_batch(config, drive_client, classifier, state):
        return processed

    async def fake_send_telegram_summary(config, processed_documents):
        sent.append((config.telegram_chat_id, processed_documents))

    monkeypatch.setattr("receipt_sorter.app.process_drive_batch", fake_process_drive_batch)
    monkeypatch.setattr("receipt_sorter.app.send_telegram_summary", fake_send_telegram_summary)

    result = asyncio.run(poll_drive_once(config, drive_client, classifier, state))

    assert result == processed
    assert sent == []
    output = capsys.readouterr().out
    assert "Skipping Telegram summary because server is in Drive-only degraded mode." in output


def test_poll_drive_once_logs_notification_failure_without_failing_batch(monkeypatch, capsys):
    config = Config(
        accounting_folder_id="accounting-id",
        inbox_folder_id="inbox-id",
        telegram_bot_token="token",
        telegram_chat_id="12345",
    )
    state = SessionState()
    drive_client = FakeDriveClient([])
    classifier = FakeClassifier()
    processed = [
        ProcessedDocument(
            original_name="receipt.pdf",
            destination_year="2026",
            destination_month="05-May",
            new_name="Vendor_Office_20260512.pdf",
            result=DocumentResult(
                supplier="Vendor",
                category="Office Supplies",
                date="2026-05-12",
                amount=42.0,
                currency="USD",
                confidence=0.9,
            ),
        )
    ]

    async def fake_process_drive_batch(config, drive_client, classifier, state):
        return processed

    async def fake_send_telegram_summary(config, processed_documents):
        raise RuntimeError("httpx.ConnectError")

    monkeypatch.setattr("receipt_sorter.app.process_drive_batch", fake_process_drive_batch)
    monkeypatch.setattr("receipt_sorter.app.send_telegram_summary", fake_send_telegram_summary)

    result = asyncio.run(poll_drive_once(config, drive_client, classifier, state))

    assert result == processed
    output = capsys.readouterr().out
    assert "Telegram summary failed; Drive processing already completed." in output


def test_main_defaults_to_one_shot_mode(monkeypatch):
    config = Config(accounting_folder_id="accounting-id", inbox_folder_id="inbox-id")
    calls = []

    async def fake_run_once(seen_config):
        calls.append(("once", seen_config))

    async def fake_run_server(seen_config):
        calls.append(("serve", seen_config))

    monkeypatch.setattr(app, "parse_config", lambda: config)
    monkeypatch.setattr(app, "run_once", fake_run_once, raising=False)
    monkeypatch.setattr(app, "run_server", fake_run_server, raising=False)

    app.main([])

    assert calls == [("once", config)]


def test_main_serve_flag_runs_long_lived_mode(monkeypatch):
    config = Config(accounting_folder_id="accounting-id", inbox_folder_id="inbox-id")
    calls = []

    async def fake_run_once(seen_config):
        calls.append(("once", seen_config))

    async def fake_run_server(seen_config):
        calls.append(("serve", seen_config))

    monkeypatch.setattr(app, "parse_config", lambda: config)
    monkeypatch.setattr(app, "run_once", fake_run_once, raising=False)
    monkeypatch.setattr(app, "run_server", fake_run_server, raising=False)

    app.main(["--serve"])

    assert calls == [("serve", config)]


def test_main_handles_keyboard_interrupt_cleanly(monkeypatch, capsys):
    config = Config(accounting_folder_id="accounting-id", inbox_folder_id="inbox-id")

    def fake_asyncio_run(coro):
        coro.close()
        raise KeyboardInterrupt()

    async def fake_run_server(seen_config):
        raise AssertionError("asyncio.run is monkeypatched")

    monkeypatch.setattr(app, "parse_config", lambda: config)
    monkeypatch.setattr(app, "run_server", fake_run_server, raising=False)
    monkeypatch.setattr(app.asyncio, "run", fake_asyncio_run)

    app.main(["--serve"])

    output = capsys.readouterr().out
    assert "Shutdown requested." in output


def test_run_once_processes_drive_without_telegram_notification(monkeypatch):
    config = Config(
        accounting_folder_id="accounting-id",
        inbox_folder_id="inbox-id",
        telegram_bot_token="token",
        telegram_chat_id="12345",
    )
    processed = [
        ProcessedDocument(
            original_name="receipt.pdf",
            destination_year="2026",
            destination_month="05-May",
            new_name="Vendor_Office_20260512.pdf",
            result=DocumentResult(
                supplier="Vendor",
                category="Office Supplies",
                date="2026-05-12",
                amount=42.0,
                currency="USD",
                confidence=0.9,
            ),
        )
    ]
    sent = []

    class FakeAsyncDriveClient:
        def __init__(self, service):
            self.service = service

    async def fake_process_drive_batch(seen_config, drive_client, classifier, state):
        assert seen_config is config
        assert classifier == "classifier"
        assert isinstance(state, SessionState)
        return processed

    async def fake_send_telegram_summary(seen_config, processed_documents):
        sent.append((seen_config, processed_documents))

    monkeypatch.setattr(app, "build_document_classifier", lambda seen_config: "classifier")
    monkeypatch.setattr(app, "drive_service", lambda: "drive-service")
    monkeypatch.setattr(app, "AsyncDriveClient", FakeAsyncDriveClient)
    monkeypatch.setattr(app, "process_drive_batch", fake_process_drive_batch)
    monkeypatch.setattr(app, "send_telegram_summary", fake_send_telegram_summary)

    result = asyncio.run(app.run_once(config))

    assert result == processed
    assert sent == []


def test_run_telegram_bot_with_retries_degrades_after_three_failures(monkeypatch, capsys):
    config = Config(accounting_folder_id="accounting-id", inbox_folder_id="inbox-id")
    state = SessionState()
    attempts = []
    sleeps = []

    async def fake_run_telegram_bot(config, state, classifier, correction_parser, drive_client):
        attempts.append((config, state, classifier, correction_parser, drive_client))
        raise RuntimeError("HTTP 409: https://api.telegram.org/botTOKEN/getUpdates")

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(app, "run_telegram_bot", fake_run_telegram_bot)
    monkeypatch.setattr(app.asyncio, "sleep", fake_sleep)

    asyncio.run(
        app.run_telegram_bot_with_retries(
            config,
            state,
            classifier=cast(DocumentClassifier, "classifier"),
            correction_parser=cast(CorrectionParser, "parser"),
            drive_client=cast(DriveClient, "drive-client"),
            retry_delays_seconds=(5, 30),
            max_attempts=3,
        )
    )

    assert len(attempts) == 3
    assert sleeps == [5, 30]
    assert state.telegram_available is False
    output = capsys.readouterr().out
    assert "Telegram bot unavailable on attempt 1/3." in output
    assert "Retrying Telegram bot in 5s." in output
    assert "Telegram bot unavailable on attempt 2/3." in output
    assert "Retrying Telegram bot in 30s." in output
    assert "Telegram bot unavailable on attempt 3/3." in output
    assert (
        "Telegram unavailable after 3 attempts; continuing in Drive-only degraded mode." in output
    )
    assert "HTTP 409" not in output
    assert "api.telegram.org" not in output
