"""Tests for the document classifier."""

from __future__ import annotations

import json

import pytest

from src.classify.classifier import Classifier
from tests.conftest import FakeClaudeClient, FakeResponse, FakeTextBlock


def _make_client(doc_type: str, confidence: float) -> FakeClaudeClient:
    return FakeClaudeClient([
        FakeResponse(content=[FakeTextBlock(text=json.dumps({
            "doc_type": doc_type,
            "confidence": confidence,
            "reasoning": "test",
        }))])
    ])


class TestClassifier:
    def test_classify_invoice(self):
        client = _make_client("invoice", 0.95)
        classifier = Classifier(client=client)
        result = classifier.classify("INVOICE\nInvoice Number: 123")

        assert result.doc_type == "invoice"
        assert result.confidence == 0.95

    def test_classify_ticket(self):
        client = _make_client("support_ticket", 0.88)
        classifier = Classifier(client=client)
        result = classifier.classify("Subject: Help needed")

        assert result.doc_type == "support_ticket"
        assert result.confidence == 0.88

    def test_classify_email(self):
        client = _make_client("email", 0.92)
        classifier = Classifier(client=client)
        result = classifier.classify("From: user@example.com\nSubject: Hello")

        assert result.doc_type == "email"
        assert result.confidence == 0.92

    def test_classify_sends_correct_system_prompt(self):
        client = _make_client("invoice", 0.9)
        classifier = Classifier(client=client, doc_types=["invoice", "email"])
        classifier.classify("test document")

        call = client.messages.call_log[0]
        assert "invoice" in call["system"]
        assert "email" in call["system"]

    def test_classify_handles_markdown_wrapped_json(self):
        inner = '{"doc_type": "invoice", "confidence": 0.9, "reasoning": "test"}'
        raw = f"```json\n{inner}\n```"
        client = FakeClaudeClient([
            FakeResponse(content=[FakeTextBlock(text=raw)])
        ])
        classifier = Classifier(client=client)
        result = classifier.classify("test")

        assert result.doc_type == "invoice"

    def test_classify_invalid_json_raises(self):
        client = FakeClaudeClient([
            FakeResponse(content=[FakeTextBlock(text="not json")])
        ])
        classifier = Classifier(client=client)

        with pytest.raises(json.JSONDecodeError):
            classifier.classify("test")
