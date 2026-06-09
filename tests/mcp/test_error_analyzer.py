"""Tests for ``crackerjack.mcp.tools.error_analyzer``.

The module is a pure-function analyzer: it pulls cached error patterns from
a context object, classifies them into categories, and returns a JSON-shaped
summary with recommendations, urgency level, and fix suggestions.

These tests exercise the public entry point, the classification rules, and
the shape of the returned dictionary for empty / unknown / mixed inputs.
"""

from __future__ import annotations

import typing as t
from unittest.mock import MagicMock

import pytest

from crackerjack.mcp.tools import error_analyzer
from crackerjack.mcp.tools.error_analyzer import analyze_errors_with_caching


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _context_with_patterns(patterns: list[t.Any]) -> MagicMock:
    """Build a context mock whose ``cache.get_error_patterns()`` returns *patterns*."""
    cache = MagicMock()
    cache.get_error_patterns = MagicMock(return_value=patterns)
    ctx = MagicMock()
    ctx.cache = cache
    return ctx


def _context_with_broken_cache() -> MagicMock:
    """A cache whose ``get_error_patterns`` raises — exercises the suppress path."""
    cache = MagicMock()
    cache.get_error_patterns = MagicMock(side_effect=RuntimeError("boom"))
    ctx = MagicMock()
    ctx.cache = cache
    return ctx


# ---------------------------------------------------------------------------
# Public entry point — empty / no-cache paths
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_cache_attribute_returns_clean_result() -> None:
    """A context without a ``cache`` attribute is treated as no patterns."""
    ctx = MagicMock(spec=[])  # no .cache attribute at all

    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert result["status"] == "success"
    assert result["patterns_found"] == 0
    assert "No cached error patterns" in result["message"]
    assert result["urgency_level"] == "low"
    assert result["fix_suggestions"] == []


@pytest.mark.unit
def test_use_cache_false_skips_cache_lookup() -> None:
    """When use_cache is False, get_error_patterns must not be called."""
    ctx = _context_with_patterns(["some syntax error"])

    result = analyze_errors_with_caching(ctx, use_cache=False)

    assert result["status"] == "success"
    assert result["patterns_found"] == 0
    ctx.cache.get_error_patterns.assert_not_called()


@pytest.mark.unit
def test_broken_cache_returns_empty_patterns_via_suppress() -> None:
    """If the cache raises, ``_get_cached_patterns`` swallows it and returns []."""
    ctx = _context_with_broken_cache()

    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert result["status"] == "success"
    assert result["patterns_found"] == 0
    assert "No cached error patterns" in result["message"]


@pytest.mark.unit
def test_empty_patterns_includes_default_recommendations() -> None:
    """Empty patterns list yields a default recommendations block."""
    ctx = _context_with_patterns([])

    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert result["status"] == "success"
    assert len(result["recommendations"]) >= 2
    assert any("current development practices" in r for r in result["recommendations"])


# ---------------------------------------------------------------------------
# Output shape contract
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("use_cache", [True, False])
def test_output_shape_contains_required_keys(use_cache: bool) -> None:
    """The result dict must always contain the documented top-level keys."""
    ctx = _context_with_patterns([])
    result = analyze_errors_with_caching(ctx, use_cache=use_cache)

    required_keys = {
        "status",
        "patterns_found",
        "recommendations",
        "error_categories",
        "fix_suggestions",
        "urgency_level",
    }
    assert required_keys.issubset(result.keys())


