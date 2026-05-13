# Security

Receipt Sorter is intended to run locally against a user's own Google Drive and Telegram bot. It can access financial documents, so treat configuration and logs carefully.

## Supported Versions

Security fixes are expected on the default branch until formal releases are established.

## Reporting a Vulnerability

When the GitHub repository is created, use the repository's private vulnerability reporting or security advisory flow if available. If private reporting is not configured, open a minimal public issue that describes the affected area without sharing secrets, tokens, document contents, or exploit details.

## Secret Handling

Never commit:

- `.env`
- `MEMORY.md`
- OpenAI API keys
- Telegram bot tokens
- Google OAuth client secrets
- Google Application Default Credentials
- Real accounting PDFs or screenshots
- Personal Drive folder IDs or Telegram chat IDs unless you intentionally made them public

If a secret is exposed, revoke or rotate it immediately:

- OpenAI keys: rotate in the OpenAI dashboard.
- Telegram bot tokens: regenerate with BotFather.
- Google credentials: delete exposed OAuth clients or revoke tokens from the Google account security settings.

## Runtime Scope

The bot should only operate inside the configured Drive folder IDs. Changes that broaden file access, add new input channels, or persist document metadata should include tests and documentation explaining the security and privacy implications.
