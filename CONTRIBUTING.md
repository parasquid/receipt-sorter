# Contributing

Thanks for helping improve Receipt Sorter. This project is local-first and handles financial documents, so small, well-tested changes are preferred.

## Local Setup

Install dependencies:

```bash
uv sync
```

Create local config:

```bash
cp .env.example .env
cp MEMORY.md.example MEMORY.md
```

Do not commit `.env`, local `MEMORY.md`, Google ADC files, Telegram tokens, OpenAI keys, sample receipts, invoices, or generated PDFs containing personal data.

## Development Workflow

Run the bot locally:

```bash
uv run python bot.py
```

Run the Drive setup helper:

```bash
uv run python setup_drive.py
```

Run the full local check suite before opening a pull request:

```bash
uv run ruff check .
uv run ruff format . --check
uv run basedpyright
uv run pytest -q
uv run python -m py_compile bot.py setup_drive.py receipt_sorter/*.py
uv lock --check
```

## Pull Requests

- Keep changes focused on one behavior or refactor.
- Add or update tests for runtime behavior changes.
- Update `README.md` and `.env.example` when configuration changes.
- Keep provider-specific code behind the provider interfaces where possible.
- Avoid adding persistent storage unless the issue or pull request explains the migration path and privacy implications.

## Privacy

Tests should use fakes or sanitized fixtures. Do not include real accounting documents, Drive folder IDs, chat IDs, API keys, access tokens, or refresh tokens in commits.
