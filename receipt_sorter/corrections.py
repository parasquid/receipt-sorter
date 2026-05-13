from __future__ import annotations

from typing import Any

from receipt_sorter.ai import CorrectionParser
from receipt_sorter.memory import append_correction_to_memory
from receipt_sorter.models import Correction


def should_handle_correction_message(message: Any) -> bool:
    text = getattr(message, "text", None)
    return bool(text and not text.startswith("/"))


def correction_original_summary(message: Any) -> str:
    reply_to = getattr(message, "reply_to_message", None)
    if reply_to:
        original_summary = getattr(reply_to, "text", None) or getattr(reply_to, "caption", None)
        if original_summary:
            return original_summary
    return "(No original summary; user sent a standalone correction.)"


def format_correction_confirmation(correction: Correction) -> str | None:
    if not correction.vendor or not correction.new_category:
        return None
    return f"Got it. {correction.vendor} -> {correction.new_category}. Updated memory."


def build_correction_input(original_summary: str, user_reply: str) -> str:
    return f"""# Original classification summary
{original_summary}

# User reply
{user_reply}

Parse the correction and return Correction."""


async def parse_and_apply_correction(
    parser: CorrectionParser,
    original_summary: str,
    user_reply: str,
    memory_path: str,
) -> Correction:
    correction = await parser.parse(original_summary, user_reply)
    if correction.vendor and correction.new_category:
        append_correction_to_memory(
            memory_path,
            correction.vendor,
            correction.new_category,
            correction.reason,
        )
    return correction
