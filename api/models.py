"""Pydantic request/response models for the Extract Pipeline API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ClassifyRequest(BaseModel):
    text: str


class ExtractRequest(BaseModel):
    text: str


class StageResult(BaseModel):
    stage: str
    status: str
    detail: str = ""
    duration_ms: float = 0


class ClassifyResponse(BaseModel):
    doc_type: str
    confidence: float
    reasoning: str


class ExtractResponse(BaseModel):
    source: str
    classification: ClassifyResponse | None
    extraction: dict[str, Any] | None
    validation: dict[str, Any] | None
    route_action: str
    guardrail_flags: list[str]
    stages: list[StageResult]
    duration_seconds: float


class SchemaDetail(BaseModel):
    doc_type: str
    description: str
    required_fields: list[str]
    optional_fields: list[str]
    raw_yaml: str


class HealthResponse(BaseModel):
    status: str
    schemas_loaded: int


class SampleInfo(BaseModel):
    name: str
    doc_type: str
