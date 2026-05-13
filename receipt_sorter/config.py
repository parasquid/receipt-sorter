from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_OPENAI_MODEL = "gpt-5.5"
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class Config:
    accounting_folder_id: str
    inbox_folder_id: str
    openai_api_key: str = ""
    openai_model: str = DEFAULT_OPENAI_MODEL
    poll_interval_drive: int = 5
    memory_path: str = "MEMORY.md"
    default_currency: str = "USD"
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


def parse_config(env_path: str | os.PathLike[str] = ".env") -> Config:
    load_dotenv(dotenv_path=Path(env_path), override=False)
    accounting_folder_id = os.environ.get("DRIVE_ACCOUNTING_FOLDER_ID")
    inbox_folder_id = os.environ.get("DRIVE_INBOX_FOLDER_ID")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not accounting_folder_id or not inbox_folder_id:
        raise RuntimeError("DRIVE_ACCOUNTING_FOLDER_ID and DRIVE_INBOX_FOLDER_ID must be set")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY must be set")
    poll_interval_drive = parse_poll_interval(os.environ.get("POLL_INTERVAL_DRIVE", "5"))
    default_currency = os.environ.get("DEFAULT_CURRENCY", "USD").upper()
    if not CURRENCY_PATTERN.fullmatch(default_currency):
        raise RuntimeError("DEFAULT_CURRENCY must be a 3-letter ISO currency code")
    return Config(
        accounting_folder_id=accounting_folder_id,
        inbox_folder_id=inbox_folder_id,
        openai_api_key=openai_api_key,
        openai_model=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        poll_interval_drive=poll_interval_drive,
        default_currency=default_currency,
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID") or None,
    )


def parse_poll_interval(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("POLL_INTERVAL_DRIVE must be an integer >= 1") from exc
    if value < 1:
        raise RuntimeError("POLL_INTERVAL_DRIVE must be an integer >= 1")
    return value
