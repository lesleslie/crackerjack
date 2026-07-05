"""Tests for the async-path ty diagnostic filtering.

Mirrors the sync-side ``TestTyVerboseFiltersTestDir`` class in
``tests/test_hook_executor.py``. The two paths must produce identical
per-issue detail panels — both go through the module-level
``parse_ty_ratchet_issues`` filter in ``crackerjack.executors.hook_executor``.

User report (2026-07-04): running ``crackerjack -c -v`` was still showing
``tests/*`` diagnostics in the per-issue details. The fix:

1. ``AsyncHookExecutor.__init__`` accepts ``verbose`` and ``test_dir``.
2. ``AsyncHookExecutor._parse_hook_output`` now branches on ``hook_name == "ty"``
   and delegates to the shared ``parse_ty_ratchet_issues`` filter.
3. ``AsyncHookExecutor._build_success_result`` skips the raw-10-line
   fallback for ty so filtered-out ``tests/*`` lines do not leak back
   into the panel via the fallback path.
4. ``AsyncHookManager.__init__`` plumbs ``verbose`` and ``test_dir``
   into the default ``AsyncHookExecutor`` and flips ``quiet=not verbose``
   so an explicit ``-v`` wins over the hardcoded ``quiet=True``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

from rich.console import Console

from crackerjack.executors.async_hook_executor import AsyncHookExecutor
from crackerjack.managers.async_hook_manager import AsyncHookManager


def _quiet_executor(test_dir: str = "tests") -> AsyncHookExecutor:
    return AsyncHookExecutor(
        console=Console(),
        pkg_path=Path(),
        verbose=False,
        test_dir=test_dir,
    )


def _verbose_executor(test_dir: str = "tests") -> AsyncHookExecutor:
    return AsyncHookExecutor(
        console=Console(),
        pkg_path=Path(),
        verbose=True,
        test_dir=test_dir,
    )


TY_MIXED_OUTPUT = (
    "ty ratchet [split] prod: FAIL (5/150)\n"
    "ty ratchet [split] test: FAIL (12/30)\n"
    "crackerjack/agents/foo.py:1:1: error[E001] x\n"
    "crackerjack/agents/bar.py:2:2: error[E001] y\n"
    "crackerjack/agents/baz.py:3:3: error[E001] z\n"
    "crackerjack/agents/qux.py:4:4: error[E001] w\n"
    "crackerjack/agents/quux.py:5:5: error[E001] v\n"
    "tests/test_alpha.py:1:1: error[E001] test1\n"
    "tests/test_beta.py:2:2: error[E001] test2\n"
    "tests/test_gamma.py:3:3: error[E001] test3\n"
    "tests/test_delta.py:4:4: error[E001] test4\n"
    "tests/test_epsilon.py:5:5: error[E001] test5\n"
    "tests/test_zeta.py:6:6: error[E001] test6\n"
    "tests/test_eta.py:7:7: error[E001] test7\n"
    "tests/test_theta.py:8:8: error[E001] test8\n"
    "tests/test_iota.py:9:9: error[E001] test9\n"
    "tests/test_kappa.py:10:10: error[E001] test10\n"
    "tests/test_lambda.py:11:11: error[E001] test11\n"
    "tests/test_mu.py:12:12: error[E001] test12\n"
    "Found 5 diagnostics\n"
    "Found 12 diagnostics\n"
)


class TestAsyncHookExecutorTyInit:
    """``AsyncHookExecutor.__init__`` accepts and stores verbose/test_dir."""

    def test_verbose_true_is_stored(self) -> None:
        executor = AsyncHookExecutor(
            console=Console(),
            pkg_path=Path(),
            verbose=True,
        )
        assert executor.verbose is True

    def test_verbose_false_is_stored(self) -> None:
        executor = AsyncHookExecutor(
            console=Console(),
            pkg_path=Path(),
            verbose=False,
        )
        assert executor.verbose is False

    def test_test_dir_default_is_tests(self) -> None:
        executor = AsyncHookExecutor(
            console=Console(),
            pkg_path=Path(),
            verbose=True,
        )
        assert executor._ty_test_dir == "tests"

    def test_test_dir_custom_is_stored(self) -> None:
        executor = AsyncHookExecutor(
            console=Console(),
            pkg_path=Path(),
            verbose=True,
            test_dir="tests_unit",
        )
        assert executor._ty_test_dir == "tests_unit"

    def test_default_kwargs_keep_quiet_default(self) -> None:
        """No verbose, no test_dir: defaults to verbose=False, test_dir='tests'."""
        executor = AsyncHookExecutor(console=Console(), pkg_path=Path())
        assert executor.verbose is False
        assert executor._ty_test_dir == "tests"


class TestAsyncHookExecutorTyParsing:
    """``_parse_hook_output`` returns filtered issues for ty."""

    def test_verbose_keeps_prod_drops_tests(
        self,
    ) -> None:
        executor = _verbose_executor()
        result = executor._parse_hook_output(0, TY_MIXED_OUTPUT, "ty")
        # 5 prod diagnostics remain; 12 test-dir diagnostics dropped.
        assert len(result["issues"]) == 5, (
            f"verbose must drop tests/* diagnostics; got {result['issues']!r}"
        )
        for issue in result["issues"]:
            assert issue.startswith("crackerjack/"), (
                f"verbose leaked non-prod line: {issue!r}"
            )
            assert not issue.startswith("tests/"), (
                f"verbose leaked tests/ prefix: {issue!r}"
            )

    def test_non_verbose_still_drops_tests(self) -> None:
        """The filter is unconditional — verbose=False does NOT re-enable
        test-dir diagnostics. This pins the intentional contract; see
        ``parse_ty_ratchet_issues`` docstring for rationale.
        """
        executor = _quiet_executor()
        result = executor._parse_hook_output(0, TY_MIXED_OUTPUT, "ty")
        # 5 prod diagnostics remain; 12 test-dir diagnostics dropped,
        # regardless of verbose flag.
        assert len(result["issues"]) == 5, (
            f"filter must drop tests/* diagnostics regardless of verbose; "
            f"got {len(result['issues'])}: {result['issues']!r}"
        )
        for issue in result["issues"]:
            assert not issue.startswith("tests/"), (
                f"filter leaked tests/ prefix: {issue!r}"
            )

    def test_verbose_respects_custom_test_dir(self) -> None:
        executor = _verbose_executor(test_dir="tests_unit")
        rewritten = TY_MIXED_OUTPUT.replace("tests/", "tests_unit/")
        result = executor._parse_hook_output(0, rewritten, "ty")
        # All prod diagnostics remain; tests_unit/* dropped.
        assert len(result["issues"]) == 5
        for issue in result["issues"]:
            assert not issue.startswith("tests_unit/"), (
                f"verbose leaked tests_unit/ prefix: {issue!r}"
            )

    def test_ty_branch_skips_semgrep_branch(self) -> None:
        """Sanity: hook_name=ty uses ty branch, not semgrep."""
        executor = _verbose_executor()
        # JSON-shaped output that semgrep would treat as JSON
        json_output = (
            '{"results": [{"path": "tests/leak.py", "start": {"line": 1}, '
            '"check_id": "X", "extra": {"message": "leak"}}]}'
        )
        result = executor._parse_hook_output(1, json_output, "ty")
        # ty filter ignores JSON; result["issues"] is [].
        assert result["issues"] == [], (
            f"ty branch must not parse JSON like semgrep; got {result!r}"
        )

    def test_non_ty_hooks_still_use_default_branch(self) -> None:
        """Sanity: hook_name != 'ty' returns the default parse result."""
        executor = _verbose_executor()
        result = executor._parse_hook_output(
            1,
            "Found issues in 3 files",
            "ruff-check",
        )
        # The default branch populates files_processed via file-count regex.
        assert result["files_processed"] >= 0
        assert result["issues"] == []


class TestAsyncHookExecutorBuildSuccessSkipsRawFallback:
    """``_build_success_result`` MUST NOT leak raw 10 lines for ty.

    This is the user's reported symptom: when verbose filters all
    diagnostics out (because they're test-dir lines), the synchronous
    fallback path grabs the first 10 lines of stdout/stderr and stuffs
    ``tests/*`` lines back into the panel. We need the async path to
    stay empty in that scenario so the panel surfaces prod-only
    diagnostics.
    """

    async def test_ty_with_no_parsed_issues_does_not_leak_raw_lines(
        self,
        monkeypatch: object,
    ) -> None:
        """When ty parser returns [] (verbose filtered everything),
        the result's issues_found stays []. The raw 10-line fallback
        is what previously leaked tests/* diagnostics.
        """
        executor = _verbose_executor()
        # No prod diagnostics; only test-dir diagnostics.
        tests_only_output = (
            "ty ratchet [split] prod: PASS (0/150)\n"
            "ty ratchet [split] test: FAIL (3/30)\n"
            "tests/test_a.py:1:1: error[E001] a\n"
            "tests/test_b.py:2:2: error[E001] b\n"
            "tests/test_c.py:3:3: error[E001] c\n"
            "Found 3 diagnostics\n"
        )

        # Mock process to supply stdout/stderr bytes.
        class _FakeProcess:
            returncode = 1

            def __init__(self) -> None:
                pass

        # Patch _decode_process_output via direct attrs.
        executor._last_stdout = tests_only_output.encode()
        executor._last_stderr = b""

        # Use a real HookDefinition for stage value.
        from crackerjack.config.hooks import HookDefinition, HookStage
        hook = HookDefinition(
            name="ty",
            command=["fake"],
            stage=HookStage.FAST,
        )

        result = await executor._build_success_result(
            _FakeProcess(), hook, 0.5
        )

        # The fix: no raw-10-line fallback for ty when parser returned [].
        # 3 tests/* diagnostics should NOT appear in the panel.
        assert result.status == "failed"
        assert result.issues_found == [], (
            f"ty panel leaked non-empty issues_found: {result.issues_found!r}"
        )
        assert all(
            not issue.startswith("tests/")
            for issue in result.issues_found
        ), "tests/* line leaked into per-issue panel"


class TestAsyncHookManagerPlumbsVerbose:
    """``AsyncHookManager`` propagates ``verbose`` and ``test_dir``."""

    def test_verbose_true_propagates_to_executor(self) -> None:
        """When verbose=True is passed, the default AsyncHookExecutor
        is constructed with verbose=True and quiet=False.
        """
        manager = AsyncHookManager(
            console=MagicMock(),
            pkg_path=Path(),
            verbose=True,
            test_dir="tests_unit",
        )
        executor = manager.async_executor
        assert isinstance(executor, AsyncHookExecutor)
        assert executor.verbose is True, (
            "verbose=True must propagate to the default AsyncHookExecutor"
        )
        assert executor.quiet is False, (
            "verbose=True must override the hardcoded quiet=True default"
        )
        assert executor._ty_test_dir == "tests_unit", (
            "custom test_dir must propagate to the default AsyncHookExecutor"
        )

    def test_verbose_false_keeps_quiet_true_default(self) -> None:
        """When verbose=False is passed, the default AsyncHookExecutor
        stays quiet=True (the historical default).
        """
        manager = AsyncHookManager(
            console=MagicMock(),
            pkg_path=Path(),
            verbose=False,
        )
        executor = manager.async_executor
        assert isinstance(executor, AsyncHookExecutor)
        assert executor.verbose is False
        assert executor.quiet is True, (
            "verbose=False must keep the historical quiet=True default"
        )
        assert executor._ty_test_dir == "tests"

    def test_manager_stores_verbose_for_inspection(self) -> None:
        manager = AsyncHookManager(
            console=MagicMock(),
            pkg_path=Path(),
            verbose=True,
        )
        assert manager.verbose is True
