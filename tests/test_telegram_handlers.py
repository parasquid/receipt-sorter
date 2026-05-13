import asyncio
from contextlib import suppress
from typing import cast

from telegram.error import NetworkError

from receipt_sorter.ai import CorrectionParser, DocumentClassifier
from receipt_sorter.config import Config
from receipt_sorter.drive import DriveClient
from receipt_sorter.models import Correction, DocumentResult, ProcessedDocument, SessionState
from receipt_sorter.telegram_bot import (
    build_ipv4_telegram_request,
    run_telegram_bot,
    send_telegram_summary,
    telegram_correction_handler,
    telegram_pdf_handler,
)


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


class StopTelegram(BaseException):
    pass


class FakeTelegramApplication:
    def __init__(self, updater):
        self.bot_data = {}
        self.updater = updater
        self.handlers = []

    def add_handler(self, handler, group=0):
        self.handlers.append((handler, group))

    def add_error_handler(self, handler):
        self.error_handler = handler

    async def initialize(self):
        self.initialized = True

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def shutdown(self):
        self.shutdown_completed = True


class FakeTelegramApplicationBuilder:
    def __init__(self, application):
        self.application = application
        self.seen_token = None
        self.seen_request = None
        self.seen_get_updates_request = None

    def token(self, token):
        self.seen_token = token
        return self

    def request(self, request):
        self.seen_request = request
        return self

    def get_updates_request(self, request):
        self.seen_get_updates_request = request
        return self

    def build(self):
        return self.application


class FakeTelegramEvent:
    async def wait(self):
        raise StopTelegram()


class FakeCancelledTelegramEvent:
    async def wait(self):
        raise asyncio.CancelledError()


class FakeUpdater:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.error_callback = None

    async def start_polling(self, error_callback=None):
        self.started = True
        self.error_callback = error_callback

    async def stop(self):
        self.stopped = True


class ExplodingUpdater(FakeUpdater):
    async def stop(self):
        raise RuntimeError("HTTP 409: https://api.telegram.org/botTOKEN/getUpdates")


def test_build_ipv4_telegram_request_binds_ipv4_with_retries(monkeypatch):
    seen_transport_kwargs = []
    seen_request_kwargs = []

    class FakeTransport:
        def __init__(self, **kwargs):
            seen_transport_kwargs.append(kwargs)

    class FakeHTTPXRequest:
        def __init__(self, **kwargs):
            seen_request_kwargs.append(kwargs)

    import httpx
    import telegram.request

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", FakeTransport)
    monkeypatch.setattr(telegram.request, "HTTPXRequest", FakeHTTPXRequest)

    request = build_ipv4_telegram_request()

    assert isinstance(request, FakeHTTPXRequest)
    assert seen_transport_kwargs == [{"local_address": "0.0.0.0", "retries": 3}]
    assert seen_request_kwargs[0]["connect_timeout"] == 10.0
    assert seen_request_kwargs[0]["read_timeout"] == 30.0
    assert isinstance(seen_request_kwargs[0]["httpx_kwargs"]["transport"], FakeTransport)


def test_run_telegram_bot_logs_when_polling_has_started(monkeypatch, capsys):
    updater = FakeUpdater()
    application = FakeTelegramApplication(updater)
    builder = FakeTelegramApplicationBuilder(application)

    import telegram.ext

    monkeypatch.setattr(telegram.ext, "ApplicationBuilder", lambda: builder)
    monkeypatch.setattr("receipt_sorter.telegram_bot.asyncio.Event", FakeTelegramEvent)

    with suppress(StopTelegram):
        asyncio.run(
            run_telegram_bot(
                Config(
                    accounting_folder_id="accounting-id",
                    inbox_folder_id="inbox-id",
                    telegram_bot_token="token",
                ),
                SessionState(),
                classifier=cast(DocumentClassifier, object()),
                correction_parser=cast(CorrectionParser, object()),
                drive_client=cast(DriveClient, FakeDriveClient()),
            )
        )

    output = capsys.readouterr().out
    assert "Starting Telegram bot polling." in output
    assert "Telegram bot polling started." in output
    assert updater.started is True
    assert updater.stopped is True
    assert updater.error_callback is not None


