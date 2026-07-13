"""Unit tests for the precommitment hypothesis lock module.

TDD: Spec #2 (precommitment-hypothesis-lock). The lock prevents
post-hoc rationalization by freezing a hypothesis slate at iteration 0
and detecting later mismatches.
"""

from __future__ import annotations

import pytest

from crackerjack.core.precommitment import (
    Hypothesis,
    HypothesisLock,
    HypothesisViolation,
    InMemoryLockStore,
    LockResult,
    LockStore,
    SignatureMismatch,
    compute_signature,
    verify_lock,
)


# ---------------------------------------------------------------------------
# Hypothesis dataclass
# ---------------------------------------------------------------------------


class TestHypothesisDataclass:
    """Test the Hypothesis dataclass shape and immutability."""

    def test_hypothesis_required_fields(self) -> None:
        h = Hypothesis(
            claim="X is true",
            falsification_criteria="if X is false",
            success_criteria="if X is true",
            confidence=0.8,
            locked_at="2026-06-22T00:00:00Z",
        )
        assert h.claim == "X is true"
        assert h.falsification_criteria == "if X is false"
        assert h.success_criteria == "if X is true"
        assert h.confidence == 0.8
        assert h.locked_at == "2026-06-22T00:00:00Z"

    def test_hypothesis_is_frozen(self) -> None:
        h = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        with pytest.raises((AttributeError, Exception)):
            h.claim = "Y"  # type: ignore[misc]

    def test_hypothesis_confidence_bounded(self) -> None:
        with pytest.raises(ValueError):
            Hypothesis(
                claim="X",
                falsification_criteria="~X",
                success_criteria="X",
                confidence=1.5,  # out of range
                locked_at="2026-06-22T00:00:00Z",
            )
        with pytest.raises(ValueError):
            Hypothesis(
                claim="X",
                falsification_criteria="~X",
                success_criteria="X",
                confidence=-0.1,
                locked_at="2026-06-22T00:00:00Z",
            )

    def test_hypothesis_equality_by_content(self) -> None:
        a = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        b = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        assert a == b

    def test_hypothesis_hashable(self) -> None:
        h = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        # Should be hashable for use in sets/dicts
        assert hash(h) == hash(h)
        assert {h} == {h}


# ---------------------------------------------------------------------------
# Signature / hash
# ---------------------------------------------------------------------------


