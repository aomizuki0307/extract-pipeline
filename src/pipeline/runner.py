"""Pipeline runner — orchestrate classify → route → extract → validate → guard."""

from __future__ import annotations

import time
from typing import Any

from src.classify.classifier import Classifier
from src.extract.extractor import Extractor
from src.extract.schema_registry import SchemaRegistry
from src.guardrails.input_sanitizer import InputSanitizer
from src.guardrails.output_guard import OutputGuard
from src.models import PipelineResult
from src.route.router import Router
from src.validate.output_validator import OutputValidator


class PipelineRunner:
    """Orchestrate the full extraction pipeline."""

    def __init__(
        self,
        client: Any,
        schema_registry: SchemaRegistry,
        classification_model: str = "claude-sonnet-4-20250514",
        extraction_model: str = "claude-sonnet-4-20250514",
        confidence_threshold: float = 0.7,
        max_input_length: int = 10000,
        injection_patterns: list[str] | None = None,
    ) -> None:
        self._classifier = Classifier(
            client=client,
            model=classification_model,
            doc_types=schema_registry.list_types(),
        )
        self._extractor = Extractor(
            client=client,
            schema_registry=schema_registry,
            model=extraction_model,
        )
        self._router = Router(
            threshold=confidence_threshold,
            available_types=schema_registry.list_types(),
        )
        self._sanitizer = InputSanitizer(
            max_length=max_input_length,
            injection_patterns=injection_patterns,
        )
        self._validator = OutputValidator(schema_registry)
        self._guard = OutputGuard(schema_registry)

    def run(self, text: str, source: str = "") -> PipelineResult:
        """Run the full pipeline on a single document."""
        start = time.time()
        result = PipelineResult(source=source)

        # Step 1: Input sanitization
        is_safe, flags = self._sanitizer.check(text)
        result.guardrail_flags.extend(flags)
        if not is_safe:
            result.routed = False
            result.route_action = "reject"
            result.duration_seconds = time.time() - start
            return result

        # Step 2: Classification
        classification = self._classifier.classify(text)
        result.classification = classification

        # Step 3: Routing
        decision = self._router.route(classification)
        result.route_action = decision.action
        result.routed = decision.action == "extract"

        if decision.action == "reject":
            result.guardrail_flags.append(decision.reason)
            result.duration_seconds = time.time() - start
            return result

        # Step 4: Extraction (for both "extract" and "fallback")
        extraction = self._extractor.extract(text, classification.doc_type)
        result.extraction = extraction

        # Step 5: Validation
        validation = self._validator.validate(
            extraction.fields, classification.doc_type
        )
        result.validation = validation

        # Step 6: Output guard
        is_clean, guard_flags = self._guard.check(
            extraction.fields, classification.doc_type
        )
        result.guardrail_flags.extend(guard_flags)

        if decision.action == "fallback":
            result.guardrail_flags.append(decision.reason)

        result.duration_seconds = time.time() - start
        return result
