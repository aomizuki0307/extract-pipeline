"""Document classifier — multi-class classification with confidence score."""

from __future__ import annotations

import json
from typing import Any

from src.models import ClassificationResult

_SYSTEM_PROMPT = """\
You are a document classifier. Given an input document, classify it into \
exactly one of the following types: {doc_types}.

Respond with a JSON object containing:
- "doc_type": one of {doc_types}
- "confidence": a float between 0.0 and 1.0 indicating your confidence
- "reasoning": a brief explanation of why you chose this classification

Respond ONLY with the JSON object. No additional text."""


class Classifier:
    """Classify documents into predefined types using Claude."""

    def __init__(
        self,
        client: Any,
        model: str = "claude-sonnet-4-20250514",
        doc_types: list[str] | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._doc_types = doc_types or ["invoice", "support_ticket", "email"]

    def classify(self, text: str) -> ClassificationResult:
        """Classify a document and return the result with confidence score."""
        doc_types_str = ", ".join(self._doc_types)
        system = _SYSTEM_PROMPT.format(doc_types=doc_types_str)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": text}],
        )

        raw = self._extract_text(response)
        return self._parse_response(raw)

    def _extract_text(self, response: Any) -> str:
        """Extract text content from Claude response."""
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    def _parse_response(self, raw: str) -> ClassificationResult:
        """Parse the JSON response into a ClassificationResult."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])

        data = json.loads(cleaned)
        return ClassificationResult(
            doc_type=data["doc_type"],
            confidence=float(data["confidence"]),
            reasoning=data.get("reasoning", ""),
        )

    def get_token_usage(self, response: Any) -> tuple[int, int]:
        """Extract token usage from a response."""
        usage = getattr(response, "usage", None)
        if usage:
            return (
                getattr(usage, "input_tokens", 0),
                getattr(usage, "output_tokens", 0),
            )
        return (0, 0)
