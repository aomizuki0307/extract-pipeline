"""Data models for the Extract Pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    """Result of document classification."""

    doc_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class ExtractionField(BaseModel):
    """A single extracted field with its value and source evidence."""

    name: str
    value: Any
    evidence: str = ""


class ExtractionResult(BaseModel):
    """Result of schema-driven extraction."""

    doc_type: str
    fields: dict[str, Any] = Field(default_factory=dict)
    raw_response: str = ""


class ValidationIssue(BaseModel):
    """A single validation issue found in the extraction output."""

    field: str
    issue: str
    severity: str = "error"  # error | warning


class ValidationResult(BaseModel):
    """Result of output validation."""

    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    validated_data: dict[str, Any] = Field(default_factory=dict)


class PipelineResult(BaseModel):
    """Full pipeline result combining classification, extraction, and validation."""

    source: str = ""
    classification: ClassificationResult | None = None
    extraction: ExtractionResult | None = None
    validation: ValidationResult | None = None
    routed: bool = True
    route_action: str = "extract"  # extract | fallback | reject
    guardrail_flags: list[str] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    duration_seconds: float = 0.0


class FieldScore(BaseModel):
    """Score for a single field comparison."""

    field: str
    expected: Any = None
    actual: Any = None
    match: bool = False
    match_type: str = ""  # exact | fuzzy | missing | extra


class EvalResult(BaseModel):
    """Evaluation result for a single test case."""

    case_id: str
    doc_type: str
    field_scores: list[FieldScore] = Field(default_factory=list)
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    error: str | None = None
