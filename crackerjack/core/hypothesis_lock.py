from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class Hypothesis:
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
    lock_id: str
    hypothesis: Hypothesis
    signature: str


def compute_signature(hypothesis: Hypothesis) -> str:
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
    expected = compute_signature(lock.hypothesis)
    if expected != lock.signature:
        msg = (
            f"signature mismatch for lock_id={lock.lock_id!r}: "
            f"expected {expected!r}, got {lock.signature!r}"
        )
        raise SignatureMismatch(msg)


class HypothesisViolation(Exception):
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
    pass


class HypothesisLock:
    @staticmethod
    def lock(hypothesis: Hypothesis) -> LockResult:
        signature = compute_signature(hypothesis)

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


def _result_satisfies(
    falsification_criteria: str,
    success_criteria: str,
    result: Mapping[str, Any],
) -> bool:
    falsification_keywords = _extract_keywords(falsification_criteria)
    success_keywords = _extract_keywords(success_criteria)

    text_blob = json.dumps(dict(result), sort_keys=True).lower()

    if falsification_keywords:
        if any(kw in text_blob for kw in falsification_keywords):
            return False
    else:
        if result.get("crashed") is True:
            return False
        if result.get("outcome") and "crash" in str(result["outcome"]).lower():
            return False

    if success_keywords:
        return any(kw in text_blob for kw in success_keywords)

    return True


def _extract_keywords(criteria: str) -> list[str]:
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
    _verify_signature(lock)
    return _result_satisfies(
        lock.hypothesis.falsification_criteria,
        lock.hypothesis.success_criteria,
        result,
    )


@runtime_checkable
class LockStore(Protocol):
    def put(self, lock: LockResult) -> None: ...

    def get(self, lock_id: str) -> LockResult | None: ...

    def size(self) -> int: ...


@dataclass
class InMemoryLockStore:
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
