## Summary

- 

## Test Plan

- [ ] `uv run ruff check .`
- [ ] `uv run ruff format . --check`
- [ ] `uv run basedpyright`
- [ ] `uv run pytest -q`
- [ ] `uv run python -m py_compile bot.py setup_drive.py receipt_sorter/*.py`
- [ ] `uv lock --check`

## Checklist

- [ ] I kept secrets out of committed files.
- [ ] I updated docs or `.env.example` for config changes.
- [ ] I added or updated tests for behavior changes.
