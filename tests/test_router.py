"""Tests for the confidence-based router."""

from __future__ import annotations

from src.models import ClassificationResult
from src.route.router import Router


class TestRouter:
    def test_high_confidence_routes_to_extract(self):
        router = Router(threshold=0.7, available_types=["invoice"])
        classification = ClassificationResult(
            doc_type="invoice", confidence=0.95, reasoning="test"
        )
        decision = router.route(classification)

        assert decision.action == "extract"
        assert decision.doc_type == "invoice"

    def test_medium_confidence_routes_to_fallback(self):
        router = Router(threshold=0.7, fallback_threshold=0.3)
        classification = ClassificationResult(
            doc_type="invoice", confidence=0.5, reasoning="test"
        )
        decision = router.route(classification)

        assert decision.action == "fallback"

    def test_low_confidence_rejects(self):
        router = Router(threshold=0.7, fallback_threshold=0.3)
        classification = ClassificationResult(
            doc_type="invoice", confidence=0.1, reasoning="test"
        )
        decision = router.route(classification)

        assert decision.action == "reject"

    def test_unknown_type_rejects(self):
        router = Router(available_types=["invoice", "email"])
        classification = ClassificationResult(
            doc_type="unknown_type", confidence=0.99, reasoning="test"
        )
        decision = router.route(classification)

        assert decision.action == "reject"
        assert "Unknown" in decision.reason

    def test_boundary_confidence_at_threshold(self):
        router = Router(threshold=0.7)
        classification = ClassificationResult(
            doc_type="invoice", confidence=0.7, reasoning="test"
        )
        decision = router.route(classification)

        assert decision.action == "extract"

    def test_no_available_types_skips_type_check(self):
        router = Router(threshold=0.7)
        classification = ClassificationResult(
            doc_type="anything", confidence=0.9, reasoning="test"
        )
        decision = router.route(classification)

        assert decision.action == "extract"
