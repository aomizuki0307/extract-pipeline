"""Confidence-based router — route classified documents to extraction or fallback."""

from __future__ import annotations

from src.models import ClassificationResult


class RoutingDecision:
    """Encapsulates a routing decision."""

    def __init__(
        self,
        action: str,
        doc_type: str,
        confidence: float,
        reason: str = "",
    ) -> None:
        self.action = action  # "extract" | "fallback" | "reject"
        self.doc_type = doc_type
        self.confidence = confidence
        self.reason = reason


class Router:
    """Route documents based on classification confidence.

    - confidence >= threshold → extract with the classified schema
    - confidence >= fallback_threshold → extract with generic/fallback schema
    - confidence < fallback_threshold → reject
    """

    def __init__(
        self,
        threshold: float = 0.7,
        fallback_threshold: float = 0.3,
        available_types: list[str] | None = None,
    ) -> None:
        self._threshold = threshold
        self._fallback_threshold = fallback_threshold
        self._available_types = set(available_types or [])

    def route(self, classification: ClassificationResult) -> RoutingDecision:
        """Determine routing action based on classification result."""
        doc_type = classification.doc_type
        confidence = classification.confidence

        # Check if doc_type has a registered schema
        if self._available_types and doc_type not in self._available_types:
            return RoutingDecision(
                action="reject",
                doc_type=doc_type,
                confidence=confidence,
                reason=f"Unknown document type '{doc_type}'",
            )

        if confidence >= self._threshold:
            return RoutingDecision(
                action="extract",
                doc_type=doc_type,
                confidence=confidence,
                reason=f"High confidence ({confidence:.2f} >= {self._threshold})",
            )

        if confidence >= self._fallback_threshold:
            return RoutingDecision(
                action="fallback",
                doc_type=doc_type,
                confidence=confidence,
                reason=(
                    f"Low confidence ({confidence:.2f}), "
                    f"below threshold {self._threshold} — using fallback extraction"
                ),
            )

        return RoutingDecision(
            action="reject",
            doc_type=doc_type,
            confidence=confidence,
            reason=(
                f"Very low confidence ({confidence:.2f} < {self._fallback_threshold}) "
                "— document rejected for manual review"
            ),
        )
