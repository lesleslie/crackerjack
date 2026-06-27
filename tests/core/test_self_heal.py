"""Tests for the three-layer self-heal protocol (L1/L2/L3).

Spec #4: three-layer-self-heal (Phase 2).
- L1 = transient retry with exponential backoff (3 attempts).
- L2 = no-op stub (already fixed in C4). Regression test ensures it returns
  the no-op outcome without invoking a real Claude session.
- L3 = long-term rule extraction. A failed operation contributes a rule to a
  rule-store and returns the rule.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from crackerjack.core.self_heal import (
    L1Exhausted,
    L1Retry,
    L2Noop,
    RuleRecord,
    RuleStore,
    apply_rule,
    extract_rule,
    l1_retry,
    l2_noop,
    record_rule,
    retry_with_backoff,
)


# ---------------------------------------------------------------------------
# L1 — transient retry with exponential backoff
# ---------------------------------------------------------------------------


class TestL1Retry:
    """L1 retries a transient operation up to 3 times with exponential backoff."""

    async def test_returns_first_success_without_retry(self) -> None:
        calls: list[int] = []

        async def op() -> str:
            calls.append(1)
            return "ok"

        result = await retry_with_backoff(op, max_attempts=3, base_delay=0.0)
        assert result == "ok"
        assert len(calls) == 1

    async def test_retries_until_success(self) -> None:
        calls: list[int] = []

        async def op() -> str:
            calls.append(1)
            if len(calls) < 3:
                raise RuntimeError("transient")
            return "recovered"

        result = await retry_with_backoff(op, max_attempts=3, base_delay=0.0)
        assert result == "recovered"
        assert len(calls) == 3

    async def test_raises_l1_exhausted_after_max_attempts(self) -> None:
        calls: list[int] = []

        async def op() -> str:
            calls.append(1)
            raise RuntimeError("always fails")

        with pytest.raises(L1Exhausted) as exc:
            await retry_with_backoff(op, max_attempts=3, base_delay=0.0)
        assert len(calls) == 3
        assert "RuntimeError" in str(exc.value)
        assert "always fails" in str(exc.value)

    async def test_exponential_backoff_uses_attempt_index(self) -> None:
        """Backoff delay scales with attempt index (attempt * base_delay * factor)."""
        seen_delays: list[float] = []

        async def fake_sleep(delay: float) -> None:
            seen_delays.append(delay)

        async def op() -> str:
            raise RuntimeError("fail")

        with pytest.raises(L1Exhausted):
            await retry_with_backoff(
                op,
                max_attempts=3,
                base_delay=0.5,
                backoff_factor=2.0,
                sleep=fake_sleep,
            )
        # 3 attempts => 2 sleeps (after attempt 1 and after attempt 2).
        # Delays: base_delay * factor**(attempt-1)
        # attempt 1 -> 0.5 * 1 = 0.5; attempt 2 -> 0.5 * 2 = 1.0
        assert seen_delays == [0.5, 1.0]

    async def test_does_not_sleep_after_final_attempt(self) -> None:
        seen_delays: list[float] = []

        async def fake_sleep(delay: float) -> None:
            seen_delays.append(delay)

        async def op() -> str:
            raise RuntimeError("fail")

        with pytest.raises(L1Exhausted):
            await retry_with_backoff(
                op,
                max_attempts=3,
                base_delay=1.0,
                sleep=fake_sleep,
            )
        # After the final (3rd) failure we do not sleep. Only 2 sleeps total.
        assert len(seen_delays) == 2

    async def test_l1_retry_helper_alias(self) -> None:
        """l1_retry() is the public alias for retry_with_backoff."""

        async def op() -> int:
            return 42

        assert await l1_retry(op, max_attempts=3, base_delay=0.0) == 42
        assert l1_retry is retry_with_backoff

    def test_l1_retry_dataclass_carries_attempt_count(self) -> None:
        rec = L1Retry(operation="git_push", attempts=3, last_error="boom")
        assert rec.operation == "git_push"
        assert rec.attempts == 3
        assert rec.last_error == "boom"


# ---------------------------------------------------------------------------
# L2 — no-op stub (regression for C4 fix)
# ---------------------------------------------------------------------------


class TestL2Noop:
    """L2 is a no-op stub. It must not invoke Claude and must not retry."""

    async def test_returns_noop_marker(self) -> None:
        outcome = await l2_noop(operation="git_push", l1_context={"branch": "main"})
        assert outcome == "noop_recovery"

    async def test_does_not_call_claude(self) -> None:
        """No real Claude session is invoked. Capture call_count via a guard."""
        call_count = 0

        async def fake_claude(*args: Any, **kwargs: Any) -> tuple[str, int]:
            nonlocal call_count
            call_count += 1
            return ("fake", 100)

        outcome = await l2_noop(
            operation="git_push",
            l1_context={},
            claude_turn=fake_claude,  # type: ignore[arg-type]
        )
        assert outcome == "noop_recovery"
        assert call_count == 0  # stub must NOT call into the optional claude_turn

    def test_l2_noop_constant_marker(self) -> None:
        assert L2Noop.MARKER == "noop_recovery"


# ---------------------------------------------------------------------------
# L3 — long-term rule extraction
# ---------------------------------------------------------------------------


class TestRuleStore:
    """In-memory rule store that records failures for later L3 application."""

    def test_starts_empty(self) -> None:
        store = RuleStore()
        assert store.all() == []

    def test_record_rule_appends(self) -> None:
        store = RuleStore()
        rule = RuleRecord(
            operation="git_push",
            pattern="remote rejected non-fast-forward",
            recovery_hint="fetch + rebase first",
        )
        store.add(rule)
        assert store.all() == [rule]

    def test_find_matching_returns_relevant_rules(self) -> None:
        store = RuleStore()
        store.add(RuleRecord("git_push", "non-fast-forward", "rebase first"))
        store.add(RuleRecord("git_push", "auth failed", "rotate token"))
        store.add(RuleRecord("git_rebase", "conflict", "use three-way merge"))

        matches = store.find_matching(operation="git_push", error="non-fast-forward detected")
        assert len(matches) == 1
        assert matches[0].recovery_hint == "rebase first"

    def test_record_rule_returns_record(self) -> None:
        store = RuleStore()
        rec = record_rule(
            store,
            operation="git_push",
            error="connection refused",
            recovery_hint="wait and retry; check network",
        )
        assert isinstance(rec, RuleRecord)
        assert rec.pattern == "connection refused"
        assert rec.recovery_hint.startswith("wait")
        assert store.all() == [rec]


class TestExtractRule:
    """extract_rule() derives a RuleRecord from a failed operation's context."""

    def test_extract_returns_record_with_pattern_and_hint(self) -> None:
        rec = extract_rule(
            operation="git_push",
            error="fatal: refusing to merge unrelated histories",
            hint="set up tracking branch first",
        )
        assert isinstance(rec, RuleRecord)
        assert rec.operation == "git_push"
        assert "unrelated histories" in rec.pattern
        assert rec.recovery_hint == "set up tracking branch first"

    def test_extract_truncates_long_errors(self) -> None:
        long_err = "x" * 1000
        rec = extract_rule(operation="op", error=long_err, hint="hint")
        # Pattern is a digest of the error, capped at a reasonable length.
        assert len(rec.pattern) <= 256

    def test_extract_strips_whitespace(self) -> None:
        rec = extract_rule(
            operation="op",
            error="  some error  \n",
            hint="  do this  ",
        )
        assert rec.pattern == "some error"
        assert rec.recovery_hint == "do this"


