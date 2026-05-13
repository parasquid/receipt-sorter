from __future__ import annotations

from receipt_sorter.config import Config
from receipt_sorter.openai_provider import OpenAICorrectionParser, OpenAIDocumentClassifier


def build_document_classifier(config: Config) -> OpenAIDocumentClassifier:
    return OpenAIDocumentClassifier(model=config.openai_model)


def build_correction_parser(config: Config) -> OpenAICorrectionParser:
    return OpenAICorrectionParser(model=config.openai_model)
