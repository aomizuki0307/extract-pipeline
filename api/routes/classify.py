"""Classification route."""

from __future__ import annotations

import anthropic
from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_api_key
from api.models import ClassifyRequest, ClassifyResponse
from src.classify.classifier import Classifier
from src.config import get_settings
from src.guardrails.input_sanitizer import InputSanitizer

router = APIRouter()


@router.post("/classify", response_model=ClassifyResponse)
def classify(body: ClassifyRequest, api_key: str = Depends(get_api_key)) -> ClassifyResponse:
    settings = get_settings()
    sanitizer = InputSanitizer(
        max_length=settings.guardrails.max_input_length,
        injection_patterns=settings.guardrails.injection_patterns,
    )
    is_safe, flags = sanitizer.check(body.text)
    if not is_safe:
        raise HTTPException(status_code=422, detail=f"Input rejected: {', '.join(flags)}")
    client = anthropic.Anthropic(api_key=api_key)
    classifier = Classifier(
        client=client,
        model=settings.classification.model,
        doc_types=settings.classification.doc_types,
    )
    try:
        result = classifier.classify(body.text)
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid Anthropic API key")
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {exc.message}")
    return ClassifyResponse(
        doc_type=result.doc_type,
        confidence=result.confidence,
        reasoning=result.reasoning,
    )
