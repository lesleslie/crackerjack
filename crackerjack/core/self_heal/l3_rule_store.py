from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_MAX_PATTERN_LEN = 256


@dataclass(frozen=True)
class RuleRecord:
    operation: str
    pattern: str
    recovery_hint: str


@dataclass
class RuleStore:
    _rules: list[RuleRecord] = field(default_factory=list)

    def add(self, rule: RuleRecord) -> None:
        self._rules.append(rule)

    def all(self) -> list[RuleRecord]:
        return self._rules.copy()

    def find_matching(self, *, operation: str, error: str) -> list[RuleRecord]:
        return [
            r
            for r in self._rules
            if r.operation == operation and r.pattern and r.pattern in error
        ]


def extract_rule(
    *,
    operation: str,
    error: str,
    hint: str,
) -> RuleRecord:
    pattern = error.strip()
    if len(pattern) > _MAX_PATTERN_LEN:
        pattern = pattern[:_MAX_PATTERN_LEN]
    return RuleRecord(
        operation=operation.strip(),
        pattern=pattern,
        recovery_hint=hint.strip(),
    )


def record_rule(
    store: RuleStore,
    *,
    operation: str,
    error: str,
    recovery_hint: str,
) -> RuleRecord:
    rec = extract_rule(operation=operation, error=error, hint=recovery_hint)
    store.add(rec)
    return rec


def apply_rule(
    store: RuleStore,
    *,
    operation: str,
    error: str,
) -> str | None:
    matches = store.find_matching(operation=operation, error=error)
    if not matches:
        return None
    return matches[0].recovery_hint


__all__ = [
    "RuleRecord",
    "RuleStore",
    "apply_rule",
    "extract_rule",
    "record_rule",
]


_ = Any
