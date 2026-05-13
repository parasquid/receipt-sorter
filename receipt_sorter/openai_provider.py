from __future__ import annotations

from hashlib import sha256
from typing import Any, cast

from openai import AsyncOpenAI
from pydantic import ValidationError

from receipt_sorter.ai import DocumentInput
from receipt_sorter.corrections import build_correction_input
from receipt_sorter.log import log_step
from receipt_sorter.models import Correction, DocumentResult
from receipt_sorter.prompts import (
    CATEGORY_PROMPT_LIST,
    CLASSIFIER_SYSTEM_PROMPT,
    CORRECTION_SYSTEM_PROMPT,
)
from receipt_sorter.validation import InvalidClassificationError, validate_document_result

PROMPT_CACHE_KEY_PREFIX = "receipt-sorter"
EXTENDED_PROMPT_CACHE_MODEL_PREFIXES = ("gpt-5", "gpt-4.1")


def build_classifier_instructions(default_currency: str) -> str:
    return CLASSIFIER_SYSTEM_PROMPT.format(
        category_list=CATEGORY_PROMPT_LIST,
        default_currency=default_currency,
    )


def build_classifier_input(memory_md_content: str, file_id: str) -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": f"# MEMORY.md\n\n{memory_md_content}\n\nClassify the document below.",
                },
                {
                    "type": "input_file",
                    "file_id": file_id,
                },
            ],
        }
    ]


def supports_extended_prompt_cache(model: str) -> bool:
    normalized_model = model.strip().lower()
    return normalized_model.startswith(EXTENDED_PROMPT_CACHE_MODEL_PREFIXES)


def build_prompt_cache_key(
    flow: str,
    model: str,
    static_prompt_content: str,
) -> str:
    normalized_model = model.strip().lower() or "unknown"
    cache_identity = f"{normalized_model}\0{static_prompt_content}"
    digest = sha256(cache_identity.encode("utf-8")).hexdigest()[:32]
    return f"{PROMPT_CACHE_KEY_PREFIX}:{flow}:{digest}"


def build_openai_model_settings_kwargs(
    flow: str,
    model: str,
    static_prompt_content: str,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "extra_args": {
            "prompt_cache_key": build_prompt_cache_key(flow, model, static_prompt_content),
        }
    }
    if supports_extended_prompt_cache(model):
        kwargs["prompt_cache_retention"] = "24h"
    return kwargs


def log_openai_usage(label: str, usage: Any) -> None:
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    total_tokens = getattr(usage, "total_tokens", 0) or 0
    input_token_details = getattr(usage, "input_tokens_details", None)
    cached_tokens = getattr(input_token_details, "cached_tokens", 0) or 0
    if not any((input_tokens, output_tokens, total_tokens, cached_tokens)):
        return
    log_step(
        f"{label} token usage: input={input_tokens}, cached={cached_tokens}, "
        f"output={output_tokens}, total={total_tokens}."
    )


async def upload_document_for_model(document: DocumentInput) -> str:
    log_step("Uploading document to OpenAI Files API...")
    client = AsyncOpenAI()
    uploaded = await client.files.create(
        file=(document.filename, document.content, document.mime_type),
        purpose="user_data",
    )
    log_step(f"Uploaded document to OpenAI as {uploaded.id}.")
    return uploaded.id


async def delete_uploaded_document(file_id: str) -> None:
    log_step(f"Deleting OpenAI uploaded file {file_id}...")
    client = AsyncOpenAI()
    await client.files.delete(file_id)
    log_step(f"Deleted OpenAI uploaded file {file_id}.")


async def best_effort_delete_uploaded_document(file_id: str) -> None:
    try:
        await delete_uploaded_document(file_id)
    except Exception as exc:
        log_step(f"Failed to delete OpenAI uploaded file {file_id}: {exc}")


class OpenAIDocumentClassifier:
    def __init__(self, model: str):
        self.model = model

    async def classify(
        self,
        document: DocumentInput,
        memory_md_content: str,
        default_currency: str,
    ) -> DocumentResult:
        from agents import Agent, ModelSettings, RunContextWrapper, Runner

        instructions = build_classifier_instructions(default_currency)
        agent = Agent(
            name="DocClassifier",
            model=self.model,
            instructions=instructions,
            model_settings=ModelSettings(
                **build_openai_model_settings_kwargs(
                    "classifier",
                    self.model,
                    f"{instructions}\n\n# MEMORY.md\n\n{memory_md_content}",
                )
            ),
            output_type=DocumentResult,
        )
        file_id = await upload_document_for_model(document)
        log_step("Running DocClassifier agent...")
        run_context = RunContextWrapper(context=None)
        try:
            result = await Runner.run(
                agent,
                input=cast(Any, build_classifier_input(memory_md_content, file_id)),
                context=run_context,
            )
            log_step("DocClassifier returned structured output.")
            log_openai_usage("DocClassifier", run_context.usage)
            return validate_document_result(result.final_output)
        except ValidationError as exc:
            raise InvalidClassificationError(str(exc)) from exc
        finally:
            await best_effort_delete_uploaded_document(file_id)


class OpenAICorrectionParser:
    def __init__(self, model: str):
        self.model = model

    async def parse(self, original_summary: str, user_reply: str) -> Correction:
        from agents import Agent, ModelSettings, RunContextWrapper, Runner

        instructions = CORRECTION_SYSTEM_PROMPT.format(category_list=CATEGORY_PROMPT_LIST)
        agent = Agent(
            name="CorrectionAgent",
            model=self.model,
            instructions=instructions,
            model_settings=ModelSettings(
                **build_openai_model_settings_kwargs(
                    "correction",
                    self.model,
                    instructions,
                )
            ),
            output_type=Correction,
        )
        run_context = RunContextWrapper(context=None)
        try:
            result = await Runner.run(
                agent,
                input=build_correction_input(original_summary, user_reply),
                context=run_context,
            )
            log_openai_usage("CorrectionAgent", run_context.usage)
            return result.final_output
        except ValidationError:
            return Correction(vendor=None, new_category=None, reason=None)
