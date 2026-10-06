"""Tests for Veyra Boundary Argument Validator & Normalizer."""

import pytest
from veyra.boundary.validator import (
    SchemaValidationError,
    normalize_iso_date,
    normalize_value,
    validate_and_normalize,
)


class TestValueNormalization:
    def test_integer_normalization(self):
        assert normalize_value("42", "int") == 42
        assert normalize_value("-10", int) == -10
        assert normalize_value(42, int) == 42
        assert normalize_value(42.0, int) == 42

        # Invalid integers must fail strictly
        with pytest.raises(SchemaValidationError):
            normalize_value("42.5", int)
        with pytest.raises(SchemaValidationError):
            normalize_value("not_a_number", int)

    def test_float_normalization(self):
        assert normalize_value("42.5", "float") == 42.5
        assert normalize_value("100", float) == 100.0
        assert normalize_value(42.5, float) == 42.5

        with pytest.raises(SchemaValidationError):
            normalize_value("invalid", float)

    def test_boolean_normalization(self):
        assert normalize_value("true", bool) is True
        assert normalize_value("True", "boolean") is True
        assert normalize_value("1", bool) is True
        assert normalize_value("false", bool) is False
        assert normalize_value("0", bool) is False
        assert normalize_value(True, bool) is True
        assert normalize_value(False, bool) is False

        with pytest.raises(SchemaValidationError):
            normalize_value("maybe", bool)

    def test_enum_normalization(self):
        allowed = ["active", "suspended", "archived"]
        assert normalize_value("ACTIVE", str, allowed_enums=allowed) == "active"
        assert normalize_value("suspended", str, allowed_enums=allowed) == "suspended"
        assert normalize_value("  Archived  ", str, allowed_enums=allowed) == "archived"

        with pytest.raises(SchemaValidationError):
            normalize_value("deleted", str, allowed_enums=allowed)

    def test_date_normalization(self):
        assert normalize_iso_date("2026/10/06") == "2026-10-06"
        assert normalize_iso_date("2026-10-06T14:30:00Z") == "2026-10-06"
        assert normalize_iso_date("  2026-10-06  ") == "2026-10-06"


class TestSchemaValidation:
    def test_json_schema_validation_and_coercion(self):
        schema = {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "status": {"type": "string", "enum": ["pending", "approved", "rejected"]},
                "start_date": {"type": "string", "format": "date"},
            },
            "required": ["customer_id", "status"],
            "additionalProperties": False,
        }

        raw_args = {
            "customer_id": "1052",
            "status": "APPROVED",
            "start_date": "2026/10/06",
            "hallucinated_param": "should_be_dropped",
        }

        normalized, corrections = validate_and_normalize(raw_args, schema=schema)

        assert normalized["customer_id"] == 1052
        assert normalized["status"] == "approved"
        assert normalized["start_date"] == "2026-10-06"
        assert "hallucinated_param" not in normalized
        assert len(corrections) >= 3

    def test_missing_required_argument_raises(self):
        schema = {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        }
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_and_normalize({}, schema=schema)
        assert exc_info.value.field == "id"

    def test_function_signature_validation(self):
        def transfer_funds(account_id: int, amount: float, memo: str = ""):
            return True

        raw_args = {
            "account_id": "9921",
            "amount": "250.75",
            "memo": "  payment for invoice  ",
            "extra_junk": 123,
        }

        normalized, corrections = validate_and_normalize(raw_args, fn=transfer_funds)

        assert normalized["account_id"] == 9921
        assert normalized["amount"] == 250.75
        assert normalized["memo"] == "payment for invoice"
        assert "extra_junk" not in normalized
