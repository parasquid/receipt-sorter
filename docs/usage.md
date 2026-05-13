# Usage

## One-Shot Mode

The default mode processes the Drive inbox once and exits:

```bash
uv run python bot.py
```

Equivalent console-script form:

```bash
uv run receipt-sorter
```

This is intended for cron, launchd, systemd timers, or other external schedulers.

One-shot mode:

- Lists PDFs in `Accounting/Inbox/`.
- Processes each PDF once.
- Creates the relevant year/month folder only when needed.
- Moves valid PDFs into the filed folder.
- Moves invalid classifications into `Accounting/Needs Review/`.
- Does not run the Telegram listener.
- Does not send Telegram notifications.

`--once` is accepted as an explicit alias:

```bash
uv run python bot.py --once
```

## Server Mode

Server mode runs continuously:

```bash
uv run python bot.py --serve
```

Equivalent console-script form:

```bash
uv run receipt-sorter --serve
```

Server mode:

- Polls Drive every `POLL_INTERVAL_DRIVE` seconds.
- Runs the Telegram listener if `TELEGRAM_BOT_TOKEN` is configured.
- Sends Drive processing summaries to `TELEGRAM_CHAT_ID` if both Telegram values are configured.
- Accepts Telegram PDF uploads.
- Accepts correction messages.

## Drive Workflow

Drop a PDF into `Accounting/Inbox/`. The bot will:

1. Detect the PDF.
2. Download it from Drive.
3. Upload it to OpenAI Files.
4. Classify it.
5. Create the relevant year/month folder if needed.
6. Rename and move the file.
7. In server mode, send a Telegram notification if configured.

If the destination filename already exists, the bot adds a numeric suffix:

```text
Vendor_Office_20260512.pdf
Vendor_Office_20260512-2.pdf
Vendor_Office_20260512-3.pdf
```

## Corrections

Corrections are available only while server mode is running because Telegram must be listening.

Examples:

```text
eleven labs should be marketing
```

```text
Tony Roma's should be Marketing, not Meals
```

If the correction parses, the bot updates `MEMORY.md` under `## Corrections`.
Existing corrections for the same vendor are replaced instead of accumulated.
