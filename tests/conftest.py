"""Shared test fixtures — FakeClaudeClient and helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from src.extract.schema_registry import SchemaRegistry

# --- Fake Claude API objects ---

@dataclass
class FakeTextBlock:
    type: str = "text"
    text: str = ""


@dataclass
class FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 50


@dataclass
class FakeResponse:
    content: list = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: FakeUsage = field(default_factory=FakeUsage)


class FakeMessages:
    """Mock for anthropic.Anthropic().messages."""

    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self._responses = list(responses or [])
        self._call_count = 0
        self.call_log: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        self.call_log.append(kwargs)
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            resp = FakeResponse(
                content=[FakeTextBlock(text="{}")],
                stop_reason="end_turn",
            )
        self._call_count += 1
        return resp


class FakeClaudeClient:
    """Mock for anthropic.Anthropic."""

    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.messages = FakeMessages(responses)


# --- Helper to build a classification response ---

def make_classification_response(
    doc_type: str = "invoice",
    confidence: float = 0.95,
    reasoning: str = "Test classification",
) -> FakeResponse:
    return FakeResponse(
        content=[FakeTextBlock(text=json.dumps({
            "doc_type": doc_type,
            "confidence": confidence,
            "reasoning": reasoning,
        }))],
    )


def make_extraction_response(fields: dict[str, Any]) -> FakeResponse:
    return FakeResponse(
        content=[FakeTextBlock(text=json.dumps(fields, ensure_ascii=False))],
    )


# --- Fixtures ---

@pytest.fixture
def schema_registry(tmp_path):
    """A SchemaRegistry with test schemas."""
    import yaml

    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()

    inv_fields = {
        "invoice_number": {
            "type": "string", "required": True, "description": "ID",
        },
        "vendor_name": {
            "type": "string", "required": True, "description": "Vendor",
        },
        "total_amount": {
            "type": "number", "required": True, "description": "Total",
        },
        "currency": {
            "type": "string", "required": False, "description": "Cur",
        },
    }
    invoice_schema = {
        "doc_type": "invoice",
        "description": "Invoice",
        "fields": inv_fields,
    }
    with open(schemas_dir / "invoice.yaml", "w") as f:
        yaml.dump(invoice_schema, f)

    tkt_fields = {
        "customer_name": {
            "type": "string", "required": True, "description": "Name",
        },
        "subject": {
            "type": "string", "required": True, "description": "Subj",
        },
        "category": {
            "type": "string", "required": True, "description": "Cat",
        },
        "priority": {
            "type": "string", "required": True, "description": "Pri",
        },
    }
    ticket_schema = {
        "doc_type": "support_ticket",
        "description": "Support ticket",
        "fields": tkt_fields,
    }
    with open(schemas_dir / "support_ticket.yaml", "w") as f:
        yaml.dump(ticket_schema, f)

    return SchemaRegistry(schemas_dir)


@pytest.fixture
def fake_classify_client():
    """A FakeClaudeClient that returns a classification response."""
    return FakeClaudeClient([make_classification_response()])


@pytest.fixture
def fake_extract_client():
    """A FakeClaudeClient that returns classification then extraction."""
    return FakeClaudeClient([
        make_classification_response("invoice", 0.95),
        make_extraction_response({
            "invoice_number": "INV-001",
            "vendor_name": "Test Corp",
            "total_amount": 100.0,
            "currency": "USD",
        }),
    ])
