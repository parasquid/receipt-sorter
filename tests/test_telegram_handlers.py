import asyncio

from receipt_sorter.config import Config
from receipt_sorter.models import Correction, DocumentResult, ProcessedDocument, SessionState
from receipt_sorter.telegram_bot import telegram_correction_handler, telegram_pdf_handler


class FakeApplication:
    def __init__(self, bot_data):
        self.bot_data = bot_data


class FakeContext:
    def __init__(self, bot_data):
        self.application = FakeApplication(bot_data)


class FakeChat:
    id = 12345


class FakeTelegramFile:
    async def download_as_bytearray(self):
        return bytearray(b"%PDF")


class FakeDocument:
    file_name = "receipt.pdf"
    mime_type = "application/pdf"

    async def get_file(self):
        return FakeTelegramFile()


class FakeMessage:
    def __init__(self, text=None, document=None):
        self.text = text
        self.document = document
        self.replies = []
        self.reply_to_message = None

    async def reply_text(self, text):
        self.replies.append(text)


class FakeUpdate:
    def __init__(self, message):
        self.message = message
        self.effective_chat = FakeChat()
        self.effective_message = message


class FakeDriveClient:
    def __init__(self):
        self.uploads = []

    async def upload_pdf_to_drive_inbox(self, inbox_folder_id, filename, pdf_bytes):
        self.uploads.append((inbox_folder_id, filename, pdf_bytes))
        return {"id": "drive-file-id", "name": filename, "mimeType": "application/pdf"}


class FakeParser:
    async def parse(self, original_summary, user_reply):
        return Correction(
            vendor="Eleven Labs",
            new_category="Marketing & Advertising",
            reason=None,
        )


def test_telegram_pdf_handler_uses_async_drive_client(monkeypatch):
    drive_client = FakeDriveClient()
    message = FakeMessage(document=FakeDocument())
    update = FakeUpdate(message)
    config = Config(accounting_folder_id="accounting-id", inbox_folder_id="inbox-id")
    state = SessionState()

    async def fake_process_file(seen_drive_client, seen_config, drive_file, classifier):
        assert seen_drive_client is drive_client
        assert seen_config is config
        assert drive_file["id"] == "drive-file-id"
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

    monkeypatch.setattr("receipt_sorter.telegram_bot.process_file", fake_process_file)
    context = FakeContext(
        {
            "config": config,
            "drive_client": drive_client,
            "state": state,
            "classifier": object(),
        }
    )

    asyncio.run(telegram_pdf_handler(update, context))

    assert drive_client.uploads == [("inbox-id", "receipt.pdf", b"%PDF")]
    assert state.processed_count == 1
    assert message.replies


def test_telegram_pdf_handler_replies_when_processing_fails(monkeypatch):
    drive_client = FakeDriveClient()
    message = FakeMessage(document=FakeDocument())
    update = FakeUpdate(message)
    config = Config(accounting_folder_id="accounting-id", inbox_folder_id="inbox-id")
    state = SessionState()

    async def fake_process_file(seen_drive_client, seen_config, drive_file, classifier):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("receipt_sorter.telegram_bot.process_file", fake_process_file)
    context = FakeContext(
        {
            "config": config,
            "drive_client": drive_client,
            "state": state,
            "classifier": object(),
        }
    )

    asyncio.run(telegram_pdf_handler(update, context))

    assert drive_client.uploads == [("inbox-id", "receipt.pdf", b"%PDF")]
    assert state.processed_count == 0
    assert state.in_progress_file_ids == set()
    assert message.replies == [
        "I uploaded receipt.pdf to Drive Inbox, but processing failed. "
        "It will stay in Inbox for retry. Error: provider unavailable"
    ]


def test_telegram_correction_handler_uses_fake_parser(tmp_path):
    memory_path = tmp_path / "MEMORY.md"
    memory_path.write_text("# Rules and Corrections\n\n## Corrections\n\n", encoding="utf-8")
    message = FakeMessage(text="eleven labs should be marketing")
    update = FakeUpdate(message)
    context = FakeContext(
        {
            "config": Config(
                accounting_folder_id="accounting-id",
                inbox_folder_id="inbox-id",
                memory_path=str(memory_path),
            ),
            "correction_parser": FakeParser(),
        }
    )

    asyncio.run(telegram_correction_handler(update, context))

    assert "Eleven Labs -> Marketing & Advertising" in memory_path.read_text(encoding="utf-8")
    assert message.replies == ["Got it. Eleven Labs -> Marketing & Advertising. Updated memory."]
