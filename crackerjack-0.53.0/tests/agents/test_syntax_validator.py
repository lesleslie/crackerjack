"""
Tests for SyntaxValidator.

Test AST-based syntax validation.
"""
import pytest

from crackerjack.agents.syntax_validator import SyntaxValidator, ValidationResult


class TestSyntaxValidator:
    """Test suite for SyntaxValidator."""

    @pytest.mark.asyncio
    async def test_valid_code_passes(self) -> None:
        """Test that valid Python code passes validation."""
        validator = SyntaxValidator()
        code = """
def hello():
    print("Hello, world!")

class Foo:
    def method(self):
        pass
"""
        result = await validator.validate(code)

        assert result.valid is True
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_syntax_error_detected(self) -> None:
        """Test that syntax errors are detected."""
        validator = SyntaxValidator()
        code = """
def broken(
    print("Missing closing paren")
"""
        result = await validator.validate(code)

        assert result.valid is False
        assert len(result.errors) == 1
        assert "Syntax error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_unclosed_parenthesis(self) -> None:
        """Test detection of unclosed parenthesis."""
        validator = SyntaxValidator()

        warnings = validator.validate_incomplete_code("def foo(:")
        errors = await validator.validate("def foo(")

        assert "unclosed parenthesis" in warnings[0]
        assert errors.valid is False

    @pytest.mark.asyncio
    async def test_unclosed_braces(self) -> None:
        """Test detection of unclosed braces."""
        validator = SyntaxValidator()

        warnings = validator.validate_incomplete_code("dict = {")
        errors = await validator.validate("dict = {")

        assert "unclosed braces" in warnings[0]
        assert errors.valid is False

    @pytest.mark.asyncio
    async def test_unclosed_square_brackets(self) -> None:
        """Test detection of unclosed square brackets."""
        validator = SyntaxValidator()

        warnings = validator.validate_incomplete_code("arr = [")
        errors = await validator.validate("arr = [")

        assert "unclosed square brackets" in warnings[0]
        assert errors.valid is False

    @pytest.mark.asyncio
    async def test_multiple_unclosed_brackets(self) -> None:
        """Test detection of multiple unclosed brackets."""
        validator = SyntaxValidator()

        warnings = validator.validate_incomplete_code("def foo(]:")
        assert any("unclosed" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_result_bool_conversion(self) -> None:
        """Test that ValidationResult converts to bool correctly."""
        valid_result = ValidationResult(valid=True, errors=[])
        invalid_result = ValidationResult(valid=False, errors=["error"])

        assert valid_result.valid is True
        assert invalid_result.valid is False
        assert bool(valid_result) is True
        assert bool(invalid_result) is False

    @pytest.mark.asyncio
    async def test_merge_results(self) -> None:
        """Test merging two validation results."""
        result1 = ValidationResult(valid=True, errors=["error1"])
        result2 = ValidationResult(valid=False, errors=["error2"])

        merged = result1.merge(result2)

        assert merged.valid is False  # AND of valid flags
        assert merged.errors == ["error1", "error2"]
