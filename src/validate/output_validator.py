"""Output validator — YAML schema → dynamic Pydantic model → LLM output validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError, create_model

from src.extract.schema_registry import SchemaRegistry
from src.models import ValidationIssue, ValidationResult

# Mapping from YAML type names to Python types
_TYPE_MAP: dict[str, type] = {
    "string": str,
    "number": float,
    "integer": int,
    "boolean": bool,
    "list": list,
}


class OutputValidator:
    """Validate LLM extraction output against YAML schemas."""

    def __init__(self, schema_registry: SchemaRegistry) -> None:
        self._registry = schema_registry
        self._model_cache: dict[str, type[BaseModel]] = {}

    def validate(
        self, data: dict[str, Any], doc_type: str
    ) -> ValidationResult:
        """Validate extracted data against the schema for doc_type."""
        issues: list[ValidationIssue] = []
        fields_def = self._registry.get_field_definitions(doc_type)

        # Check required fields
        for name, spec in fields_def.items():
            if spec.get("required") and name not in data:
                issues.append(ValidationIssue(
                    field=name,
                    issue=f"Required field '{name}' is missing",
                    severity="error",
                ))

        # Check for extra fields not in schema
        schema_fields = set(fields_def.keys())
        for key in data:
            if key not in schema_fields:
                issues.append(ValidationIssue(
                    field=key,
                    issue=f"Unexpected field '{key}' not in schema",
                    severity="warning",
                ))

        # Try dynamic Pydantic validation
        try:
            model_cls = self._get_or_build_model(doc_type, fields_def)
            validated = model_cls.model_validate(data)
            validated_data = validated.model_dump()
        except ValidationError as e:
            for error in e.errors():
                field_name = ".".join(str(loc) for loc in error["loc"])
                issues.append(ValidationIssue(
                    field=field_name,
                    issue=error["msg"],
                    severity="error",
                ))
            validated_data = data

        is_valid = not any(i.severity == "error" for i in issues)
        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            validated_data=validated_data if is_valid else data,
        )

    def _get_or_build_model(
        self, doc_type: str, fields_def: dict[str, dict[str, Any]]
    ) -> type[BaseModel]:
        """Build or retrieve a cached dynamic Pydantic model for a doc_type."""
        if doc_type in self._model_cache:
            return self._model_cache[doc_type]

        field_definitions: dict[str, Any] = {}
        for name, spec in fields_def.items():
            py_type = _TYPE_MAP.get(spec.get("type", "string"), Any)
            if spec.get("required"):
                field_definitions[name] = (py_type, ...)
            else:
                field_definitions[name] = (py_type | None, None)

        model = create_model(f"{doc_type}_Model", **field_definitions)
        self._model_cache[doc_type] = model
        return model