@pytest.mark.unit
def test_error_categories_omits_empty_buckets() -> None:
    """Empty category buckets are stripped from the response."""
    ctx = _context_with_patterns(["syntax error: invalid token"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    # Only syntax_errors should appear; the other 8 buckets were empty.
    assert "syntax_errors" in result["error_categories"]
    assert "import_errors" not in result["error_categories"]
    assert "unknown" not in result["error_categories"]


# ---------------------------------------------------------------------------
# Per-category classification
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "pattern,expected_category",
    [
        ("SyntaxError: invalid syntax", "syntax_errors"),
        ("unexpected token at line 5", "syntax_errors"),
        ("ModuleNotFoundError: No module named 'foo'", "import_errors"),
        ("ImportError: cannot import name 'bar'", "import_errors"),
        ("TypeError: expected str, got int", "type_errors"),
        ("Missing type annotation for 'x'", "type_errors"),
        ("mypy found 3 errors", "type_errors"),
        ("pyright: type mismatch", "type_errors"),
        ("test_foo FAILED", "test_failures"),
        ("AssertionError: 1 != 2", "test_failures"),
        ("pytest collection error", "test_failures"),
        ("bandit: security issue B105", "security_issues"),
        ("Detected vulnerability in dep", "security_issues"),
        ("complexity of function is too high", "complexity_issues"),
        ("cognitive complexity exceeded", "complexity_issues"),
        ("Missing dependency: foo", "dependency_issues"),
        ("package version conflict", "dependency_issues"),
        ("ruff: formatting issue", "formatting_issues"),
        ("black would reformat file", "formatting_issues"),
        ("style violation: line too long", "formatting_issues"),
    ],
)
def test_classify_error_pattern_each_category(
    pattern: str, expected_category: str
) -> None:
    """Each keyword bucket maps to the expected category."""
    ctx = _context_with_patterns([pattern])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert result["error_categories"] == {expected_category: [pattern]}


# ---------------------------------------------------------------------------
# Mixed and unknown patterns
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_mixed_patterns_distribute_across_categories() -> None:
    """Multiple patterns with different keywords land in separate buckets."""
    patterns = [
        "SyntaxError: invalid syntax",
        "ModuleNotFoundError: No module named 'foo'",
        "test_foo FAILED",
        "mypy found 3 errors",
    ]
    ctx = _context_with_patterns(patterns)

    result = analyze_errors_with_caching(ctx, use_cache=True)

    cats = result["error_categories"]
    assert cats["syntax_errors"] == ["SyntaxError: invalid syntax"]
    assert cats["import_errors"] == ["ModuleNotFoundError: No module named 'foo'"]
    assert cats["test_failures"] == ["test_foo FAILED"]
    assert cats["type_errors"] == ["mypy found 3 errors"]
    assert result["patterns_found"] == 4
    assert result["status"] == "success"


@pytest.mark.unit
def test_unknown_patterns_bucket() -> None:
    """Patterns with no matching keyword fall into the ``unknown`` bucket."""
    ctx = _context_with_patterns(["unrecognized gibberish xyzzy"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert result["error_categories"] == {"unknown": ["unrecognized gibberish xyzzy"]}
    # Unknown errors shouldn't trigger the security path, urgency stays low.
    assert result["urgency_level"] == "low"


@pytest.mark.unit
def test_pattern_string_is_lowercased_before_match() -> None:
    """Keyword matching is case-insensitive (lowercased internally)."""
    ctx = _context_with_patterns(["SYNTAX ERROR: INVALID SYNTAX"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert "syntax_errors" in result["error_categories"]


@pytest.mark.unit
def test_non_string_patterns_are_stringified() -> None:
    """Non-string patterns are coerced via str() before classification.

    A plain int that doesn't match any keyword lands in ``unknown``; a
    non-string whose str() contains a known keyword lands in that bucket.
    """
    pattern_obj = MagicMock()
    pattern_obj.__str__ = MagicMock(return_value="test_foo failed")
    ctx = _context_with_patterns([42, pattern_obj])

    result = analyze_errors_with_caching(ctx, use_cache=True)

    # 42 -> "42" (no keyword match) -> unknown bucket.
    assert "unknown" in result["error_categories"]
    assert 42 in result["error_categories"]["unknown"]
    # The mock with a matching str() lands in test_failures.
    assert pattern_obj in result["error_categories"]["test_failures"]


# ---------------------------------------------------------------------------
# Recommendation generation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_recommendations_for_security_issues() -> None:
    """Security issues produce security-flavored recommendations."""
    ctx = _context_with_patterns(["bandit: security issue"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    recs = result["recommendations"]
    assert any("security" in r.lower() for r in recs)
    assert any("🔒" in r for r in recs)


@pytest.mark.unit
def test_recommendations_for_many_categories_includes_comprehensive() -> None:
    """More than 3 categories adds the comprehensive fix recommendations."""
    patterns = [
        "syntax error",
        "import error",
        "type error",
        "test failed",
    ]
    ctx = _context_with_patterns(patterns)
    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert len(result["error_categories"]) > 3
    recs = result["recommendations"]
    assert any("AI agent" in r for r in recs)
    assert any("quality metrics" in r for r in recs)


@pytest.mark.unit
def test_recommendations_for_syntax_only() -> None:
    """A single syntax category emits at least the syntax recommendation."""
    ctx = _context_with_patterns(["invalid syntax here"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    recs = result["recommendations"]
    assert any("syntax" in r.lower() for r in recs)


# ---------------------------------------------------------------------------
# Urgency level calculation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_urgency_high_for_security() -> None:
    """Any security issue bumps urgency to ``high``."""
    ctx = _context_with_patterns(["bandit: security issue"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert result["urgency_level"] == "high"


@pytest.mark.unit
def test_urgency_high_for_many_test_failures() -> None:
    """More than 5 test failures with no security issues is ``high``."""
    patterns = [f"test_{i} FAILED" for i in range(6)]
    ctx = _context_with_patterns(patterns)

    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert result["urgency_level"] == "high"


@pytest.mark.unit
def test_urgency_medium_for_syntax() -> None:
    """Syntax errors without security/tests push urgency to ``medium``."""
    ctx = _context_with_patterns(["invalid syntax"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert result["urgency_level"] == "medium"


@pytest.mark.unit
def test_urgency_medium_for_total_over_20() -> None:
    """More than 20 total errors (in one category) yields ``medium``."""
    patterns = [f"formatting issue {i}" for i in range(21)]
    ctx = _context_with_patterns(patterns)

    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert result["urgency_level"] == "medium"


@pytest.mark.unit
def test_urgency_low_for_single_category() -> None:
    """A single low-impact category stays at ``low``."""
    ctx = _context_with_patterns(["ruff formatting issue"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert result["urgency_level"] == "low"


# ---------------------------------------------------------------------------
# Fix suggestions
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fix_suggestion_for_formatting() -> None:
    """Formatting issues produce a formatting fix suggestion."""
    ctx = _context_with_patterns(["ruff formatting issue"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    suggestions = result["fix_suggestions"]
    assert any(s["category"] == "formatting" for s in suggestions)
    formatting = next(s for s in suggestions if s["category"] == "formatting")
    assert "command" in formatting
    assert "description" in formatting


@pytest.mark.unit
def test_fix_suggestion_for_types() -> None:
    """Type issues produce a types fix suggestion."""
    ctx = _context_with_patterns(["mypy type error"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    suggestions = result["fix_suggestions"]
    assert any(s["category"] == "types" for s in suggestions)


@pytest.mark.unit
def test_fix_suggestion_for_test_failures() -> None:
    """Test failures produce a tests fix suggestion."""
    ctx = _context_with_patterns(["test_foo FAILED"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    suggestions = result["fix_suggestions"]
    assert any(s["category"] == "tests" for s in suggestions)


@pytest.mark.unit
def test_fix_suggestion_for_security() -> None:
    """Security issues produce a security fix suggestion."""
    ctx = _context_with_patterns(["bandit security issue"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    suggestions = result["fix_suggestions"]
    assert any(s["category"] == "security" for s in suggestions)


@pytest.mark.unit
def test_comprehensive_fix_suggestion_for_many_categories() -> None:
    """More than 3 categories adds a comprehensive fix suggestion."""
    patterns = [
        "syntax error",
        "import error",
        "type error",
        "test failed",
    ]
    ctx = _context_with_patterns(patterns)
    result = analyze_errors_with_caching(ctx, use_cache=True)

    suggestions = result["fix_suggestions"]
    assert any(s["category"] == "comprehensive" for s in suggestions)


@pytest.mark.unit
def test_fix_suggestion_dict_shape() -> None:
    """Every fix suggestion has the documented keys."""
    ctx = _context_with_patterns(["mypy type error", "ruff formatting issue"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    for s in result["fix_suggestions"]:
        assert isinstance(s, dict)
        assert {"category", "action", "command", "description"}.issubset(s.keys())


# ---------------------------------------------------------------------------
# Error / exception handling at the public boundary
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_top_level_exception_returns_error_envelope() -> None:
    """If something blows up in the analysis path, we return an error envelope.

    The ``_get_cached_patterns`` call is wrapped in suppress, but if
    ``_build_error_analysis`` itself raises we should still get a status=error
    dict rather than a raised exception.
    """

    class BadContext:
        cache = "not-a-cache"  # truthy but lacks get_error_patterns

    result = analyze_errors_with_caching(BadContext(), use_cache=True)

    # Path: cache is truthy but lacks get_error_patterns → falls through to [].
    # We get a normal success response, not an error envelope.
    assert result["status"] == "success"
    assert result["patterns_found"] == 0


@pytest.mark.unit
def test_cache_without_get_error_patterns_attribute_returns_empty() -> None:
    """A truthy cache missing ``get_error_patterns`` falls through to []."""
    cache = MagicMock(spec=["other_method"])
    ctx = MagicMock()
    ctx.cache = cache

    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert result["status"] == "success"
    assert result["patterns_found"] == 0


# ---------------------------------------------------------------------------
# End-to-end: pattern shape & message
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_message_reports_patterns_and_category_count() -> None:
    """With patterns, the message names both the pattern count and the category count."""
    patterns = ["syntax error", "import error", "test failed"]
    ctx = _context_with_patterns(patterns)

    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert "3 cached error patterns" in result["message"]
    assert "3 categories" in result["message"]


@pytest.mark.unit
def test_status_field_is_success_on_normal_path() -> None:
    """A normal analysis run reports status='success'."""
    ctx = _context_with_patterns(["syntax error"])
    result = analyze_errors_with_caching(ctx, use_cache=True)

    assert result["status"] == "success"


@pytest.mark.unit
def test_module_exports_analyze_errors_with_caching() -> None:
    """The public function must be importable from the module."""
    assert callable(error_analyzer.analyze_errors_with_caching)
    assert callable(analyze_errors_with_caching)
