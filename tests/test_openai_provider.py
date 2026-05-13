import asyncio
import sys
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from receipt_sorter.ai import DocumentInput
from receipt_sorter.models import Correction, DocumentResult
from receipt_sorter.openai_provider import (
    OpenAICorrectionParser,
    OpenAIDocumentClassifier,
    build_prompt_cache_key,
    log_openai_usage,
)
from receipt_sorter.validation import InvalidClassificationError


def test_openai_classifier_uses_configured_model(monkeypatch):
    seen = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            seen["agent_kwargs"] = kwargs

    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeRunContextWrapper:
        def __init__(self, context):
            self.context = context
            self.usage = None

    class FakeRunner:
        @staticmethod
        async def run(agent, input, **kwargs):
            seen["run_kwargs"] = kwargs
            return SimpleNamespace(
                final_output=DocumentResult(
                    supplier="Vendor",
                    category="Office Supplies",
                    date="2026-05-12",
                    amount=42.0,
                    currency="USD",
                    confidence=0.9,
                )
            )

    monkeypatch.setitem(
        sys.modules,
        "agents",
        SimpleNamespace(
            Agent=FakeAgent,
            ModelSettings=FakeModelSettings,
            RunContextWrapper=FakeRunContextWrapper,
            Runner=FakeRunner,
        ),
    )

    async def fake_upload_document_for_model(document):
        return "file-id"

    monkeypatch.setattr(
        "receipt_sorter.openai_provider.upload_document_for_model",
        fake_upload_document_for_model,
    )

    classifier = OpenAIDocumentClassifier(model="gpt-custom")
    result = asyncio.run(
        classifier.classify(
            DocumentInput("receipt.pdf", b"%PDF", "application/pdf"),
            "memory",
            "USD",
        )
    )

    assert result.supplier == "Vendor"
    assert seen["agent_kwargs"]["model"] == "gpt-custom"


def test_openai_classifier_deletes_uploaded_file_after_success(monkeypatch):
    deleted_file_ids = []

    class FakeAgent:
        def __init__(self, **kwargs):
            pass

    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeRunContextWrapper:
        def __init__(self, context):
            self.context = context
            self.usage = None

    class FakeRunner:
        @staticmethod
        async def run(agent, input, **kwargs):
            return SimpleNamespace(
                final_output=DocumentResult(
                    supplier="Vendor",
                    category="Office Supplies",
                    date="2026-05-12",
                    amount=42.0,
                    currency="USD",
                    confidence=0.9,
                )
            )

    monkeypatch.setitem(
        sys.modules,
        "agents",
        SimpleNamespace(
            Agent=FakeAgent,
            ModelSettings=FakeModelSettings,
            RunContextWrapper=FakeRunContextWrapper,
            Runner=FakeRunner,
        ),
    )

    async def fake_upload_document_for_model(document):
        return "file-id"

    async def fake_delete_uploaded_document(file_id):
        deleted_file_ids.append(file_id)

    monkeypatch.setattr(
        "receipt_sorter.openai_provider.upload_document_for_model",
        fake_upload_document_for_model,
    )
    monkeypatch.setattr(
        "receipt_sorter.openai_provider.delete_uploaded_document",
        fake_delete_uploaded_document,
        raising=False,
    )

    asyncio.run(
        OpenAIDocumentClassifier(model="gpt-custom").classify(
            DocumentInput("receipt.pdf", b"%PDF", "application/pdf"),
            "memory",
            "USD",
        )
    )

    assert deleted_file_ids == ["file-id"]


def test_openai_classifier_deletes_uploaded_file_after_validation_error(monkeypatch):
    deleted_file_ids = []

    class FakeAgent:
        def __init__(self, **kwargs):
            pass

    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeRunContextWrapper:
        def __init__(self, context):
            self.context = context
            self.usage = None

    class FakeRunner:
        @staticmethod
        async def run(agent, input, **kwargs):
            try:
                DocumentResult.model_validate(
                    {
                        "supplier": "Vendor",
                        "category": "Not Real",
                        "date": "2026-05-12",
                        "amount": 42.0,
                        "currency": "USD",
                        "confidence": 0.9,
                    }
                )
            except ValidationError as exc:
                raise exc

    monkeypatch.setitem(
        sys.modules,
        "agents",
        SimpleNamespace(
            Agent=FakeAgent,
            ModelSettings=FakeModelSettings,
            RunContextWrapper=FakeRunContextWrapper,
            Runner=FakeRunner,
        ),
    )

    async def fake_upload_document_for_model(document):
        return "file-id"

    async def fake_delete_uploaded_document(file_id):
        deleted_file_ids.append(file_id)

    monkeypatch.setattr(
        "receipt_sorter.openai_provider.upload_document_for_model",
        fake_upload_document_for_model,
    )
    monkeypatch.setattr(
        "receipt_sorter.openai_provider.delete_uploaded_document",
        fake_delete_uploaded_document,
        raising=False,
    )

    with pytest.raises(InvalidClassificationError):
        asyncio.run(
            OpenAIDocumentClassifier(model="gpt-custom").classify(
                DocumentInput("receipt.pdf", b"%PDF", "application/pdf"),
                "memory",
                "USD",
            )
        )

    assert deleted_file_ids == ["file-id"]