class TestApplyRule:
    """apply_rule() uses a recorded rule to suggest recovery for a new error."""

    def test_returns_matching_recovery_hint(self) -> None:
        store = RuleStore()
        store.add(
            RuleRecord(
                operation="git_push",
                pattern="non-fast-forward",
                recovery_hint="run `git pull --rebase` first",
            )
        )
        hint = apply_rule(store, operation="git_push", error="non-fast-forward update")
        assert hint is not None
        assert "rebase" in hint

    def test_returns_none_when_no_match(self) -> None:
        store = RuleStore()
        hint = apply_rule(store, operation="git_push", error="totally unknown")
        assert hint is None


class TestL3EndToEnd:
    """After L1 exhausts and L2 no-ops, the failure contributes a rule."""

    async def test_failure_flow_extracts_rule_to_store(self) -> None:
        store = RuleStore()

        async def flaky() -> str:
            raise RuntimeError("connection refused")

        # L1 retries until exhausted.
        with pytest.raises(L1Exhausted) as exc:
            await retry_with_backoff(flaky, max_attempts=3, base_delay=0.0)

        # L2 is a no-op (does not recover).
        l2_outcome = await l2_noop(operation="flaky_op", l1_context={"err": str(exc.value)})
        assert l2_outcome == "noop_recovery"

        # L3 extracts the failure into a long-term rule.
        rec = record_rule(
            store,
            operation="flaky_op",
            error=str(exc.value),
            recovery_hint="wait + retry; verify network",
        )
        assert store.find_matching(operation="flaky_op", error="connection refused")
        assert rec.recovery_hint.startswith("wait")


# Silence unused-import warning for asyncio in static analyzers.
_ = asyncio