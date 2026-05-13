# Security

## Local-First Assumption

Receipt Sorter is designed to run on a user's local machine against that user's own Google Drive and Telegram bot.

It is not currently designed as a hosted multi-tenant service.

## Secrets

Do not commit:

- `.env`
- OpenAI API keys
- Telegram bot tokens
- Google OAuth client secrets
- Google Application Default Credentials
- Real accounting PDFs or screenshots
- Personal Drive folder IDs or Telegram chat IDs unless intentionally public

## Google Scope

The local setup uses the broad Drive scope:

```text
https://www.googleapis.com/auth/drive
```

This is pragmatic for a local tool that needs to read, rename, move, and create files in user-created folders. A hosted product should revisit scope, OAuth verification, tenant isolation, and data retention.

## Data Handling

PDF contents are sent to the configured model provider for classification. With the OpenAI provider, PDFs are uploaded through the OpenAI Files API for use in model requests.
After classification, the OpenAI provider attempts to delete each uploaded OpenAI File. Cleanup failures are logged but treated as non-fatal.

`MEMORY.md` may contain organization-specific vendor rules. Treat it as sensitive if it reveals business relationships.
The repository ships `MEMORY.md.example`; the live `MEMORY.md` file is ignored.

## Prompt Caching

OpenAI prompt caching may retain derived key/value tensors for a limited time depending on model and retention settings. The provider uses prompt caching as an OpenAI-specific optimization.

## Vulnerability Reporting

See `SECURITY.md` at the repository root for reporting guidance and secret rotation notes.
