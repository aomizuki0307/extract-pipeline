"""Schema and sample routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.models import SampleInfo, SchemaDetail
from src.config import get_settings
from src.extract.schema_registry import SchemaNotFoundError, SchemaRegistry

router = APIRouter()


def _get_registry() -> SchemaRegistry:
    settings = get_settings()
    return SchemaRegistry(settings.pipeline.schemas_dir)


def _schemas_dir() -> Path:
    return Path(get_settings().pipeline.schemas_dir)


def _samples_dir() -> Path:
    return Path(get_settings().pipeline.samples_dir)


@router.get("/schemas", response_model=list[SchemaDetail])
def list_schemas() -> list[SchemaDetail]:
    registry = _get_registry()
    schemas_dir = _schemas_dir()
    result = []
    for item in registry.list_schemas():
        doc_type = item["doc_type"]
        yaml_path = schemas_dir / f"{doc_type}.yaml"
        raw_yaml = yaml_path.read_text(encoding="utf-8") if yaml_path.exists() else ""
        result.append(
            SchemaDetail(
                doc_type=doc_type,
                description=item["description"],
                required_fields=item["required_fields"],
                optional_fields=item["optional_fields"],
                raw_yaml=raw_yaml,
            )
        )
    return result


@router.get("/schemas/{doc_type}", response_model=SchemaDetail)
def get_schema(doc_type: str) -> SchemaDetail:
    registry = _get_registry()
    schemas_dir = _schemas_dir()
    try:
        item = registry.get(doc_type)
    except SchemaNotFoundError:
        raise HTTPException(status_code=404, detail=f"Schema '{doc_type}' not found")

    fields = item.get("fields", {})
    required_fields = [k for k, v in fields.items() if v.get("required")]
    optional_fields = [k for k, v in fields.items() if not v.get("required")]
    yaml_path = schemas_dir / f"{doc_type}.yaml"
    raw_yaml = yaml_path.read_text(encoding="utf-8") if yaml_path.exists() else ""

    return SchemaDetail(
        doc_type=doc_type,
        description=item.get("description", ""),
        required_fields=required_fields,
        optional_fields=optional_fields,
        raw_yaml=raw_yaml,
    )


@router.get("/samples", response_model=list[SampleInfo])
def list_samples() -> list[SampleInfo]:
    samples_dir = _samples_dir()
    result = []
    for path in sorted(samples_dir.glob("*.txt")):
        if not path.is_file():
            continue
        name = path.name
        # Strip trailing _NN.txt to get doc_type (e.g. "invoice_01.txt" -> "invoice")
        stem = path.stem  # e.g. "invoice_01"
        parts = stem.rsplit("_", 1)
        doc_type = parts[0] if len(parts) == 2 and parts[1].isdigit() else stem
        result.append(SampleInfo(name=name, doc_type=doc_type))
    return result


@router.get("/samples/{name}")
def get_sample(name: str) -> dict:
    samples_dir = _samples_dir()
    path = (samples_dir / name).resolve()
    if not path.is_relative_to(samples_dir.resolve()) or not path.is_file() or path.suffix != ".txt":
        raise HTTPException(status_code=404, detail=f"Sample '{name}' not found")
    return {"name": name, "content": path.read_text(encoding="utf-8")}
