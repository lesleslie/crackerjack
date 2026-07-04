"""L3 long-term rule extraction layer.

When L1 exhausts and L2 returns its no-op marker, the failure still has
value: we record it as a ``RuleRecord`` in an in-memory ``RuleStore`` so
future invocations of the same operation can match the error pattern to
a recovery hint via ``apply_rule``.

The store is in-memory only for v0. Dhara substrate (audit log table) is
currently ``sql_blocked``; persistent wiring follows once the substrate
unblocks. The store's API is intentionally small so swapping the backing
implementation later is mechanical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Pattern digest is capped so pathological error blobs don't bloat the store.
_MAX_PATTERN_LEN = 256


@dataclass(frozen=True)
class RuleRecord:
    """A single L3-extracted rule.

    Attributes:
        operation: the operation that failed (e.g. ``"git_push"``).
        pattern: a digest of the error message; used as the lookup key.
        recovery_hint: human-readable guidance for the next attempt.
    """

    operation: str
    pattern: str
    recovery_hint: str


@dataclass
class RuleStore:
    """In-memory rule store.

    Iteration order is insertion order. ``find_matching`` does a simple
    substring match (case-sensitive) on the recorded ``pattern`` field;
    richer matching (regex, embeddings) is a follow-up.
    """

    _rules: list[RuleRecord] = field(default_factory=list)

    def add(self, rule: RuleRecord) -> None:
        """Append a rule. Duplicates are kept (caller decides de-dupe policy)."""
        self._rules.append(rule)

    def all(self) -> list[RuleRecord]:
        """Return a snapshot of all rules in insertion order."""
        return list(self._rules)

    def find_matching(self, *, operation: str, error: str) -> list[RuleRecord]:
        """Return rules where ``operation`` matches AND ``pattern`` is a substring of ``error``."""
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
    """Build a RuleRecord from a failure.

    Strips surrounding whitespace and truncates the pattern digest to a
    reasonable length so very long error strings don't blow up the store.
    """
    pattern = (error or "").strip()
    if len(pattern) > _MAX_PATTERN_LEN:
        pattern = pattern[:_MAX_PATTERN_LEN]
    return RuleRecord(
        operation=(operation or "").strip(),
        pattern=pattern,
        recovery_hint=(hint or "").strip(),
    )


def record_rule(
    store: RuleStore,
    *,
    operation: str,
    error: str,
    recovery_hint: str,
) -> RuleRecord:
    """Build, append, and return a RuleRecord for a failed operation."""
    rec = extract_rule(operation=operation, error=error, hint=recovery_hint)
    store.add(rec)
    return rec


def apply_rule(
    store: RuleStore,
    *,
    operation: str,
    error: str,
) -> str | None:
    """Return the first matching recovery hint, or ``None`` if no rule matches."""
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


# Re-export Anything for callers passing opaque context blobs.
_ = Any