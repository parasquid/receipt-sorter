# Operations

## Recommended Production Shape

Use one-shot mode under an external scheduler:

```bash
uv run python bot.py
```

This keeps the bot simple: each run processes the current inbox and exits. Scheduler logs and exit codes become the operational source of truth.

Use server mode for interactive local use:

```bash
uv run python bot.py --serve
```

Server mode is required for Telegram corrections and Telegram PDF uploads.

## Cron Example

Run every 5 minutes:

```cron
*/5 * * * * cd /path/to/receipt-sorter && uv run python bot.py >> logs/cron.log 2>&1
```

One-shot mode intentionally does not send Telegram notifications. If you want notifications, run `--serve`.

## launchd Example

Create a plist that runs:

```bash
cd /path/to/receipt-sorter && uv run python bot.py
```

Set the interval through `StartInterval`.

## systemd Timer Shape

Use a service that runs:

```bash
WorkingDirectory=/path/to/receipt-sorter
ExecStart=/usr/bin/env uv run python bot.py
```

Use a timer unit for the interval.

## Logging

The bot logs timestamped lines to stdout. Logs include:

- Drive inbox checks.
- File processing start/failure.
- OpenAI upload and classifier status.
- Token usage when provider usage is available.
- Telegram messages in server mode.
- Needs Review sidecar failures.

## Retry Behavior

Transient provider or Drive failures leave PDFs in `Inbox/` for retry by the next run.

Invalid classifications move PDFs to `Needs Review/` because retrying the same invalid structured output is usually less useful than human inspection.

## Exit Behavior

One-shot mode exits after one inbox pass. Unhandled top-level errors should cause a non-zero process exit so the scheduler can report failure.

Server mode catches Drive polling errors, waits 60 seconds, and continues polling.
