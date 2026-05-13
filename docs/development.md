# Development

## Local Checks

The package exposes a console script for local runs:

```bash
uv run receipt-sorter --help
```

Run the same commands as CI:

```bash
uv run ruff check .
uv run ruff format . --check
uv run basedpyright
uv run pytest -q
uv run python -m py_compile bot.py setup_drive.py receipt_sorter/*.py
uv lock --check
```

## Tests

Tests use fakes for Drive, Telegram, and provider behavior. Do not add tests that require real Google Drive, Telegram, or OpenAI credentials.

Current test areas include:

- Config validation.
- Drive helper behavior.
- File processing and routing.
- Needs Review sidecars.
- Telegram handlers.
- OpenAI provider settings and prompt caching.
- Runtime CLI mode selection.

## Linting and Formatting

Ruff handles linting and formatting checks.

```bash
uv run ruff check .
uv run ruff format . --check
```

## Type Checking

Basedpyright runs in basic mode:

```bash
uv run basedpyright
```

## CI

GitHub Actions runs checks on pull requests and pushes to `main` or `master`.

Workflow file:

```text
.github/workflows/ci.yml
```

## Contribution Notes

See `CONTRIBUTING.md` for pull request expectations. Keep provider-specific behavior inside provider modules and avoid committing real accounting documents or secrets.
