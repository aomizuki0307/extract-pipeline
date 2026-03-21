"""YAML schema registry — load, validate, and look up extraction schemas."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class SchemaNotFoundError(Exception):
    """Raised when a schema for the requested doc_type is not found."""


class SchemaRegistry:
    """Load and manage YAML extraction schemas.

    Each schema YAML file defines a doc_type, description, and fields.
    """

    def __init__(self, schemas_dir: str | Path = "data/schemas") -> None:
        self._schemas_dir = Path(schemas_dir)
        self._schemas: dict[str, dict[str, Any]] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all .yaml files from the schemas directory."""
        if not self._schemas_dir.exists():
            return
        for path in sorted(self._schemas_dir.glob("*.yaml")):
            with open(path, encoding="utf-8") as f:
                schema = yaml.safe_load(f)
            if schema and "doc_type" in schema:
                self._schemas[schema["doc_type"]] = schema

    def get(self, doc_type: str) -> dict[str, Any]:
        """Get a schema by doc_type. Raises SchemaNotFoundError if missing."""
        if doc_type not in self._schemas:
            raise SchemaNotFoundError(
                f"No schema found for doc_type '{doc_type}'. "
                f"Available: {list(self._schemas.keys())}"
            )
        return self._schemas[doc_type]

    def list_types(self) -> list[str]:
        """Return all registered doc_type names."""
        return list(self._schemas.keys())

    def list_schemas(self) -> list[dict[str, Any]]:
        """Return all schemas with their metadata."""
        result = []
        for doc_type, schema in self._schemas.items():
            fields = schema.get("fields", {})
            required = [k for k, v in fields.items() if v.get("required")]
            optional = [k for k, v in fields.items() if not v.get("required")]
            result.append({
                "doc_type": doc_type,
                "description": schema.get("description", ""),
                "required_fields": required,
                "optional_fields": optional,
            })
        return result

    def get_field_definitions(self, doc_type: str) -> dict[str, dict[str, Any]]:
        """Return just the fields dict for a doc_type."""
        schema = self.get(doc_type)
        return schema.get("fields", {})

    def format_for_prompt(self, doc_type: str) -> str:
        """Format schema fields as a prompt-friendly string."""
        fields = self.get_field_definitions(doc_type)
        lines = []
        for name, spec in fields.items():
            req = "REQUIRED" if spec.get("required") else "optional"
            ftype = spec.get("type", "string")
            desc = spec.get("description", "")
            lines.append(f"- {name} ({ftype}, {req}): {desc}")
            if ftype == "list" and "item_fields" in spec:
                for iname, ispec in spec["item_fields"].items():
                    ireq = "REQUIRED" if ispec.get("required") else "optional"
                    idesc = ispec.get("description", "")
                    itype = ispec.get('type', 'string')
                    lines.append(
                        f"    - {iname} ({itype}, {ireq}): {idesc}"
                    )
        return "\n".join(lines)
