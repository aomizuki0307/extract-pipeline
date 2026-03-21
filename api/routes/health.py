"""Health check route."""

from __future__ import annotations

from fastapi import APIRouter

from api.models import HealthResponse
from src.config import get_settings
from src.extract.schema_registry import SchemaRegistry

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    registry = SchemaRegistry(settings.pipeline.schemas_dir)
    return HealthResponse(status="ok", schemas_loaded=len(registry.list_types()))
