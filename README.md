# Receipt Sorter

Receipt Sorter is a local-first agent that classifies financial PDFs and files them into a Google Drive accounting folder. It can also accept PDFs through Telegram and learn from plain-English corrections by updating `MEMORY.md`.

The default rules are intentionally generic. Teams can adapt categories, vendor rules, currency guidance, and corrections in `MEMORY.md`.

Full documentation lives in [`docs/`](docs/index.md).

## Features

- Polls a Google Drive `Accounting/Inbox/` folder for PDFs.
- Classifies receipts, invoices, statements, contracts, and payroll documents with OpenAI Agents.
- Files documents by document date into `Accounting/YYYY/MM-Mmm/`.
- Moves invalid model classifications into `Accounting/Needs Review/` for human debugging.
- Renames PDFs as `Supplier_Category_YYYYMMDD.pdf`.
- Sends Telegram notifications after Drive processing.
- Accepts Telegram PDF uploads and files them through the same pipeline.
- Supports `/start` and `/status`.
- Accepts corrections such as `eleven labs should be marketing` and keeps `MEMORY.md` current.

## Requirements

- macOS, Linux, or another local machine that can run Python.
- Python 3.11 or newer.
- `uv`.
- Google Cloud CLI.
- A Google account with Drive access.
- An OpenAI API key.
- Optional: a Telegram bot token from BotFather.

## Install

Clone the repository and install dependencies:

```bash
git clone https://github.com/parasquid/receipt-sorter.git
cd receipt-sorter
uv sync
```

Copy the environment template:

```bash
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
the bot copies `MEMORY.md.example` automatically.

The app validates required configuration on startup. `OPENAI_API_KEY`,
`DRIVE_ACCOUNTING_FOLDER_ID`, and `DRIVE_INBOX_FOLDER_ID` must be set.
`POLL_INTERVAL_DRIVE` must be an integer of at least `1`, and `DEFAULT_CURRENCY`
must be a 3-letter currency code.

## Google Drive Setup

Create these folders in Google Drive:

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

### Google Cloud Auth

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

The Drive scope generally requires your own OAuth desktop client for Application Default Credentials.

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

## Telegram Setup

Telegram is optional. Drive filing works without it.

1. Message `@BotFather`.
2. Run `/newbot`.
3. Copy the bot token into:
   ```bash
   TELEGRAM_BOT_TOKEN=
   ```
4. Start the bot locally:
   ```bash
   uv run python bot.py --serve
   ```
5. Send `/start` to your Telegram bot.
6. Watch the terminal for a log line containing your chat ID:
   ```text
   Telegram received from chat 123456789: ...
   ```
7. Put that numeric ID into:
   ```bash
   TELEGRAM_CHAT_ID=123456789
   ```

`TELEGRAM_CHAT_ID` is used for Drive-origin notifications. Telegram PDF uploads and replies work in the chat where the message was sent.

## Filing Defaults

Set the currency the classifier should use when a document does not show one:

```bash
DEFAULT_CURRENCY=USD
```

Use an ISO currency code such as `USD`, `MYR`, `SGD`, `EUR`, or `GBP`.

Set the OpenAI model used for both document classification and correction parsing:

```bash
OPENAI_MODEL=gpt-5.5
```

The OpenAI provider uses prompt caching for repeated classifier and correction
prompts. The bot sends the full prompt each request, but repeated prompt prefixes
can be cached by OpenAI for lower latency and cost. Runtime logs include input,
cached, output, and total token counts when the SDK returns usage details.

## Run

Create the base year folders:

```bash
uv run python setup_drive.py
```

Start the bot:

```bash
uv run python bot.py
```

You can also use the installed console script:

```bash
uv run receipt-sorter
```

By default, this processes the Drive inbox once and exits. This mode is intended for cron,
launchd, systemd timers, or other external schedulers. It does not run Telegram listeners or
send Telegram notifications.

For long-lived polling, Telegram notifications, Telegram PDF uploads, and correction messages,
run server mode:

```bash
uv run python bot.py --serve
```

or:

```bash
uv run receipt-sorter --serve
```

Drop a PDF into `Accounting/Inbox/`. The bot will:

1. Detect the PDF.
2. Download it from Drive.
3. Upload it to OpenAI Files.
4. Classify it.
5. Create the relevant year/month folder if needed.
6. Rename and move the file. If the destination filename already exists, the bot adds a suffix such as `-2`.
7. Send a Telegram notification if configured and running in `--serve` mode.

If the model returns an invalid classification, such as an unknown category or invalid date,
the bot creates `Accounting/Needs Review/` if needed and moves the original file there.
It also creates a matching JSON sidecar such as `receipt.pdf.review.json` in the same
folder with the original file ID, filename, MIME type, validation stage, timestamp, and
review reason.
Transient API or Drive failures leave the file in `Inbox/` so it can be retried.

The OpenAI provider deletes uploaded OpenAI Files after classification using best-effort cleanup.
Cleanup failures are logged but do not change the filing outcome.

## Corrections

Send a plain-English correction to the Telegram bot:

```text
eleven labs should be marketing
```

or reply to a bot summary:

```text
Tony Roma's should be Marketing, not Meals
```

If the correction parses, the bot writes it under `## Corrections` in `MEMORY.md`.
If a correction already exists for the same vendor, the bot replaces that line so memory stays evergreen instead of becoming an audit log.
Future classifications read `MEMORY.md` and can apply those lessons.

Corrections require `--serve` mode because Telegram must be listening.

## Development

Run tests:

```bash
uv run pytest -q
```

Run the same checks as CI:

```bash
uv run ruff check .
uv run ruff format . --check
uv run basedpyright
uv run pytest -q
uv run python -m py_compile bot.py setup_drive.py receipt_sorter/*.py
uv lock --check
```

GitHub Actions runs these checks on pull requests and pushes to `main` or `master`.
See `CONTRIBUTING.md` for local development guidance and `SECURITY.md` for secret handling.

## Project Structure

```text
.github/               CI workflow and GitHub issue/PR templates
receipt_sorter/  Application package
docs/                  Setup, usage, architecture, operations, and security docs
bot.py                  Stable local entrypoint
setup_drive.py          Creates current and previous year folders in Drive
MEMORY.md.example       Template for local classifier rules and learned corrections
tests/                  Unit tests for routing, summaries, Drive helpers, and memory
.env.example            Local environment template
CONTRIBUTING.md         Local development and pull request guidance
SECURITY.md             Vulnerability reporting and secret handling guidance
```

## License

This project is licensed under the GNU Affero General Public License v3.0. See `LICENSE`.
