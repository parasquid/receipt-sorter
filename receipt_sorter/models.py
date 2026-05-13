from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

CategoryName = Literal[
    "Transport & Travel",
    "Accommodation",
    "Meals & Entertainment",
    "Utilities",
    "Telecommunications",
    "Software & Subscriptions",
    "Office Supplies",
    "Equipment & Hardware",
    "Professional Services",
    "Marketing & Advertising",
    "Rental",
    "Banking & Finance",
    "Insurance",
    "Salaries & Payroll",
    "Government & Statutory",
    "Training & Development",
    "Other",
]

CATEGORY_NAMES: tuple[CategoryName, ...] = (
    "Transport & Travel",
    "Accommodation",
    "Meals & Entertainment",
    "Utilities",
    "Telecommunications",
    "Software & Subscriptions",
    "Office Supplies",
    "Equipment & Hardware",
    "Professional Services",
    "Marketing & Advertising",
    "Rental",
    "Banking & Finance",
    "Insurance",
    "Salaries & Payroll",
    "Government & Statutory",
    "Training & Development",
    "Other",
)


class DocumentResult(BaseModel):
    supplier: str = Field(min_length=1)
    category: CategoryName
    date: str = Field(min_length=1)
    amount: float | None
    currency: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class Correction(BaseModel):
    vendor: str | None
    new_category: CategoryName | None
    reason: str | None = None


@dataclass(frozen=True)
class ProcessedDocument:
    original_name: str
    destination_year: str
    destination_month: str
    new_name: str
    result: DocumentResult


@dataclass(frozen=True)
class NeedsReviewDocument:
    original_name: str
    review_folder_name: str
    reason: str


ProcessingOutcome = ProcessedDocument | NeedsReviewDocument


@dataclass
class SessionState:
    processed_count: int = 0
    telegram_available: bool = True
    in_progress_file_ids: set[str] = field(default_factory=set)
