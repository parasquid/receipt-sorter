# Providers

## Current Provider

The current provider is OpenAI. It uses:

- OpenAI Files API for PDF uploads.
- OpenAI Agents SDK for classifier and correction parser agents.
- Structured output models for `DocumentResult` and `Correction`.
- Prompt caching for repeated classifier and correction prompt prefixes.
- Best-effort deletion of uploaded OpenAI Files after classification.

## OpenAI Model

Configure:

```bash
OPENAI_MODEL=gpt-5.5
```

The configured model is used for both classification and correction parsing.

## Prompt Caching

The OpenAI provider sends the full prompt on every request, including the system instructions, category list, memory, and current file reference. OpenAI prompt caching can cache repeated prompt prefixes.

The provider sets a stable `prompt_cache_key` for classifier and correction flows. For supported OpenAI model families, it requests `prompt_cache_retention="24h"`.

Logs include token usage when the SDK returns it:

```text
DocClassifier token usage: input=..., cached=..., output=..., total=...
```

## Uploaded File Cleanup

The OpenAI provider deletes uploaded Files API documents after classification in a `finally` block.
Deletion failures are logged as non-fatal because Drive file movement should not be reversed just because provider cleanup failed.

## Provider-Agnostic Shape

Core runtime should continue depending on these high-level capabilities:

- Classify one document.
- Parse one correction.

Provider-specific features should stay inside provider implementations:

- OpenAI prompt caching.
- OpenAI Files API.
- OpenAI Batch API, if added later.
- Gemini file upload or caching behavior, if added later.

## Batch Processing

OpenAI Batch API is not part of the live bot path. It is a candidate for future bulk backfill workflows where 24-hour async completion is acceptable.
