"""Dependency injection helpers for the Extract Pipeline API."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()


def get_api_key(x_api_key: str = Header(None)) -> str:
    key = x_api_key or os.environ.get("ANTHROPIC_API_KEY") or ""
    if not key:
        from src.config import get_settings
        key = get_settings().anthropic_api_key
    if not key:
        raise HTTPException(status_code=401, detail="Anthropic API key required")
    return key


def build_pipeline(api_key: str):
    import anthropic

    from src.config import get_settings
    from src.extract.schema_registry import SchemaRegistry
    from src.pipeline.runner import PipelineRunner

    settings = get_settings()
    client = anthropic.Anthropic(api_key=api_key)
    registry = SchemaRegistry(settings.pipeline.schemas_dir)

    return PipelineRunner(
        client=client,
        schema_registry=registry,
        classification_model=settings.classification.model,
        extraction_model=settings.extraction.model,
        confidence_threshold=settings.classification.confidence_threshold,
        max_input_length=settings.guardrails.max_input_length,
        injection_patterns=settings.guardrails.injection_patterns,
    )
