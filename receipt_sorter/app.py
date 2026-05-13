from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence

from receipt_sorter.ai import CorrectionParser, DocumentClassifier
from receipt_sorter.config import Config, parse_config
from receipt_sorter.drive import AsyncDriveClient, DriveClient, drive_service
from receipt_sorter.log import log_step
from receipt_sorter.models import ProcessingOutcome, SessionState
from receipt_sorter.processor import process_file
from receipt_sorter.provider_factory import (
    build_correction_parser,
    build_document_classifier,
)
from receipt_sorter.telegram_bot import run_telegram_bot, send_telegram_summary


async def poll_drive(
    config: Config,
    classifier: DocumentClassifier,
    state: SessionState | None = None,
    drive_client: DriveClient | None = None,
) -> None:
    if state is None:
        state = SessionState()
    if drive_client is None:
        drive_client = AsyncDriveClient(drive_service())
    log_step("Receipt Sorter running.")
    log_step(f"Polling Drive Inbox every {config.poll_interval_drive}s.")
    if config.telegram_bot_token and config.telegram_chat_id:
        log_step(f"Drive notifications enabled for Telegram chat {config.telegram_chat_id}.")
    else:
        log_step("Drive notifications disabled because Telegram config is incomplete.")
    while True:
        try:
            await poll_drive_once(config, drive_client, classifier, state)
        except Exception as exc:
            log_step(f"Drive polling error: {exc}")
            log_step("Pausing for 60s before retrying Drive.")
            await asyncio.sleep(60)
            continue
        await asyncio.sleep(config.poll_interval_drive)


async def poll_drive_once(
    config: Config,
    drive_client: DriveClient,
    classifier: DocumentClassifier,
    state: SessionState,
) -> list[ProcessingOutcome]:
    processed_batch = await process_drive_batch(config, drive_client, classifier, state)
    if processed_batch and config.telegram_bot_token and config.telegram_chat_id:
        await send_telegram_summary(config, processed_batch)
    return processed_batch


async def process_drive_batch(
    config: Config,
    drive_client: DriveClient,
    classifier: DocumentClassifier,
    state: SessionState,
) -> list[ProcessingOutcome]:
    files = await drive_client.list_inbox_pdfs(config.inbox_folder_id)
    if not files:
        log_step("No PDFs in Inbox.")
    processed_batch = []
    for file in files:
        if file["id"] in state.in_progress_file_ids:
            log_step(f"Skipping {file['name']} because it is already processing.")
            continue
        try:
            state.in_progress_file_ids.add(file["id"])
            processed = await process_file(drive_client, config, file, classifier)
            processed_batch.append(processed)
            state.processed_count += 1
        except Exception as exc:
            log_step(f"Failed to process {file.get('name', file.get('id'))}: {exc}")
            log_step("Leaving file in Inbox for manual review.")
        finally:
            state.in_progress_file_ids.discard(file["id"])
    return processed_batch


async def run_once(config: Config) -> list[ProcessingOutcome]:
    log_step("Receipt Sorter one-shot run.")
    log_step("Telegram notifications are disabled in one-shot mode.")
    state = SessionState()
    classifier = build_document_classifier(config)
    return await process_drive_batch(
        config,
        AsyncDriveClient(drive_service()),
        classifier,
        state,
    )


async def run_server(config: Config) -> None:
    state = SessionState()
    classifier = build_document_classifier(config)
    correction_parser = build_correction_parser(config)
    await asyncio.gather(
        poll_drive(config, classifier, state, AsyncDriveClient(drive_service())),
        run_telegram_bot_with_retries(
            config,
            state,
            classifier,
            correction_parser,
            AsyncDriveClient(drive_service()),
        ),
    )


async def run_telegram_bot_with_retries(
    config: Config,
    state: SessionState,
    classifier: DocumentClassifier,
    correction_parser: CorrectionParser,
    drive_client: DriveClient,
    retry_delay_seconds: int = 60,
) -> None:
    while True:
        try:
            await run_telegram_bot(config, state, classifier, correction_parser, drive_client)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log_step(f"Telegram bot error: {exc}")
            log_step(f"Retrying Telegram bot in {retry_delay_seconds}s.")
            await asyncio.sleep(retry_delay_seconds)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Classify and file accounting PDFs from a Google Drive inbox."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="process the Drive inbox once and exit; this is the default",
    )
    mode.add_argument(
        "--serve",
        action="store_true",
        help="run continuous Drive polling and the Telegram bot listener",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    config = parse_config()
    if args.serve:
        asyncio.run(run_server(config))
        return
    asyncio.run(run_once(config))
