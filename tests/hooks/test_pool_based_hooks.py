"""Tests for pool_based_hooks.PoolHookResult.

Phase H: verifies that the dataclass accepts the kwargs that the
17 call sites in pool_based_hooks.py pass to it. Prior to Phase H,
the file imported HookResult from a non-existent location
(crackerjack.models.protocols), which would have raised
ImportError at module load time.
"""

from __future__ import annotations

from crackerjack.hooks.pool_based_hooks import PoolBasedHooks, PoolHookResult


class TestPoolHookResult:
    """PoolHookResult is the type the pool-based hooks construct."""

    def test_default_construction(self):
        """Default values match the call-site patterns."""
        r = PoolHookResult()
        assert r.success is True
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.exit_code == 0
        assert r.error_message is None
        assert r.duration == 0.0
        assert r.metadata == {}

    def test_success_kwargs(self):
        """The most common call-site pattern (early-return for disabled)."""
        r = PoolHookResult(
            success=True,
            stdout="Pool scanning disabled, skipping complexipy",
            stderr="",
            exit_code=0,
        )
        assert r.success is True
        assert "Pool scanning disabled" in r.stdout
        assert r.exit_code == 0

    def test_failure_kwargs(self):
        """The error-path pattern."""
        r = PoolHookResult(
            success=False,
            stdout="",
            stderr="connection refused",
            exit_code=1,
        )
        assert r.success is False
        assert r.stderr == "connection refused"
        assert r.exit_code == 1

    def test_module_imports_without_error(self):
        """The original bug: ``from crackerjack.models.protocols import
        HookResult`` raised ImportError. Verify the module now loads."""
        # If this import fails, the test fails. We re-import here to
        # make the contract explicit even though it's already at the
        # top of the file.
        from crackerjack.hooks import pool_based_hooks  # noqa: F401

        assert hasattr(pool_based_hooks, "PoolBasedHooks")
        assert hasattr(pool_based_hooks, "PoolHookResult")

    def test_pool_based_hooks_class_exists(self):
        """The PoolBasedHooks class is importable (was orphaned before)."""
        assert PoolBasedHooks is not None
        # Constructor signature: (settings, console=None)
        import inspect

        sig = inspect.signature(PoolBasedHooks.__init__)
        params = list(sig.parameters.keys())
        assert "settings" in params
        assert "console" in params
