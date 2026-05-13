from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

CORRECTION_VENDOR_PATTERN = re.compile(r"^- (?P<vendor>.+?) -> ")
EMPTY_CORRECTIONS_MARKER = "(Empty initially.)"
DEFAULT_MEMORY_EXAMPLE_PATH = "MEMORY.md.example"


def read_memory(
    path: str | os.PathLike[str],
    example_path: str | os.PathLike[str] = DEFAULT_MEMORY_EXAMPLE_PATH,
) -> str:
    memory_path = Path(path)
    if not memory_path.exists():
        example = Path(example_path)
        memory_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    return memory_path.read_text(encoding="utf-8")


def normalize_vendor_key(vendor: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", vendor.lower())


def correction_line_vendor(line: str) -> str | None:
    match = CORRECTION_VENDOR_PATTERN.match(line)
    if not match:
        return None
    return match.group("vendor")


def replace_or_insert_correction(memory: str, line: str, vendor: str) -> str:
    heading = "## Corrections"
    heading_index = memory.find(heading)
    if heading_index == -1:
        return memory.rstrip() + f"\n\n{heading}\n\n{line}\n"

    section_start = memory.find("\n", heading_index)
    if section_start == -1:
        section_start = len(memory)
    else:
        section_start += 1

    next_heading_index = memory.find("\n## ", section_start)
    section_end = len(memory) if next_heading_index == -1 else next_heading_index

    prefix = memory[:section_start]
    section = memory[section_start:section_end]
    suffix = memory[section_end:]
    vendor_key = normalize_vendor_key(vendor)

    output_lines = []
    replaced = False
    for existing_line in section.splitlines():
        if existing_line.strip() == EMPTY_CORRECTIONS_MARKER:
            continue
        existing_vendor = correction_line_vendor(existing_line)
        if existing_vendor and normalize_vendor_key(existing_vendor) == vendor_key:
            if not replaced:
                output_lines.append(line)
                replaced = True
            continue
        output_lines.append(existing_line)

    if not replaced:
        while output_lines and not output_lines[-1].strip():
            output_lines.pop()
        output_lines.append(line)

    new_section = "\n".join(output_lines).strip()
    return f"{prefix}\n{new_section}\n{suffix.lstrip(chr(10))}"


def append_correction_to_memory(
    memory_path: str | os.PathLike[str],
    vendor: str,
    new_category: str,
    reason: str | None,
    today: str | None = None,
) -> str:
    correction_date = today or date.today().isoformat()
    correction_reason = reason or "not specified"
    line = (
        f"- {vendor} -> {new_category} (corrected {correction_date}, reason: {correction_reason})"
    )
    path = Path(memory_path)
    memory = path.read_text(encoding="utf-8")
    if line in memory:
        return f"Memory updated: {vendor} -> {new_category}."
    memory = replace_or_insert_correction(memory, line, vendor)
    path.write_text(memory, encoding="utf-8")
    return f"Memory updated: {vendor} -> {new_category}."
