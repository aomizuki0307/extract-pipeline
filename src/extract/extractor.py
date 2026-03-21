"""Schema-driven field extractor — Claude + schema prompt → structured JSON."""

from __future__ import annotations

import json
from typing import Any

from src.extract.schema_registry import SchemaRegistry
from src.models import ExtractionResult

_SYSTEM_PROMPT = """\
You are a structured data extractor. Given a document and a schema, \
extract the specified fields from the document.

Schema for document type "{doc_type}":
{schema_fields}

Instructions:
- Extract ONLY the fields listed in the schema.
- For REQUIRED fields, always provide a value. Use null if not found in the document.
- For optional fields, include them only if found in the document.
- For "list" type fields, return an array of objects with the specified item_fields.
- For "number" type fields, return numeric values (not strings).
- Return a JSON object with field names as keys.
- Respond ONLY with the JSON object. No additional text."""


class Extractor:
    """Extract structured fields from documents using Claude and YAML schemas."""

    def __init__(
        self,
        client: Any,
        schema_registry: SchemaRegistry,
        model: str = "claude-sonnet-4-20250514",
        max_retries: int = 2,
    ) -> None:
        self._client = client
        self._registry = schema_registry
        self._model = model
        self._max_retries = max_retries

    def extract(self, text: str, doc_type: str) -> ExtractionResult:
        """Extract fields from a document based on its schema."""
        schema_fields = self._registry.format_for_prompt(doc_type)
        system = _SYSTEM_PROMPT.format(
            doc_type=doc_type,
            schema_fields=schema_fields,
        )

        last_error: Exception | None = None
        for _attempt in range(self._max_retries + 1):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=2048,
                    system=system,
                    messages=[{"role": "user", "content": text}],
                )
                raw = self._extract_text(response)
                fields = self._parse_response(raw)
                return ExtractionResult(
                    doc_type=doc_type,
                    fields=fields,
                    raw_response=raw,
                )
            except (json.JSONDecodeError, KeyError) as e:
                last_error = e
                continue

        raise ValueError(
            f"Failed to extract after {self._max_retries + 1} attempts: {last_error}"
        )

    def _extract_text(self, response: Any) -> str:
        """Extract text content from Claude response."""
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    def _parse_response(self, raw: str) -> dict[str, Any]:
        """Parse the JSON response into a dict of fields."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])
        return json.loads(cleaned)
