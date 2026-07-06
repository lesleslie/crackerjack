"""Tests for ``crackerjack.tools.ty_classify``.

The classifier reads ty concise output and groups errors by which
auto-fix tier should handle them:

    tier 1: mechanical fix (ty_cleanup, ty_imports, future narrow-helper)
    tier 2: one-shot LLM (TypeErrorSpecialistAgent)
    tier 3: iterative CLI session (IterativeFixAgent)
    tier 4: human review queue

The classification is intentionally rule-based (no LLM) so it can run
as a fast pre-flight report before any expensive dispatch.
"""

from __future__ import annotations

from pathlib import Path

from crackerjack.tools.ty_classify import (
    TIER_1_MECHANICAL,
    TIER_3_ITERATIVE,
    TIER_4_HUMAN,
    classify_code,
    classify_diagnostics,
)

# ---------------------------------------------------------------------------
# classify_code: pure rule for one error code
# ---------------------------------------------------------------------------


class TestClassifyCode:
    """One ty error code → one tier. Stable mapping."""

    def test_unused_type_ignore_is_tier_1(self) -> None:
        # ty_cleanup.py already handles this mechanically.
        assert classify_code("unused-type-ignore-comment") == TIER_1_MECHANICAL

    def test_redundant_cast_is_tier_1(self) -> None:
        # ty_cleanup.py already handles this mechanically.
        assert classify_code("redundant-cast") == TIER_1_MECHANICAL

    def test_unresolved_reference_is_tier_1(self) -> None:
        # ty_imports.py (NEW) handles the resolvable cases mechanically.
        # Unresolvable sub-cases flow to tier 2 — but the *classification*
        # of the error code itself is tier 1.
        assert classify_code("unresolved-reference") == TIER_1_MECHANICAL

    def test_unsupported_operator_is_tier_1(self) -> None:
        # int + None, etc. — ``ty_narrow`` handles the `in` / `not in`
        # cases mechanically. The rest still fall through to tier 3.
        assert classify_code("unsupported-operator") == TIER_1_MECHANICAL

    def test_unresolved_attribute_is_tier_3(self) -> None:
        # Union attribute access — needs isinstance narrowing, multi-step.
        assert classify_code("unresolved-attribute") == TIER_3_ITERATIVE

    def test_invalid_argument_type_is_tier_3(self) -> None:
        # Passing T | None where T required — needs None-check insertion.
        assert classify_code("invalid-argument-type") == TIER_3_ITERATIVE

    def test_invalid_method_override_is_tier_4(self) -> None:
        # Subclass method signature drift — design decision; human review.
        assert classify_code("invalid-method-override") == TIER_4_HUMAN

    def test_unknown_code_defaults_to_tier_3(self) -> None:
        # Conservative default: when we don't know the code, send it to the
        # iterative agent rather than pretending we can fix it.
        assert classify_code("some-future-ty-code") == TIER_3_ITERATIVE


# ---------------------------------------------------------------------------
# classify_diagnostics: full ty output → tier buckets
# ---------------------------------------------------------------------------


class TestClassifyDiagnostics:
    """End-to-end: parse ty output lines, return a tier report."""

    def test_buckets_errors_by_tier(self) -> None:
        lines = [
            "tests/a.py:1:1: error[unused-type-ignore-comment] Unused blanket `type: ignore` directive",
            "tests/a.py:2:1: error[redundant-cast] Redundant cast",
            "tests/a.py:3:1: error[unresolved-reference] Name `time` used when not defined",
            "tests/a.py:4:1: error[unsupported-operator] Operator `+` not supported for types `int | None` and `int`",
            "tests/a.py:5:1: error[unresolved-attribute] Attribute `lower` is not defined on `None`",
            "tests/a.py:6:1: error[invalid-method-override] Signature mismatch",
        ]
        report = classify_diagnostics(lines)
        assert (
            report.tier_1 == 4
        )  # ignore + cast + unresolved-ref + unsupported-operator
        assert report.tier_2 == 0
        assert report.tier_3 == 1  # unresolved-attribute
        assert report.tier_4 == 1  # invalid-method-override
        assert report.total == 6

    def test_ignores_non_error_lines(self) -> None:
        lines = [
            "Some other ty output that isn't an error line",
            "",
            "tests/a.py:1:1: error[unused-type-ignore-comment] Unused",
        ]
        report = classify_diagnostics(lines)
        assert report.total == 1
        assert report.tier_1 == 1

    def test_top_offenders_by_file(self) -> None:
        # The classifier should also surface "which files have the most
        # errors" — that's where the dashboard / tier-3 agent should focus.
        lines = (
            [
                f"tests/file_a.py:{i}:1: error[unsupported-operator] msg"
                for i in range(5)
            ]
            + [
                f"tests/file_b.py:{i}:1: error[unsupported-operator] msg"
                for i in range(3)
            ]
            + [
                "tests/file_c.py:1:1: error[unused-type-ignore-comment] msg",
            ]
        )
        report = classify_diagnostics(lines)
        top = report.top_files(limit=2)
        assert len(top) == 2
        assert top[0].path == Path("tests/file_a.py")
        assert top[0].count == 5
        assert top[1].path == Path("tests/file_b.py")
        assert top[1].count == 3

    def test_top_files_dedupes_codes_per_file(self) -> None:
        # If file_a has 5 unsupported-operator + 3 unresolved-attribute, the
        # count should be 8 total, not bucketed by code.
        lines = [
            f"tests/file_a.py:{i}:1: error[unsupported-operator] msg" for i in range(5)
        ] + [
            f"tests/file_a.py:{i + 10}:1: error[unresolved-attribute] msg"
            for i in range(3)
        ]
        report = classify_diagnostics(lines)
        top = report.top_files(limit=1)
        assert top[0].count == 8


# ---------------------------------------------------------------------------
# Human-readable report rendering
# ---------------------------------------------------------------------------


class TestReportRender:
    def test_render_includes_all_tiers(self) -> None:
        lines = [
            "tests/a.py:1:1: error[unused-type-ignore-comment] Unused",
            "tests/a.py:2:1: error[unsupported-operator] Bad",
        ]
        report = classify_diagnostics(lines)
        text = report.render()
        assert "Total: 2" in text
        assert "Tier 1" in text
        assert "Tier 3" in text
        # Coverage estimate should appear
        assert "%" in text
