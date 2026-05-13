from __future__ import annotations

import asyncio

from receipt_sorter.ai import DocumentClassifier, DocumentInput
from receipt_sorter.log import log_step
from receipt_sorter.models import DocumentResult
from receipt_sorter.validation import InvalidClassificationError, validate_document_result


async def classify_document_with_retry(
    classifier: DocumentClassifier,
    document: DocumentInput,
    memory_md_content: str,
    default_currency: str,
) -> DocumentResult:
    try:
        result = await classifier.classify(document, memory_md_content, default_currency)
        return validate_document_result(result)
    except InvalidClassificationError:
        raise
    except Exception as first_error:
        log_step(f"Model error: {first_error}. Retrying once in 5s...")
        await asyncio.sleep(5)
        result = await classifier.classify(document, memory_md_content, default_currency)
        return validate_document_result(result)
