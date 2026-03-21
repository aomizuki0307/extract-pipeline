"""Tests for the output validator."""

from __future__ import annotations

from src.validate.output_validator import OutputValidator


class TestOutputValidator:
    def test_valid_invoice(self, schema_registry):
        validator = OutputValidator(schema_registry)
        result = validator.validate(
            {
                "invoice_number": "INV-001",
                "vendor_name": "Test Corp",
                "total_amount": 100.0,
            },
            "invoice",
        )
        assert result.is_valid

    def test_missing_required_field(self, schema_registry):
        validator = OutputValidator(schema_registry)
        result = validator.validate(
            {"invoice_number": "INV-001"},
            "invoice",
        )
        assert not result.is_valid
        missing = [i for i in result.issues if "missing" in i.issue.lower()]
        assert len(missing) >= 1

    def test_extra_field_warning(self, schema_registry):
        validator = OutputValidator(schema_registry)
        result = validator.validate(
            {
                "invoice_number": "INV-001",
                "vendor_name": "Test Corp",
                "total_amount": 100.0,
                "extra_field": "should warn",
            },
            "invoice",
        )
        warnings = [i for i in result.issues if i.severity == "warning"]
        assert len(warnings) >= 1
        assert any("extra_field" in w.issue for w in warnings)

    def test_optional_field_not_required(self, schema_registry):
        validator = OutputValidator(schema_registry)
        result = validator.validate(
            {
                "invoice_number": "INV-001",
                "vendor_name": "Test Corp",
                "total_amount": 100.0,
                # currency is optional — not provided
            },
            "invoice",
        )
        assert result.is_valid

    def test_validated_data_returned(self, schema_registry):
        validator = OutputValidator(schema_registry)
        result = validator.validate(
            {
                "invoice_number": "INV-001",
                "vendor_name": "Test Corp",
                "total_amount": 100.0,
            },
            "invoice",
        )
        assert result.validated_data["invoice_number"] == "INV-001"
