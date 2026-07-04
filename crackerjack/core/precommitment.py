"""Precommitment Hypothesis Lock.

Spec: 2026-06-22-precommitment-hypothesis-lock-design.md

A hypothesis slate is locked at iteration 0 to prevent post-hoc
rationalization. The lock produces an immutable, signature-bound copy
that downstream verification can detect for mismatch.

Layered:
- ``Hypothesis`` - frozen dataclass; the actual claim + criteria.
- ``compute_signature`` - stable content hash (sha256 hex).
- ``HypothesisLock.lock`` - returns an immutable ``LockResult``.
- ``verify_lock`` - returns True/False for whether a result satisfies criteria.
- ``HypothesisLock.check_post_hoc`` - raises on claim drift.
- ``LockStore`` (Protocol) + ``InMemoryLockStore`` - swappable persistence
  interface (Dhara in production; in-memory for v0).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class Hypothesis:
    """A precommitment hypothesis with claim, criteria, and confidence.

    All fields are required. The dataclass is frozen so the locked
    hypothesis cannot be mutated after creation.
    """

    claim: str
    falsification_criteria: str
    success_criteria: str
    confidence: float
    locked_at: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"confidence must be in [0.0, 1.0], got {self.confidence!r}"
            raise ValueError(msg)


@dataclass(frozen=True)
class LockResult:
    """An immutable, signed lock for a hypothesis."""

    lock_id: str
    hypothesis: Hypothesis
    signature: str


def compute_signature(hypothesis: Hypothesis) -> str:
    """Compute a stable content-addressed signature for a hypothesis.

    Uses canonical JSON serialization of all fields so identical content
    produces identical signatures regardless of construction order.
    """
    payload = {
        "claim": hypothesis.claim,
        "falsification_criteria": hypothesis.falsification_criteria,
        "success_criteria": hypothesis.success_criteria,
        "confidence": hypothesis.confidence,
        "locked_at": hypothesis.locked_at,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _verify_signature(lock: LockResult) -> None:
    """Raise SignatureMismatch if the lock's signature does not match its content."""
    expected = compute_signature(lock.hypothesis)
    if expected != lock.signature:
        msg = (
            f"signature mismatch for lock_id={lock.lock_id!r}: "
            f"expected {expected!r}, got {lock.signature!r}"
        )
        raise SignatureMismatch(msg)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class HypothesisViolation(Exception):
    """Raised when post-hoc evidence conflicts with the locked hypothesis.

    This is the detection signal for post-hoc rationalization: the
    locked claim at iteration 0 no longer matches the claim the agent
    is asserting at a later point.
    """

    def __init__(
        self,
        message: str,
        *,
        locked_claim: str | None = None,
        post_hoc_claim: str | None = None,
        lock_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.locked_claim = locked_claim
        self.post_hoc_claim = post_hoc_claim
        self.lock_id = lock_id


class SignatureMismatch(Exception):
    """Raised when a lock's signature does not match its content."""


# ---------------------------------------------------------------------------
# Lock + verify
# ---------------------------------------------------------------------------


class HypothesisLock:
    """Static helpers for locking hypotheses and checking post-hoc claims."""

    @staticmethod
    def lock(hypothesis: Hypothesis) -> LockResult:
        """Produce an immutable, signed copy of the hypothesis.

        The returned ``LockResult`` is frozen; the original ``hypothesis``
        is not mutated.
        """
        signature = compute_signature(hypothesis)
        # Hypothesis is already frozen via @dataclass(frozen=True),
        # so storing it directly is safe.
        return LockResult(
            lock_id=uuid.uuid4().hex,
            hypothesis=hypothesis,
            signature=signature,
        )

    @staticmethod
    def check_post_hoc(
        lock: LockResult,
        *,
        post_hoc_claim: str,
    ) -> None:
        """Raise ``HypothesisViolation`` if ``post_hoc_claim`` drifts from lock.

        Also raises ``SignatureMismatch`` if the lock's signature does
        not match its content (i.e. the lock was tampered with).
        """
        _verify_signature(lock)
        if post_hoc_claim != lock.hypothesis.claim:
            msg = (
                f"post-hoc claim drift detected for lock_id={lock.lock_id!r}: "
                f"locked={lock.hypothesis.claim!r}, "
                f"post_hoc={post_hoc_claim!r}"
            )
            raise HypothesisViolation(
                msg,
                locked_claim=lock.hypothesis.claim,
                post_hoc_claim=post_hoc_claim,
                lock_id=lock.lock_id,
            )


# ---------------------------------------------------------------------------
# Verify criteria
# ---------------------------------------------------------------------------


def _result_satisfies(
    falsification_criteria: str,
    success_criteria: str,
    result: Mapping[str, Any],
) -> bool:
    """Heuristic check whether a result satisfies the success / falsification criteria.

    Strategy:
    - If any falsification keyword appears in the result text, falsify.
    - If any success keyword appears in the result text, succeed.
    - If neither pattern matches (no keywords to match), fall back to a
      simple "crashed == False" rule for falsification and any
      non-empty success criterion as a soft success.

    This is intentionally simple for v0; richer NLP can replace it later.
    """
    falsification_keywords = _extract_keywords(falsification_criteria)
    success_keywords = _extract_keywords(success_criteria)

    text_blob = json.dumps(dict(result), sort_keys=True).lower()

    if falsification_keywords:
        if any(kw in text_blob for kw in falsification_keywords):
            return False
    else:
        # No falsification keywords to match → check explicit crash flag
        if result.get("crashed") is True:
            return False
        if result.get("outcome") and "crash" in str(result["outcome"]).lower():
            return False

    if success_keywords:
        return any(kw in text_blob for kw in success_keywords)

    # No success keywords; default to not-violated (since falsification passed)
    return True


def _extract_keywords(criteria: str) -> list[str]:
    """Extract simple word-level keywords from a criteria string.

    Drops very short words and common stop words. Used for the heuristic
    matcher in ``_result_satisfies``.
    """
    stop_words = {
        "the",
        "a",
        "an",
        "is",
        "if",
        "on",
        "in",
        "of",
        "to",
        "and",
        "or",
        "for",
        "within",
        "than",
        "that",
        "this",
        "it",
    }
    tokens = [t.lower().strip(".,;:!?\"'()[]{}") for t in criteria.split()]
    return [t for t in tokens if len(t) >= 3 and t not in stop_words]


def verify_lock(lock: LockResult, result: Mapping[str, Any]) -> bool:
    """Return True iff ``result`` satisfies the locked hypothesis's criteria.

    Verifies the lock's signature first; raises ``SignatureMismatch``
    on tamper, otherwise returns the boolean satisfaction result.
    """
    _verify_signature(lock)
    return _result_satisfies(
        lock.hypothesis.falsification_criteria,
        lock.hypothesis.success_criteria,
        result,
    )


# ---------------------------------------------------------------------------
# Lock store (Protocol + in-memory v0)
# ---------------------------------------------------------------------------


@runtime_checkable
class LockStore(Protocol):
    """Pluggable lock store interface.

    v0 ships only the in-memory implementation; later iterations can
    swap to Dhara or another durable store without changing callers.
    """

    def put(self, lock: LockResult) -> None:
        """Persist a lock. Must overwrite any existing entry with the same lock_id."""
        ...

    def get(self, lock_id: str) -> LockResult | None:
        """Return the lock for ``lock_id`` or None if absent."""
        ...

    def size(self) -> int:
        """Return the number of locks currently stored."""
        ...


@dataclass
class InMemoryLockStore:
    """Volatile in-memory ``LockStore`` implementation for v0."""

    _locks: dict[str, LockResult] = field(default_factory=dict)

    def put(self, lock: LockResult) -> None:
        self._locks[lock.lock_id] = lock

    def get(self, lock_id: str) -> LockResult | None:
        return self._locks.get(lock_id)

    def size(self) -> int:
        return len(self._locks)


__all__ = [
    "Hypothesis",
    "HypothesisLock",
    "HypothesisViolation",
    "InMemoryLockStore",
    "LockResult",
    "LockStore",
    "SignatureMismatch",
    "compute_signature",
    "verify_lock",
]
