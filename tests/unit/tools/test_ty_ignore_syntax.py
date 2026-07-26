from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

import crackerjack.tools.ty_ignore_syntax as _ty_ignore

DECISION_FILE = Path(
    os.environ.get(
        "CRACKERJACK_TY_IGNORE_DECISION_FILE",
        "/Users/les/Projects/mahavishnu/.claude/decisions/ty-ignore-codes.md",
    ),
)
DECISION_RULE_PATTERN = re.compile(
    r"^## Decision rule\s*\n(?P<body>.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)
TY_IGNORE_CODE_PATTERN = re.compile(
    r"#\s*ty:\s*ignore\[([a-zA-Z0-9_,\- ]+)\]",
)


def _decision_rule_codes() -> set[str]:
    """Extract ty diagnostic codes from the canonical decision rule."""
    if not DECISION_FILE.is_file():
        pytest.fail(f"Canonical ty ignore-code decision file is missing: {DECISION_FILE}")

    decision_text = DECISION_FILE.read_text(encoding="utf-8")
    decision_rule = DECISION_RULE_PATTERN.search(decision_text)
    if decision_rule is None:
        pytest.fail(f"Canonical decision file has no Decision rule section: {DECISION_FILE}")

    return {
        code.strip()
        for raw_codes in TY_IGNORE_CODE_PATTERN.findall(decision_rule.group("body"))
        for code in raw_codes.split(",")
        if code.strip()
    }


def _diff_sets(left: set[str], right: set[str]) -> tuple[list[str], list[str]]:
    return sorted(left - right), sorted(right - left)


def test_known_ty_codes_match_decision_file() -> None:
    """Keep the hook's accepted ty codes synchronized with the policy."""
    decision_codes = _decision_rule_codes()
    known_codes = set(_ty_ignore.KNOWN_TY_CODES)
    only_in_decision, only_in_known = _diff_sets(decision_codes, known_codes)

    assert decision_codes == known_codes, (
        "KNOWN_TY_CODES drifted from the canonical ty-ignore decision file.\n"
        f"Decision file: {DECISION_FILE}\n"
        f"Only in decision file: {only_in_decision}\n"
        f"Only in KNOWN_TY_CODES: {only_in_known}"
    )


def test_sync_check_detects_extra_code_in_hook(monkeypatch) -> None:
    """Regression: prove the sync check fails when the hook accepts extra codes."""
    baseline = set(_ty_ignore.KNOWN_TY_CODES)
    fake_hook_codes = baseline | {"foo-suppression"}
    monkeypatch.setattr(_ty_ignore, "KNOWN_TY_CODES", frozenset(fake_hook_codes))

    decision_codes = _decision_rule_codes()
    known_codes = set(_ty_ignore.KNOWN_TY_CODES)
    only_in_decision, only_in_known = _diff_sets(decision_codes, known_codes)

    # Drift must be reported (whatever the baseline state is) and the injected
    # code must show up on the "only in KNOWN_TY_CODES" side.
    assert decision_codes != known_codes
    assert "foo-suppression" in only_in_known
    assert "foo-suppression" not in only_in_decision


def test_sync_check_detects_missing_code_in_hook(monkeypatch) -> None:
    """Regression: prove the sync check fails when the hook drops a sanctioned code."""
    baseline = set(_ty_ignore.KNOWN_TY_CODES)
    decision_codes = _decision_rule_codes()
    # Pick a code present in both baseline and decision file so the regression
    # assertion stays valid even if the baseline has other drift.
    target_drop = next(iter(baseline & decision_codes))
    fake_hook_codes = baseline - {target_drop}
    monkeypatch.setattr(_ty_ignore, "KNOWN_TY_CODES", frozenset(fake_hook_codes))

    known_codes = set(_ty_ignore.KNOWN_TY_CODES)
    only_in_decision, only_in_known = _diff_sets(decision_codes, known_codes)

    # Drift must be reported and the dropped code must show up on the
    # "only in decision file" side.
    assert decision_codes != known_codes
    assert target_drop in only_in_decision
    assert target_drop not in only_in_known