class TestComputeSignature:
    """Test that compute_signature is stable and content-addressed."""

    def test_signature_stable_for_same_content(self) -> None:
        h = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        s1 = compute_signature(h)
        s2 = compute_signature(h)
        assert s1 == s2

    def test_signature_changes_with_content(self) -> None:
        h1 = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        h2 = Hypothesis(
            claim="Y",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        assert compute_signature(h1) != compute_signature(h2)

    def test_signature_is_hex_string(self) -> None:
        h = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        s = compute_signature(h)
        assert isinstance(s, str)
        assert len(s) == 64  # sha256 hex


# ---------------------------------------------------------------------------
# Lock production
# ---------------------------------------------------------------------------


class TestHypothesisLock:
    """Test that locking produces an immutable, verifiable copy."""

    def test_lock_produces_immutable_copy(self) -> None:
        h = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        lock = HypothesisLock.lock(h)
        assert isinstance(lock, LockResult)
        # Locked copy is frozen
        with pytest.raises((AttributeError, Exception)):
            lock.hypothesis.claim = "Y"  # type: ignore[misc]

    def test_lock_has_signature(self) -> None:
        h = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        lock = HypothesisLock.lock(h)
        assert lock.signature == compute_signature(h)
        assert len(lock.signature) == 64

    def test_lock_has_lock_id(self) -> None:
        h = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        lock = HypothesisLock.lock(h)
        assert isinstance(lock.lock_id, str)
        assert len(lock.lock_id) > 0

    def test_lock_does_not_mutate_input(self) -> None:
        h = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        original_claim = h.claim
        HypothesisLock.lock(h)
        assert h.claim == original_claim


# ---------------------------------------------------------------------------
# Verify: True/False for criteria satisfaction
# ---------------------------------------------------------------------------


class TestVerifyLock:
    """Test that verify returns True/False for whether a result satisfies criteria."""

    def test_verify_satisfies_success_criteria_returns_true(self) -> None:
        h = Hypothesis(
            claim="deployment works",
            falsification_criteria="service crashes on startup",
            success_criteria="service starts within 5 seconds",
            confidence=0.7,
            locked_at="2026-06-22T00:00:00Z",
        )
        lock = HypothesisLock.lock(h)
        result = {
            "outcome": "started successfully",
            "duration_seconds": 3.0,
            "crashed": False,
        }
        assert verify_lock(lock, result) is True

    def test_verify_violates_falsification_returns_false(self) -> None:
        h = Hypothesis(
            claim="deployment works",
            falsification_criteria="service crashes on startup",
            success_criteria="service starts within 5 seconds",
            confidence=0.7,
            locked_at="2026-06-22T00:00:00Z",
        )
        lock = HypothesisLock.lock(h)
        result = {
            "outcome": "service crashed on startup",
            "duration_seconds": 0.5,
            "crashed": True,
        }
        assert verify_lock(lock, result) is False

    def test_verify_returns_bool_type(self) -> None:
        h = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        lock = HypothesisLock.lock(h)
        result = verify_lock(lock, {"observation": "anything"})
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Mismatch detection — raises HypothesisViolation
# ---------------------------------------------------------------------------


class TestMismatchDetection:
    """Test that post-hoc claim drift raises HypothesisViolation."""

    def test_post_hoc_claim_mismatch_raises(self) -> None:
        h = Hypothesis(
            claim="original claim",
            falsification_criteria="~original",
            success_criteria="original",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        lock = HypothesisLock.lock(h)
        with pytest.raises(HypothesisViolation):
            HypothesisLock.check_post_hoc(lock, post_hoc_claim="different claim")

    def test_matching_post_hoc_claim_passes(self) -> None:
        h = Hypothesis(
            claim="original claim",
            falsification_criteria="~original",
            success_criteria="original",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        lock = HypothesisLock.lock(h)
        # Should not raise
        HypothesisLock.check_post_hoc(lock, post_hoc_claim="original claim")

    def test_violation_carries_context(self) -> None:
        h = Hypothesis(
            claim="original",
            falsification_criteria="~original",
            success_criteria="original",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        lock = HypothesisLock.lock(h)
        with pytest.raises(HypothesisViolation) as excinfo:
            HypothesisLock.check_post_hoc(lock, post_hoc_claim="drifted")
        # The exception should reference both claims
        msg = str(excinfo.value)
        assert "original" in msg or "drifted" in msg


# ---------------------------------------------------------------------------
# Lock store
# ---------------------------------------------------------------------------


class TestInMemoryLockStore:
    """Test the in-memory lock store interface."""

    def test_store_and_retrieve(self) -> None:
        h = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        lock = HypothesisLock.lock(h)
        store: LockStore = InMemoryLockStore()
        store.put(lock)
        retrieved = store.get(lock.lock_id)
        assert retrieved is not None
        assert retrieved.lock_id == lock.lock_id
        assert retrieved.signature == lock.signature

    def test_get_missing_returns_none(self) -> None:
        store: LockStore = InMemoryLockStore()
        assert store.get("nonexistent") is None

    def test_store_iteration_count(self) -> None:
        store: LockStore = InMemoryLockStore()
        assert store.size() == 0
        h = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        store.put(HypothesisLock.lock(h))
        assert store.size() == 1
        store.put(HypothesisLock.lock(h))
        assert store.size() == 2

    def test_lock_store_is_satisfied_by_lockstore_protocol(self) -> None:
        """LockStore is a swappable interface — InMemoryLockStore implements it."""
        store = InMemoryLockStore()
        assert isinstance(store, LockStore)


# ---------------------------------------------------------------------------
# Signature mismatch
# ---------------------------------------------------------------------------


class TestSignatureMismatch:
    """Test that mutating a lock invalidates its signature."""

    def test_signature_mismatch_raises(self) -> None:
        h = Hypothesis(
            claim="X",
            falsification_criteria="~X",
            success_criteria="X",
            confidence=0.5,
            locked_at="2026-06-22T00:00:00Z",
        )
        lock = HypothesisLock.lock(h)
        # Tamper with the lock: build a new lock with same lock_id
        # but a different signature.
        tampered = LockResult(
            lock_id=lock.lock_id,
            hypothesis=Hypothesis(
                claim="X-tampered",
                falsification_criteria="~X",
                success_criteria="X",
                confidence=0.5,
                locked_at="2026-06-22T00:00:00Z",
            ),
            signature="0" * 64,
        )
        with pytest.raises(SignatureMismatch):
            HypothesisLock.check_post_hoc(tampered, post_hoc_claim="anything")
