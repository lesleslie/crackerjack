"""Regression: ``AutofixCoordinator`` delegates no-op detection to the lifecycle.

PR 4 moves the defect-#1 no-op detection logic into
``crackerjack.ai_fix.issue_lifecycle``. The coordinator keeps its
``_is_no_op_failure`` method as a thin delegator so existing callers (and the
thrash regression test) keep working unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.agents.base import FixResult
from crackerjack.ai_fix.issue_lifecycle import is_no_op_failure
from crackerjack.core.autofix_coordinator import AutofixCoordinator


@pytest.fixture
def coordinator() -> AutofixCoordinator:
    return AutofixCoordinator(console=None, pkg_path=Path("/tmp/test"))


class TestIsNoOpDelegation:
    def test_matches_helper_for_no_op_marker(self, coordinator) -> None:
        feedback = "no-op fix: file content unchanged"
        assert coordinator._is_no_op_failure(feedback, None) is True
        assert coordinator._is_no_op_failure(feedback, None) == is_no_op_failure(
            feedback, None
        )

    def test_matches_helper_for_result_marker(self, coordinator) -> None:
        results = [
            FixResult(
                success=False,
                remaining_issues=[
                    "write_file_content returned success but file content is unchanged"
                ],
            )
        ]
        assert coordinator._is_no_op_failure("Attempt 1", results) is True
        assert coordinator._is_no_op_failure("Attempt 1", results) == is_no_op_failure(
            "Attempt 1", results
        )

    def test_matches_helper_for_normal_failure(self, coordinator) -> None:
        feedback = "Quality validation failed (ruff/refurb): E501 line too long"
        assert coordinator._is_no_op_failure(feedback, None) is False
        assert coordinator._is_no_op_failure(feedback, None) == is_no_op_failure(
            feedback, None
        )
