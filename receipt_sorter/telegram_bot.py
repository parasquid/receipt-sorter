from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from telegram.request import BaseRequest

from receipt_sorter.ai import CorrectionParser, DocumentClassifier
from receipt_sorter.config import Config
from receipt_sorter.corrections import (
    correction_original_summary,
    format_correction_confirmation,
    parse_and_apply_correction,
    should_handle_correction_message,
)
from receipt_sorter.drive import AsyncDriveClient, DriveClient, drive_service
from receipt_sorter.formatting import format_batch_summary
from receipt_sorter.log import log_step
from receipt_sorter.models import ProcessingOutcome, SessionState
from receipt_sorter.processor import process_file


def is_pdf_document(document: Any) -> bool:
    if document is None:
        return False
    mime_type = getattr(document, "mime_type", None)
    file_name = getattr(document, "file_name", None) or ""
    return mime_type == "application/pdf" or file_name.lower().endswith(".pdf")


def describe_telegram_message(message: Any) -> str:
    document = getattr(message, "document", None)
    reply_to = getattr(message, "reply_to_message", None)
    reply_to_id = getattr(reply_to, "message_id", None)
    return (
        f"message_id={getattr(message, 'message_id', None)} "
        f"text={getattr(message, 'text', None)!r} "
        f"caption={getattr(message, 'caption', None)!r} "
        f"document={getattr(document, 'file_name', None)!r} "
        f"mime={getattr(document, 'mime_type', None)!r} "
        f"reply_to={reply_to_id}"
    )


async def send_telegram_summary(
    config: Config,
    processed_documents: list[ProcessingOutcome],
) -> None:
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return

    from telegram import Bot

    summary = format_batch_summary(processed_documents)
    log_step(f"Sending Telegram batch summary to {config.telegram_chat_id}.")
    async with Bot(
        config.telegram_bot_token,
        request=build_ipv4_telegram_request(),
    ) as bot:
        await bot.send_message(
            chat_id=config.telegram_chat_id,
            text=summary,
        )
    log_step("Telegram batch summary sent.")


async def start_command(update: Any, context: Any) -> None:
    log_step(f"Telegram /start from chat {update.effective_chat.id}.")
    await update.message.reply_text(
        "Send me a PDF receipt or invoice, or drop PDFs into the Drive Inbox."
    )


async def status_command(update: Any, context: Any) -> None:
    log_step(f"Telegram /status from chat {update.effective_chat.id}.")
    state: SessionState = context.application.bot_data["state"]
    await update.message.reply_text(f"Processed {state.processed_count} documents this session.")


async def telegram_message_logger(update: Any, context: Any) -> None:
    message = update.effective_message
    if message is None:
        log_step("Telegram update received without effective_message.")
        return
    log_step(
        f"Telegram received from chat {update.effective_chat.id}: "
        f"{describe_telegram_message(message)}"
    )


async def telegram_pdf_handler(update: Any, context: Any) -> None:
    document = update.message.document
    log_step(
        "Telegram document message from chat "
        f"{update.effective_chat.id}: name={getattr(document, 'file_name', None)!r}, "
        f"mime={getattr(document, 'mime_type', None)!r}"
    )
    if not is_pdf_document(document):
        await update.message.reply_text("Please send a PDF file.")
        return

    config: Config = context.application.bot_data["config"]
    drive_client: DriveClient = context.application.bot_data["drive_client"]
    telegram_file = await document.get_file()
    pdf_bytes = bytes(await telegram_file.download_as_bytearray())
    drive_file = await drive_client.upload_pdf_to_drive_inbox(
        config.inbox_folder_id,
        document.file_name or "telegram-document.pdf",
        pdf_bytes,
    )
    state: SessionState = context.application.bot_data["state"]
    state.in_progress_file_ids.add(drive_file["id"])
    try:
        classifier: DocumentClassifier = context.application.bot_data["classifier"]
        processed = await process_file(drive_client, config, drive_file, classifier)
        state.processed_count += 1
    except Exception as exc:
        log_step(f"Telegram PDF processing failed for {drive_file['name']}: {exc}")
        await update.message.reply_text(
            f"I uploaded {drive_file['name']} to Drive Inbox, but processing failed. "
            f"It will stay in Inbox for retry. Error: {exc}"
        )
        return
    finally:
        state.in_progress_file_ids.discard(drive_file["id"])
    await update.message.reply_text(format_batch_summary([processed]))


