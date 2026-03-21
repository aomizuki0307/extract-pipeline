"""Tests for the schema-driven extractor."""

from __future__ import annotations

import json

import pytest

from src.extract.extractor import Extractor
from tests.conftest import FakeClaudeClient, FakeResponse, FakeTextBlock


class TestExtractor:
    def test_extract_invoice_fields(self, schema_registry):
        fields = {
            "invoice_number": "INV-001",
            "vendor_name": "Test Corp",
            "total_amount": 500.0,
            "currency": "USD",
        }
        client = FakeClaudeClient([
            FakeResponse(content=[FakeTextBlock(text=json.dumps(fields))])
        ])
        extractor = Extractor(client=client, schema_registry=schema_registry)
        result = extractor.extract("Invoice #INV-001...", "invoice")

        assert result.doc_type == "invoice"
        assert result.fields["invoice_number"] == "INV-001"
        assert result.fields["total_amount"] == 500.0

    def test_extract_includes_schema_in_prompt(self, schema_registry):
        raw = json.dumps({
            "invoice_number": "X",
            "vendor_name": "Y",
            "total_amount": 1,
        })
        client = FakeClaudeClient([
            FakeResponse(content=[FakeTextBlock(text=raw)])
        ])
        extractor = Extractor(client=client, schema_registry=schema_registry)
        extractor.extract("test", "invoice")

        call = client.messages.call_log[0]
        assert "invoice_number" in call["system"]
        assert "vendor_name" in call["system"]

    def test_extract_retries_on_json_error(self, schema_registry):
        client = FakeClaudeClient([
            FakeResponse(content=[FakeTextBlock(text="not json")]),
            FakeResponse(content=[FakeTextBlock(text=json.dumps({
                "invoice_number": "X",
                "vendor_name": "Y",
                "total_amount": 1,
            }))]),
        ])
        extractor = Extractor(
            client=client, schema_registry=schema_registry, max_retries=2,
        )
        result = extractor.extract("test", "invoice")

        assert result.fields["invoice_number"] == "X"
        assert len(client.messages.call_log) == 2

    def test_extract_raises_after_max_retries(self, schema_registry):
        client = FakeClaudeClient([
            FakeResponse(content=[FakeTextBlock(text="bad")]),
            FakeResponse(content=[FakeTextBlock(text="bad")]),
            FakeResponse(content=[FakeTextBlock(text="bad")]),
        ])
        extractor = Extractor(
            client=client, schema_registry=schema_registry, max_retries=2,
        )

        with pytest.raises(ValueError, match="Failed to extract"):
            extractor.extract("test", "invoice")

    def test_extract_handles_markdown_wrapped_json(self, schema_registry):
        inner = '{"invoice_number": "X", "vendor_name": "Y", "total_amount": 1}'
        raw = f"```json\n{inner}\n```"
        client = FakeClaudeClient([
            FakeResponse(content=[FakeTextBlock(text=raw)])
        ])
        extractor = Extractor(client=client, schema_registry=schema_registry)
        result = extractor.extract("test", "invoice")

        assert result.fields["invoice_number"] == "X"
