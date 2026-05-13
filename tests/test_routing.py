import pytest
from pydantic import ValidationError

from receipt_sorter.config import parse_config
from receipt_sorter.corrections import (
    Correction,
    build_correction_input,
    correction_original_summary,
    format_correction_confirmation,
    should_handle_correction_message,
)
from receipt_sorter.formatting import (
    build_destination_path,
    build_safe_filename,
    format_batch_summary,
)
from receipt_sorter.log import log_step
from receipt_sorter.memory import append_correction_to_memory, read_memory
from receipt_sorter.models import (
    DocumentResult,
    NeedsReviewDocument,
    ProcessedDocument,
)
from receipt_sorter.openai_provider import (
    build_classifier_input,
    build_classifier_instructions,
)
from receipt_sorter.telegram_bot import describe_telegram_message, is_pdf_document


def test_build_safe_filename_uses_category_slug_and_compact_date():
    result = DocumentResult(
        supplier="Grab Holdings Sdn Bhd",
        category="Transport & Travel",
        date="2026-03-15",
        amount=45.5,
        currency="MYR",
        confidence=0.92,
    )

    assert build_safe_filename(result) == "GrabHoldings_Transport_20260315.pdf"


def test_build_destination_path_uses_document_year_and_month():
    result = DocumentResult(
        supplier="TNB",
        category="Utilities",
        date="2026-05-01",
        amount=320.1,
        currency="MYR",
        confidence=0.88,
    )

    assert build_destination_path(result) == ("2026", "05-May")


def test_invalid_document_date_is_rejected():
    result = DocumentResult(
        supplier="AWS",
        category="Software & Subscriptions",
        date="15/03/2026",
        amount=1240.0,
        currency="USD",
        confidence=0.9,
    )

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        build_destination_path(result)


def test_document_result_rejects_unknown_category():
    with pytest.raises(ValidationError):
        DocumentResult.model_validate(
            {
                "supplier": "Vendor",
                "category": "Marketing",
                "date": "2026-05-01",
                "amount": 99.0,
                "currency": "USD",
                "confidence": 0.9,
            }
        )


def test_correction_rejects_unknown_category():
    with pytest.raises(ValidationError):
        Correction.model_validate(
            {
                "vendor": "Vendor",
                "new_category": "Marketing",
                "reason": None,
            }
        )


