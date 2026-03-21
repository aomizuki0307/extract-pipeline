"""Configuration management for the Extract Pipeline."""

from __future__ import annotations

import functools
from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClassificationConfig(BaseModel):
    model: str = "claude-sonnet-4-20250514"
    confidence_threshold: float = 0.7
    doc_types: list[str] = ["invoice", "support_ticket", "email"]


class ExtractionConfig(BaseModel):
    model: str = "claude-sonnet-4-20250514"
    max_retries: int = 2


class GuardrailsConfig(BaseModel):
    max_input_length: int = 10000
    injection_patterns: list[str] = [
        "ignore previous instructions",
        "ignore all instructions",
        "disregard your instructions",
        "you are now",
        "act as if",
        "pretend you are",
        "forget everything",
        "system prompt",
        "jailbreak",
        "reveal your prompt",
        "output your instructions",
    ]


class PipelineConfig(BaseModel):
    schemas_dir: str = "data/schemas"
    samples_dir: str = "data/samples"
    golden_path: str = "data/golden/test_cases.yaml"
    results_dir: str = "results"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EXTRACT_",
        env_nested_delimiter="__",
    )

    anthropic_api_key: str = ""
    classification: ClassificationConfig = ClassificationConfig()
    extraction: ExtractionConfig = ExtractionConfig()
    guardrails: GuardrailsConfig = GuardrailsConfig()
    pipeline: PipelineConfig = PipelineConfig()

    @classmethod
    def from_yaml(cls, path: Path | str = "config.yaml") -> Settings:
        """Load settings from a YAML file, with env overrides."""
        p = Path(path)
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}
        return cls(**data)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings singleton."""
    return Settings.from_yaml()
