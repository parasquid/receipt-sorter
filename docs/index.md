# Documentation

Receipt Sorter is a local-first accounting document filing bot. It watches a Google Drive inbox, classifies PDF receipts and invoices, files them into dated folders, and can use Telegram for live operation and corrections.

## Start Here

- [Setup](setup.md): install dependencies, configure `.env`, Google Drive, OpenAI, and Telegram.
- [Usage](usage.md): run one-shot cron mode or long-lived server mode.
- [Operations](operations.md): cron, launchd, systemd, logging, retries, and failure behavior.

## Concepts

- [Architecture](architecture.md): package boundaries and runtime flow.
- [Classification](classification.md): categories, memory, validation, filing, and Needs Review.
- [Providers](providers.md): OpenAI provider behavior, prompt caching, and future provider shape.
- [Google Drive](google-drive.md): folder model, OAuth, ADC, Drive scopes, and file movement.
- [Telegram](telegram.md): bot setup, notifications, PDF uploads, and corrections.

## Project Work

- [Development](development.md): tests, linting, typing, CI, and contributor workflow.
- [Security](security.md): secrets, scopes, local data handling, and vulnerability reporting.
- [Roadmap](roadmap.md): likely future GitHub issues.