def test_openai_classifier_configures_prompt_cache_settings(monkeypatch):
    seen = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            seen["agent_kwargs"] = kwargs

    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeRunContextWrapper:
        def __init__(self, context):
            self.context = context
            self.usage = None

    class FakeRunner:
        @staticmethod
        async def run(agent, input, **kwargs):
            return SimpleNamespace(
                final_output=DocumentResult(
                    supplier="Vendor",
                    category="Office Supplies",
                    date="2026-05-12",
                    amount=42.0,
                    currency="USD",
                    confidence=0.9,
                )
            )

    monkeypatch.setitem(
        sys.modules,
        "agents",
        SimpleNamespace(
            Agent=FakeAgent,
            ModelSettings=FakeModelSettings,
            RunContextWrapper=FakeRunContextWrapper,
            Runner=FakeRunner,
        ),
    )

    async def fake_upload_document_for_model(document):
        return "file-id"

    monkeypatch.setattr(
        "receipt_sorter.openai_provider.upload_document_for_model",
        fake_upload_document_for_model,
    )

    asyncio.run(
        OpenAIDocumentClassifier(model="gpt-5.5").classify(
            DocumentInput("receipt.pdf", b"%PDF", "application/pdf"),
            "memory",
            "USD",
        )
    )

    settings = seen["agent_kwargs"]["model_settings"].kwargs
    assert settings["prompt_cache_retention"] == "24h"
    assert settings["extra_args"]["prompt_cache_key"].startswith("receipt-sorter:classifier:")
    assert len(settings["extra_args"]["prompt_cache_key"]) <= 64


def test_openai_correction_parser_configures_prompt_cache_settings(monkeypatch):
    seen = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            seen["agent_kwargs"] = kwargs

    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeRunContextWrapper:
        def __init__(self, context):
            self.context = context
            self.usage = None

    class FakeRunner:
        @staticmethod
        async def run(agent, input, **kwargs):
            return SimpleNamespace(
                final_output=Correction(
                    vendor="Vendor",
                    new_category="Office Supplies",
                    reason=None,
                )
            )

    monkeypatch.setitem(
        sys.modules,
        "agents",
        SimpleNamespace(
            Agent=FakeAgent,
            ModelSettings=FakeModelSettings,
            RunContextWrapper=FakeRunContextWrapper,
            Runner=FakeRunner,
        ),
    )

    correction = asyncio.run(OpenAICorrectionParser(model="gpt-5.5").parse("summary", "reply"))

    settings = seen["agent_kwargs"]["model_settings"].kwargs
    assert correction.vendor == "Vendor"
    assert settings["prompt_cache_retention"] == "24h"
    assert settings["extra_args"]["prompt_cache_key"].startswith("receipt-sorter:correction:")
    assert len(settings["extra_args"]["prompt_cache_key"]) <= 64


def test_prompt_cache_key_stays_within_openai_limit_and_changes_by_model():
    short_model_key = build_prompt_cache_key("classifier", "gpt-5.5", "static prompt")
    long_model_key = build_prompt_cache_key(
        "classifier",
        "provider/model-name-that-is-longer-than-the-openai-cache-key-limit",
        "static prompt",
    )

    assert len(short_model_key) <= 64
    assert len(long_model_key) <= 64
    assert short_model_key != long_model_key


def test_log_openai_usage_includes_cached_tokens(capsys):
    usage = SimpleNamespace(
        input_tokens=2000,
        output_tokens=100,
        total_tokens=2100,
        input_tokens_details=SimpleNamespace(cached_tokens=1500),
    )

    log_openai_usage("DocClassifier", usage)

    output = capsys.readouterr().out
    assert "DocClassifier token usage" in output
    assert "input=2000" in output
    assert "cached=1500" in output


def test_openai_correction_parser_invalid_output_returns_empty_correction(monkeypatch):
    class FakeAgent:
        def __init__(self, **kwargs):
            pass

    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeRunContextWrapper:
        def __init__(self, context):
            self.context = context
            self.usage = None

    class FakeRunner:
        @staticmethod
        async def run(agent, input, **kwargs):
            try:
                Correction.model_validate({"vendor": "Vendor", "new_category": "Not Real"})
            except ValidationError as exc:
                raise exc

    monkeypatch.setitem(
        sys.modules,
        "agents",
        SimpleNamespace(
            Agent=FakeAgent,
            ModelSettings=FakeModelSettings,
            RunContextWrapper=FakeRunContextWrapper,
            Runner=FakeRunner,
        ),
    )

    correction = asyncio.run(
        OpenAICorrectionParser(model="gpt-custom").parse(
            "summary",
            "vendor should be nonsense",
        )
    )

    assert correction == Correction(vendor=None, new_category=None, reason=None)
