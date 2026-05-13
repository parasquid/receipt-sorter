# Classification

## Inputs

Runtime input is PDF-only. A future ingestion layer can convert email messages or images to PDFs before handing them to the same pipeline, but the core processor expects PDFs.

## Categories

Allowed categories live in `receipt_sorter.models`. The model must return exactly one allowed category. Unknown category names are treated as invalid classification output.

## Memory

`MEMORY.md` is the human-editable knowledge base for classification behavior.
It is local-only and ignored by git. If it does not exist on first run, the bot copies
`MEMORY.md.example` automatically. New users can also create it manually before first run:

```bash
cp MEMORY.md.example MEMORY.md
```

It can contain:

- Rules: stable organization-specific guidance.
- Corrections: lessons from Telegram correction messages.

During classification, the provider receives `MEMORY.md` in context. During correction handling, the bot updates `MEMORY.md`; classification never writes memory.

Corrections are evergreen. A new correction for the same vendor replaces the old correction line instead of creating an audit trail.

## Currency

The classifier should use the document currency when visible. `DEFAULT_CURRENCY` is only a fallback for documents that do not show a currency.

## Validation

Structured model output is validated before file movement. Invalid output moves to Needs Review instead of being filed.

Examples of invalid output:

- Unknown category.
- Invalid date.
- Missing required supplier.
- Unreadable or non-financial document returned in a way that fails validation.

## Needs Review

Invalid classifications are moved to:

```text
Accounting/Needs Review/
```

The bot writes a JSON sidecar next to the PDF:

```text
original.pdf.review.json
```

Sidecar fields include:

- `original_name`
- `original_file_id`
- `review_folder`
- `reason`
- `stage`
- `created_at`
- `mime_type`

If sidecar creation fails after the PDF move, the bot logs the sidecar failure and leaves the PDF in Needs Review.
