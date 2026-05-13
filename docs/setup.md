# Setup

## Requirements

- Python 3.11 or newer.
- `uv`.
- Google Cloud CLI.
- A Google account with Drive access.
- An OpenAI API key.
- Optional: a Telegram bot token from BotFather.

## Install

```bash
git clone https://github.com/parasquid/receipt-sorter.git
cd receipt-sorter
uv sync
cp .env.example .env
```

Fill in `.env`:

```bash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.5

DEFAULT_CURRENCY=USD

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

DRIVE_ACCOUNTING_FOLDER_ID=
DRIVE_INBOX_FOLDER_ID=

POLL_INTERVAL_DRIVE=5
```

Do not commit `.env` or your local `MEMORY.md`. If `MEMORY.md` does not exist on first run,
the bot copies `MEMORY.md.example` automatically. You can also copy it manually before first run
if you want to edit rules up front:

```bash
cp MEMORY.md.example MEMORY.md
```

## Config Validation

Startup requires:

- `OPENAI_API_KEY`
- `DRIVE_ACCOUNTING_FOLDER_ID`
- `DRIVE_INBOX_FOLDER_ID`

`POLL_INTERVAL_DRIVE` must be an integer of at least `1`.
`DEFAULT_CURRENCY` must be a 3-letter uppercase ISO currency code such as `USD`, `MYR`, or `EUR`.
`OPENAI_MODEL` defaults to `gpt-5.5`.

## Google Drive Folders

Create:

```text
Accounting/
  Inbox/
```

Open each folder in Drive and copy the folder ID from the URL:

```text
https://drive.google.com/drive/folders/<FOLDER_ID>
```

Set:

```bash
DRIVE_ACCOUNTING_FOLDER_ID=<Accounting folder ID>
DRIVE_INBOX_FOLDER_ID=<Inbox folder ID>
```

## Google Cloud Auth

Install the Google Cloud CLI:

```bash
brew install --cask google-cloud-sdk
```

Create or select a Google Cloud project, then enable Drive API:

```bash
gcloud auth login
gcloud projects create receipt-sorter-demo
gcloud config set project receipt-sorter-demo
gcloud services enable drive.googleapis.com
```

The Drive scope usually requires your own OAuth desktop client for Application Default Credentials.

In Google Cloud Console:

1. Go to Google Auth Platform.
2. Configure OAuth consent.
3. Add yourself as a test user.
4. Add the Drive scope:
   ```text
   https://www.googleapis.com/auth/drive
   ```
5. Create an OAuth Client ID with application type `Desktop app`.
6. Download the client JSON.
7. Save it as:
   ```text
   ~/.config/gcloud/receipt-sorter-oauth-client.json
   ```

Create Application Default Credentials:

```bash
gcloud auth application-default login \
  --client-id-file="$HOME/.config/gcloud/receipt-sorter-oauth-client.json" \
  --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive"
```

Verify:

```bash
gcloud config get-value project
ls ~/.config/gcloud/application_default_credentials.json
gcloud services list --enabled --filter="drive.googleapis.com"
```

## Optional Telegram Setup

Telegram is required only for live notifications, Telegram PDF uploads, and correction messages.

1. Message `@BotFather`.
2. Run `/newbot`.
3. Copy the token into `TELEGRAM_BOT_TOKEN`.
4. Run server mode:
   ```bash
   uv run python bot.py --serve
   ```
5. Send `/start` to your bot.
6. Watch the terminal for a log line containing your chat ID.
7. Put that numeric ID into `TELEGRAM_CHAT_ID`.
