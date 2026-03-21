"""Extraction route."""

from __future__ import annotations

import anthropic
from fastapi import APIRouter, Depends, HTTPException

from api.deps import build_pipeline, get_api_key
from api.models import ClassifyResponse, ExtractRequest, ExtractResponse, StageResult
from src.models import PipelineResult

router = APIRouter()


def _build_stages(result: PipelineResult) -> list[StageResult]:
    stages: list[StageResult] = []

    # sanitize
    rejected_at_sanitize = result.route_action == "reject" and result.classification is None
    injection_flags = [f for f in result.guardrail_flags if "inject" in f.lower() or "length" in f.lower()]
    if rejected_at_sanitize:
        stages.append(StageResult(
            stage="sanitize",
            status="fail",
            detail=", ".join(result.guardrail_flags) if result.guardrail_flags else "rejected",
        ))
    else:
        stages.append(StageResult(stage="sanitize", status="pass"))

    # classify
    if result.classification:
        stages.append(StageResult(
            stage="classify",
            status="pass",
            detail=f"{result.classification.doc_type} ({result.classification.confidence:.0%})",
        ))
    else:
        stages.append(StageResult(stage="classify", status="skip"))

    # route
    if rejected_at_sanitize:
        stages.append(StageResult(stage="route", status="skip"))
    elif result.route_action in ("extract", "fallback"):
        stages.append(StageResult(stage="route", status="pass", detail=result.route_action))
    else:
        stages.append(StageResult(stage="route", status="fail", detail=result.route_action))

    # extract
    if result.extraction:
        stages.append(StageResult(stage="extract", status="pass"))
    else:
        stages.append(StageResult(stage="extract", status="skip"))

    # validate
    if result.validation:
        if result.validation.is_valid:
            stages.append(StageResult(stage="validate", status="pass"))
        else:
            issues_summary = "; ".join(
                f"{i.field}: {i.issue}" for i in result.validation.issues
            )
            stages.append(StageResult(stage="validate", status="fail", detail=issues_summary))
    else:
        stages.append(StageResult(stage="validate", status="skip"))

    # guard
    if rejected_at_sanitize:
        stages.append(StageResult(stage="guard", status="skip"))
    else:
        non_injection_flags = [
            f for f in result.guardrail_flags
            if "inject" not in f.lower() and "length" not in f.lower()
        ]
        if non_injection_flags:
            stages.append(StageResult(
                stage="guard",
                status="warn",
                detail=", ".join(non_injection_flags),
            ))
        else:
            stages.append(StageResult(stage="guard", status="pass"))

    return stages


@router.post("/extract", response_model=ExtractResponse)
def extract(body: ExtractRequest, api_key: str = Depends(get_api_key)) -> ExtractResponse:
    pipeline = build_pipeline(api_key)
    try:
        result = pipeline.run(body.text, source="api")
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid Anthropic API key")
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {exc.message}")

    classification_resp = None
    if result.classification:
        classification_resp = ClassifyResponse(
            doc_type=result.classification.doc_type,
            confidence=result.classification.confidence,
            reasoning=result.classification.reasoning,
        )

    extraction_dict = None
    if result.extraction:
        extraction_dict = result.extraction.fields

    validation_dict = None
    if result.validation:
        validation_dict = result.validation.model_dump()

    return ExtractResponse(
        source=result.source,
        classification=classification_resp,
        extraction=extraction_dict,
        validation=validation_dict,
        route_action=result.route_action,
        guardrail_flags=result.guardrail_flags,
        stages=_build_stages(result),
        duration_seconds=result.duration_seconds,
    )
