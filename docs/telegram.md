# Telegram

Telegram is optional. Drive one-shot mode works without it.

## Capabilities

In server mode, Telegram can:

- Reply to `/start`.
- Reply to `/status`.
- Accept PDF uploads and file them through the same Drive pipeline.
- Receive plain-English correction messages.
- Send Drive processing summaries to `TELEGRAM_CHAT_ID`.

One-shot mode does not run the Telegram listener and does not send Telegram notifications.

If Telegram cannot start in server mode, the bot retries three times with 5s
and 30s backoff delays. After the third failed attempt, Drive polling continues
in Drive-only degraded mode and Telegram notifications are suppressed until the
process is restarted.

## Setup

1. Message `@BotFather`.
2. Run `/newbot`.
3. Copy the token into:
   ```bash
   TELEGRAM_BOT_TOKEN=
   ```
4. Start server mode:
   ```bash
   uv run python bot.py --serve
   ```
5. Send `/start` to the bot.
6. Copy the chat ID from the terminal logs.
7. Set:
   ```bash
   TELEGRAM_CHAT_ID=
   ```

`TELEGRAM_CHAT_ID` controls Drive-origin notifications. PDF uploads and replies use the chat where the message was sent.

## Corrections

Correction examples:

```text
eleven labs should be marketing
```

```text
Grab should be Transport & Travel
```

Corrections are parsed by the configured provider and written into `MEMORY.md`.
If a correction for the same vendor already exists, it is replaced.

## Troubleshooting

If `/start` works but corrections do not:

- Confirm the bot is running with `--serve`.
- Check terminal logs for received Telegram messages.
- Confirm the message is not only being sent while one-shot mode is running.
- Confirm the category can map to one of the allowed categories.