def test_parse_config_loads_explicit_env_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "DRIVE_ACCOUNTING_FOLDER_ID=accounting-id",
                "DRIVE_INBOX_FOLDER_ID=inbox-id",
                "OPENAI_API_KEY=test-key",
                "POLL_INTERVAL_DRIVE=9",
                "OPENAI_MODEL=gpt-test",
                "TELEGRAM_BOT_TOKEN=token",
                "TELEGRAM_CHAT_ID=12345",
                "DEFAULT_CURRENCY=SGD",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("DRIVE_ACCOUNTING_FOLDER_ID", raising=False)
    monkeypatch.delenv("DRIVE_INBOX_FOLDER_ID", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("POLL_INTERVAL_DRIVE", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("DEFAULT_CURRENCY", raising=False)

    config = parse_config(env_path)

    assert config.accounting_folder_id == "accounting-id"
    assert config.inbox_folder_id == "inbox-id"
    assert config.poll_interval_drive == 9
    assert config.openai_model == "gpt-test"
    assert config.telegram_bot_token == "token"
    assert config.telegram_chat_id == "12345"
    assert config.default_currency == "SGD"


def test_parse_config_defaults_openai_model(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "DRIVE_ACCOUNTING_FOLDER_ID=accounting-id",
                "DRIVE_INBOX_FOLDER_ID=inbox-id",
                "OPENAI_API_KEY=test-key",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("DRIVE_ACCOUNTING_FOLDER_ID", raising=False)
    monkeypatch.delenv("DRIVE_INBOX_FOLDER_ID", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    config = parse_config(env_path)

    assert config.openai_model == "gpt-5.5"


@pytest.mark.parametrize(
    ("env_lines", "match"),
    [
        (
            [
                "DRIVE_ACCOUNTING_FOLDER_ID=accounting-id",
                "DRIVE_INBOX_FOLDER_ID=inbox-id",
            ],
            "OPENAI_API_KEY",
        ),
        (
            [
                "DRIVE_ACCOUNTING_FOLDER_ID=accounting-id",
                "DRIVE_INBOX_FOLDER_ID=inbox-id",
                "OPENAI_API_KEY=test-key",
                "POLL_INTERVAL_DRIVE=0",
            ],
            "POLL_INTERVAL_DRIVE",
        ),
        (
            [
                "DRIVE_ACCOUNTING_FOLDER_ID=accounting-id",
                "DRIVE_INBOX_FOLDER_ID=inbox-id",
                "OPENAI_API_KEY=test-key",
                "DEFAULT_CURRENCY=US",
            ],
            "DEFAULT_CURRENCY",
        ),
    ],
)
def test_parse_config_rejects_invalid_required_values(
    tmp_path,
    monkeypatch,
    env_lines,
    match,
):
    env_path = tmp_path / ".env"
    env_path.write_text("\n".join(env_lines), encoding="utf-8")
    for key in [
        "DRIVE_ACCOUNTING_FOLDER_ID",
        "DRIVE_INBOX_FOLDER_ID",
        "OPENAI_API_KEY",
        "POLL_INTERVAL_DRIVE",
        "DEFAULT_CURRENCY",
    ]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError, match=match):
        parse_config(env_path)


def test_build_classifier_input_uses_uploaded_file_id_not_inline_file_data():
    payload = build_classifier_input("memory text", "file-abc123")
    content = payload[0]["content"]

    assert content[0]["type"] == "input_text"
    assert "# MEMORY.md\n\nmemory text" in content[0]["text"]
    assert content[1] == {"type": "input_file", "file_id": "file-abc123"}


def test_build_classifier_instructions_includes_default_currency():
    instructions = build_classifier_instructions("EUR")

    assert '"EUR"' in instructions
    assert "otherwise default" in instructions


def test_read_memory_bootstraps_missing_memory_from_example(tmp_path):
    memory_path = tmp_path / "MEMORY.md"
    example_path = tmp_path / "MEMORY.md.example"
    example_path.write_text("# Rules and Corrections\n\n## Corrections\n\n", encoding="utf-8")

    memory = read_memory(memory_path, example_path=example_path)

    assert memory == "# Rules and Corrections\n\n## Corrections\n\n"
    assert memory_path.read_text(encoding="utf-8") == memory


def test_log_step_prints_timestamped_message(capsys):
    log_step("Checking Drive Inbox for PDFs...")

    output = capsys.readouterr().out.strip()
    assert output.endswith("Checking Drive Inbox for PDFs...")
    assert output[0] == "["
    assert output[3] == ":"
    assert output[6] == ":"
    assert output[9] == "]"


def test_format_batch_summary_lists_processed_documents():
    result = DocumentResult(
        supplier="Grab",
        category="Transport & Travel",
        date="2026-05-12",
        amount=45.5,
        currency="MYR",
        confidence=0.91,
    )
    processed = ProcessedDocument(
        original_name="receipt.pdf",
        destination_year="2026",
        destination_month="05-May",
        new_name="Grab_Transport_20260512.pdf",
        result=result,
    )

    summary = format_batch_summary([processed])

    assert "PROCESSED 1 DOCUMENT" in summary
    assert "Filed to: 2026/05-May/" in summary
    assert "Grab" in summary
    assert "Transport" in summary
    assert "MYR 45.50" in summary


def test_format_batch_summary_lists_needs_review_documents():
    summary = format_batch_summary(
        [
            NeedsReviewDocument(
                original_name="receipt.pdf",
                review_folder_name="Needs Review",
                reason="Document date must be YYYY-MM-DD: 05/12/2026",
            )
        ]
    )

    assert "NEEDS REVIEW 1 DOCUMENT" in summary
    assert "Filed to: Needs Review/" in summary
    assert "receipt.pdf" in summary
    assert "YYYY-MM-DD" in summary


def test_append_correction_to_memory_adds_line_under_corrections(tmp_path):
    memory_path = tmp_path / "MEMORY.md"
    memory_path.write_text(
        "# Rules and Corrections\n\n## Rules\n\n- Rule\n\n## Corrections\n\n"
        "(Empty initially.)\n\n## Currency\n\n- Default MYR\n",
        encoding="utf-8",
    )

    message = append_correction_to_memory(
        memory_path,
        vendor="Tony Roma's",
        new_category="Marketing & Advertising",
        reason="client meeting",
        today="2026-05-12",
    )

    memory = memory_path.read_text(encoding="utf-8")
    assert message == "Memory updated: Tony Roma's -> Marketing & Advertising."
    expected = (
        "- Tony Roma's -> Marketing & Advertising (corrected 2026-05-12, reason: client meeting)"
    )
    assert expected in memory
    assert memory.index("## Corrections") < memory.index("Tony Roma's")
    assert memory.index("Tony Roma's") < memory.index("## Currency")


def test_append_correction_to_memory_is_idempotent(tmp_path):
    memory_path = tmp_path / "MEMORY.md"
    memory_path.write_text(
        "# Rules and Corrections\n\n## Corrections\n\n## Currency\n",
        encoding="utf-8",
    )

    append_correction_to_memory(
        memory_path,
        vendor="Tony Roma's",
        new_category="Marketing & Advertising",
        reason=None,
        today="2026-05-12",
    )
    append_correction_to_memory(
        memory_path,
        vendor="Tony Roma's",
        new_category="Marketing & Advertising",
        reason=None,
        today="2026-05-12",
    )

    memory = memory_path.read_text(encoding="utf-8")
    assert memory.count("Tony Roma's -> Marketing & Advertising") == 1


def test_append_correction_to_memory_replaces_existing_vendor_line(tmp_path):
    memory_path = tmp_path / "MEMORY.md"
    memory_path.write_text(
        "# Rules and Corrections\n\n"
        "## Corrections\n\n"
        "- ElevenLabs -> Software & Subscriptions (corrected 2026-05-11, reason: old)\n\n"
        "## Currency\n\n"
        "- Default USD\n",
        encoding="utf-8",
    )

    append_correction_to_memory(
        memory_path,
        vendor="Eleven Labs",
        new_category="Marketing & Advertising",
        reason="ads",
        today="2026-05-12",
    )

    memory = memory_path.read_text(encoding="utf-8")
    assert "ElevenLabs -> Software & Subscriptions" not in memory
    assert "- Eleven Labs -> Marketing & Advertising (corrected 2026-05-12, reason: ads)" in memory
    assert memory.count("Eleven") == 1


def test_should_handle_correction_message_accepts_standalone_non_command_text():
    class Message:
        text = "Tony Roma's should be Marketing"
        reply_to_message = object()

    assert should_handle_correction_message(Message()) is True

    class Standalone:
        text = "Tony Roma's should be Marketing"
        reply_to_message = None

    assert should_handle_correction_message(Standalone()) is True

    class Command:
        text = "/status"
        reply_to_message = None

    assert should_handle_correction_message(Command()) is False


def test_correction_original_summary_uses_reply_or_standalone_fallback():
    class Reply:
        text = "Processed 1 document"
        caption = None

    class RepliedMessage:
        reply_to_message = Reply()

    assert correction_original_summary(RepliedMessage()) == "Processed 1 document"

    class Standalone:
        reply_to_message = None

    assert (
        correction_original_summary(Standalone())
        == "(No original summary; user sent a standalone correction.)"
    )


def test_is_pdf_document_accepts_pdf_mime_or_filename():
    class PdfMime:
        mime_type = "application/pdf"
        file_name = "receipt.bin"

    class PdfName:
        mime_type = "application/octet-stream"
        file_name = "receipt.PDF"

    class NotPdf:
        mime_type = "application/octet-stream"
        file_name = "receipt.txt"

    assert is_pdf_document(PdfMime()) is True
    assert is_pdf_document(PdfName()) is True
    assert is_pdf_document(NotPdf()) is False
    assert is_pdf_document(None) is False


def test_describe_telegram_message_includes_text_document_and_reply():
    class Document:
        file_name = "receipt.pdf"
        mime_type = "application/octet-stream"

    class Reply:
        message_id = 42

    class Message:
        message_id = 99
        text = "Tony Roma's should be Marketing"
        document = Document()
        reply_to_message = Reply()

    description = describe_telegram_message(Message())

    assert "message_id=99" in description
    assert 'text="Tony Roma\'s should be Marketing"' in description
    assert "document='receipt.pdf'" in description
    assert "mime='application/octet-stream'" in description
    assert "reply_to=42" in description


def test_format_correction_confirmation_handles_valid_and_empty_corrections():
    correction = Correction(
        vendor="Tony Roma's",
        new_category="Marketing & Advertising",
        reason="client meeting",
    )

    assert (
        format_correction_confirmation(correction)
        == "Got it. Tony Roma's -> Marketing & Advertising. Updated memory."
    )
    assert (
        format_correction_confirmation(Correction(vendor=None, new_category=None, reason=None))
        is None
    )


def test_build_correction_input_includes_original_summary_and_reply():
    payload = build_correction_input("Processed 1 document", "Tony Roma's should be Marketing")

    assert "# Original classification summary" in payload
    assert "Processed 1 document" in payload
    assert "# User reply" in payload
    assert "Tony Roma's should be Marketing" in payload