async def telegram_correction_handler(update: Any, context: Any) -> None:
    log_step(f"Telegram correction candidate from chat {update.effective_chat.id}.")
    message = update.message
    if not should_handle_correction_message(message):
        log_step("Ignoring Telegram text because it is not a correction candidate.")
        return

    config: Config = context.application.bot_data["config"]
    parser: CorrectionParser = context.application.bot_data["correction_parser"]
    original_summary = correction_original_summary(message)

    log_step("Parsing Telegram correction text.")
    correction = await parse_and_apply_correction(
        parser=parser,
        original_summary=original_summary,
        user_reply=message.text,
        memory_path=config.memory_path,
    )
    confirmation = format_correction_confirmation(correction)
    if confirmation is None:
        await message.reply_text("I couldn't parse that as a correction.")
        return
    await message.reply_text(confirmation)


async def telegram_error_handler(update: object, context: Any) -> None:
    log_step(f"Telegram handler error: {context.error}")
    message = getattr(update, "effective_message", None)
    if message:
        await message.reply_text(f"Error while handling message: {context.error}")


async def telegram_unhandled_message_handler(update: Any, context: Any) -> None:
    message = update.effective_message
    if message is None:
        log_step("Telegram update received without message.")
        return
    log_step(
        "Unhandled Telegram message: "
        f"chat={update.effective_chat.id}, "
        f"text={getattr(message, 'text', None)!r}, "
        f"document={getattr(getattr(message, 'document', None), 'file_name', None)!r}, "
        f"reply_to={bool(getattr(message, 'reply_to_message', None))}"
    )


def telegram_polling_error_callback(error: object) -> None:
    log_step("Telegram polling error; retrying.")


def build_ipv4_telegram_request() -> BaseRequest:
    import httpx
    from telegram.request import HTTPXRequest

    return HTTPXRequest(
        connect_timeout=10.0,
        read_timeout=30.0,
        httpx_kwargs={
            "transport": httpx.AsyncHTTPTransport(local_address="0.0.0.0", retries=3),
        },
    )


async def run_telegram_bot(
    config: Config,
    state: SessionState,
    classifier: DocumentClassifier,
    correction_parser: CorrectionParser,
    drive_client: DriveClient | None = None,
) -> None:
    if not config.telegram_bot_token:
        log_step("TELEGRAM_BOT_TOKEN not set; Telegram v1 disabled.")
        await asyncio.Event().wait()
        return

    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

    if drive_client is None:
        drive_client = AsyncDriveClient(drive_service())
    application = (
        ApplicationBuilder()
        .token(config.telegram_bot_token)
        .request(build_ipv4_telegram_request())
        .get_updates_request(build_ipv4_telegram_request())
        .build()
    )
    application.bot_data["config"] = config
    application.bot_data["drive_client"] = drive_client
    application.bot_data["state"] = state
    application.bot_data["classifier"] = classifier
    application.bot_data["correction_parser"] = correction_parser
    application.add_handler(MessageHandler(filters.ALL, telegram_message_logger), group=-1)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_correction_handler)
    )
    application.add_handler(MessageHandler(filters.Document.ALL, telegram_pdf_handler))
    application.add_handler(MessageHandler(filters.ALL, telegram_unhandled_message_handler))
    application.add_error_handler(telegram_error_handler)

    log_step("Starting Telegram bot polling.")
    await application.initialize()
    await application.start()
    updater = application.updater
    if updater is None:
        raise RuntimeError("Telegram updater was not initialized")
    await updater.start_polling(error_callback=telegram_polling_error_callback)
    log_step("Telegram bot polling started.")
    cancelled = False
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        cancelled = True
        raise
    finally:
        if cancelled:
            log_step("Telegram bot polling stopped.")
        else:
            await updater.stop()
            await application.stop()
            await application.shutdown()
