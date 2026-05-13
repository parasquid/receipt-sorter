from __future__ import annotations

from datetime import datetime


def log_step(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)