def test_run_telegram_bot_uses_ipv4_requests(monkeypatch):
    updater = FakeUpdater()
    application = FakeTelegramApplication(updater)
    builder = FakeTelegramApplicationBuilder(application)
    requests = ["standard-request", "polling-request"]

    import telegram.ext

    monkeypatch.setattr(telegram.ext, "ApplicationBuilder", lambda: builder)
    monkeypatch.setattr("receipt_sorter.telegram_bot.asyncio.Event", FakeTelegramEvent)
    monkeypatch.setattr(
        "receipt_sorter.telegram_bot.build_ipv4_telegram_request",
        lambda: requests.pop(0),
    )

    with suppress(StopTelegram):
        asyncio.run(
            run_telegram_bot(
                Config(
                    accounting_folder_id="accounting-id",
                    inbox_folder_id="inbox-id",
                    telegram_bot_token="token",
                ),
                SessionState(),
                classifier=cast(DocumentClassifier, object()),
                correction_parser=cast(CorrectionParser, object()),
                drive_client=cast(DriveClient, FakeDriveClient()),
            )
        )

    assert builder.seen_request == "standard-request"
    assert builder.seen_get_updates_request == "polling-request"


def test_run_telegram_bot_polling_error_callback_is_sanitized(monkeypatch, capsys):
    updater = FakeUpdater()
    application = FakeTelegramApplication(updater)
    builder = FakeTelegramApplicationBuilder(application)

    import telegram.ext

    monkeypatch.setattr(telegram.ext, "ApplicationBuilder", lambda: builder)
    monkeypatch.setattr("receipt_sorter.telegram_bot.asyncio.Event", FakeTelegramEvent)

    with suppress(StopTelegram):
        asyncio.run(
            run_telegram_bot(
                Config(
                    accounting_folder_id="accounting-id",
                    inbox_folder_id="inbox-id",
                    telegram_bot_token="token",
                ),
                SessionState(),
                classifier=cast(DocumentClassifier, object()),
                correction_parser=cast(CorrectionParser, object()),
                drive_client=cast(DriveClient, FakeDriveClient()),
            )
        )

    assert updater.error_callback is not None
    updater.error_callback(
        NetworkError("httpx.ConnectError: https://api.telegram.org/botTOKEN/getUpdates")
    )

    output = capsys.readouterr().out
    assert "Telegram polling error; retrying." in output
    assert "Exception happened while polling for updates." not in output
    assert "httpx.ConnectError" not in output
    assert "api.telegram.org" not in output


def test_run_telegram_bot_cancellation_shutdown_does_not_log_http_errors(monkeypatch, capsys):
    updater = ExplodingUpdater()
    application = FakeTelegramApplication(updater)
    builder = FakeTelegramApplicationBuilder(application)

    import telegram.ext

    monkeypatch.setattr(telegram.ext, "ApplicationBuilder", lambda: builder)
    monkeypatch.setattr("receipt_sorter.telegram_bot.asyncio.Event", FakeCancelledTelegramEvent)

    with suppress(asyncio.CancelledError):
        asyncio.run(
            run_telegram_bot(
                Config(
                    accounting_folder_id="accounting-id",
                    inbox_folder_id="inbox-id",
                    telegram_bot_token="token",
                ),
                SessionState(),
                classifier=cast(DocumentClassifier, object()),
                correction_parser=cast(CorrectionParser, object()),
                drive_client=cast(DriveClient, FakeDriveClient()),
            )
        )

    output = capsys.readouterr().out
    assert "Telegram bot polling stopped." in output
    assert "HTTP 409" not in output
    assert "api.telegram.org" not in output
    assert updater.stopped is False


def test_send_telegram_summary_uses_ipv4_request(monkeypatch):
    seen = {}

    class FakeBot:
        def __init__(self, token, request):
            seen["token"] = token
            seen["request"] = request

        async def __aenter__(self):
            seen["entered"] = True
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            seen["exited"] = True

        async def send_message(self, chat_id, text):
            seen["chat_id"] = chat_id
            seen["text"] = text

    import telegram

    monkeypatch.setattr(telegram, "Bot", FakeBot)
    monkeypatch.setattr(
        "receipt_sorter.telegram_bot.build_ipv4_telegram_request",
        lambda: "ipv4-request",
    )

    asyncio.run(
        send_telegram_summary(
            Config(
                accounting_folder_id="accounting-id",
                inbox_folder_id="inbox-id",
                telegram_bot_token="token",
                telegram_chat_id="12345",
            ),
            [
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
            ],
        )
    )

    assert seen["token"] == "token"
    assert seen["request"] == "ipv4-request"
    assert seen["chat_id"] == "12345"
    assert "Vendor_Office_20260512.pdf" in seen["text"]
    assert seen["entered"] is True
    assert seen["exited"] is True


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
