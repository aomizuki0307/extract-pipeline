"""Output guard — schema conformance and hallucination detection."""

from __future__ import annotations

from typing import Any

from src.extract.schema_registry import SchemaRegistry


class OutputGuard:
    """Post-validation guard for extraction output.

    Checks:
    1. No extra fields outside the schema.
    2. All required fields are present and non-null.
    3. Field values are not suspiciously generic (potential hallucinations).
    """

    _SUSPICIOUS_VALUES = {
        "n/a", "unknown", "not found", "none", "null",
        "placeholder", "example", "test", "tbd",
    }

    def __init__(self, schema_registry: SchemaRegistry) -> None:
        self._registry = schema_registry

    def check(
        self, data: dict[str, Any], doc_type: str
    ) -> tuple[bool, list[str]]:
        """Check extraction output for conformance issues.

        Returns (is_clean, list_of_flags).
        """
        flags: list[str] = []
        fields_def = self._registry.get_field_definitions(doc_type)

        # Check required fields
        for name, spec in fields_def.items():
            if spec.get("required"):
                if name not in data:
                    flags.append(f"Required field '{name}' is missing")
                elif data[name] is None:
                    flags.append(f"Required field '{name}' is null")

        # Check for extra fields
        schema_fields = set(fields_def.keys())
        for key in data:
            if key not in schema_fields:
                flags.append(f"Extra field '{key}' not in schema")

        # Check for suspicious/hallucinated values
        for name, value in data.items():
            if not isinstance(value, str):
                continue
            if value.strip().lower() in self._SUSPICIOUS_VALUES:
                flags.append(
                    f"Field '{name}' has suspicious value "
                    f"'{value}' — possible hallucination"
                )

        return (len(flags) == 0, flags)
