# Roadmap

These are likely GitHub issue candidates after the repository exists.

## Runtime

- Add first-class launchd and systemd examples with tested paths.
- Add structured JSON logs as an optional mode.
- Add a dry-run mode that classifies without moving files.
- Add a command to reprocess `Needs Review/` files explicitly.

## Providers

- Add a provider interface for optional batch classification.
- Add OpenAI Batch API support for bulk backfills.
- Research Gemini provider support for PDFs, structured outputs, and caching.
- Add provider-specific capability checks at startup.

## Ingestion

- Add image-to-PDF preprocessing.
- Add email-to-PDF preprocessing.
- Keep the core processor PDF-only unless a strong reason emerges.

## Classification

- Add configurable categories.
- Add confidence thresholds in env or config file.
- Add optional CSV export of processed summaries.

## User Experience

- Add clearer Telegram messages for Needs Review outcomes.
- Add `/status` details for last run and processed counts.
- Add `/help`.
- Add setup diagnostics command.

## Packaging

- Add a real repository URL in README once published.
- Add release tags and changelog.
- Add Dockerfile only if local Python setup becomes a recurring blocker.
