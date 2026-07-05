"""Unit tests for ClaudeCodeBridge.

Focused on ``_validate_ai_result`` and the AI-error capture contract. The
bridge is also exercised via the broader ``test_new_agents.py`` /
``test_qwen_code_bridge.py`` style integration tests, so this module keeps
its surface intentionally narrow — just the regression coverage for the
``ai_result.get("error", ...)`` capture bug at
``crackerjack/agents/claude_code_bridge.py:501``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    Priority,
)
from crackerjack.agents.claude_code_bridge import (
    ClaudeCodeBridge,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def context(tmp_path: Path) -> AgentContext:
    return AgentContext(project_path=tmp_path)


@pytest.fixture
def bridge(context: AgentContext) -> ClaudeCodeBridge:
    return ClaudeCodeBridge(context)


@pytest.fixture
def sample_issue() -> Issue:
    return Issue(
        id="issue-789",
        type=IssueType.TYPE_ERROR,
        severity=Priority.HIGH,
        message="Incompatible return type",
        file_path="/tmp/example.py",
        line_number=10,
        details=["line 10: return value should be int"],
    )


# ---------------------------------------------------------------------------
# _validate_ai_result
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateAiResult:
    async def test_returns_none_when_ai_result_failed(
        self,
        bridge: ClaudeCodeBridge,
        sample_issue: Issue,
    ) -> None:
        ai_result = {"success": False, "error": "boom"}
        result = await bridge._validate_ai_result(ai_result, sample_issue)
        assert result is None

    async def test_returns_none_when_confidence_below_threshold(
        self,
        bridge: ClaudeCodeBridge,
        sample_issue: Issue,
    ) -> None:
        ai_result = {
            "success": True,
            "fixed_code": "x = 1",
            "explanation": "e",
            "confidence": 0.5,  # below 0.7
        }
        result = await bridge._validate_ai_result(ai_result, sample_issue)
        assert result is None

    async def test_returns_tuple_when_above_threshold(
        self,
        bridge: ClaudeCodeBridge,
        sample_issue: Issue,
    ) -> None:
        ai_result = {
            "success": True,
            "fixed_code": "x = 1",
            "explanation": "e",
            "confidence": 0.9,
            "changes_made": ["c1"],
            "potential_side_effects": ["s1"],
        }
        result = await bridge._validate_ai_result(ai_result, sample_issue)
        assert result is not None
        fixed, explanation, confidence, changes, side_effects = result
        assert fixed == "x = 1"
        assert explanation == "e"
        assert confidence == 0.9
        assert changes == ["c1"]
        assert side_effects == ["s1"]

    async def test_captures_error_msg_on_failure(
        self,
        bridge: ClaudeCodeBridge,
        sample_issue: Issue,
    ) -> None:
        """The AI error string must be captured into a shared attribute, not discarded.

        Bug: at crackerjack/agents/claude_code_bridge.py:501 the value of
        ``ai_result.get("error", ...)`` was bound to a local ``error_msg``
        but never stored anywhere the caller (consult_on_issue) could pick
        it up, so the user saw "Unknown AI error" regardless of cause.
        The fix makes the captured value available via
        ``bridge._last_ai_error`` so the downstream error path can surface
        the real message.
        """
        ai_result = {"success": False, "error": "rate_limit_exceeded: 429"}
        result = await bridge._validate_ai_result(ai_result, sample_issue)
        assert result is None
        assert hasattr(bridge, "_last_ai_error"), (
            "Bridge must expose _last_ai_error so consult_on_issue can"
            " propagate the real AI failure message instead of"
            " the placeholder 'Unknown AI error'."
        )
        assert bridge._last_ai_error == "rate_limit_exceeded: 429"

    async def test_captures_unknown_placeholder_when_error_missing(
        self,
        bridge: ClaudeCodeBridge,
        sample_issue: Issue,
    ) -> None:
        """When the AI result carries no 'error' key, the placeholder is still surfaced."""
        ai_result = {"success": False}
        result = await bridge._validate_ai_result(ai_result, sample_issue)
        assert result is None
        assert getattr(bridge, "_last_ai_error", None) == "Unknown AI error"

    async def test_low_confidence_does_not_pollute_ai_error_attr(
        self,
        bridge: ClaudeCodeBridge,
        sample_issue: Issue,
    ) -> None:
        """Low-confidence path is distinct from success=False: it must not clobber
        ``_last_ai_error`` with a low-confidence signal — those are different
        failure modes.
        """
        bridge._last_ai_error = "previous_real_ai_error"
        ai_result = {
            "success": True,
            "fixed_code": "x = 1",
            "explanation": "shaky but works",
            "confidence": 0.45,
        }
        result = await bridge._validate_ai_result(ai_result, sample_issue)
        assert result is None
        # Low-confidence is NOT an AI error; the captured attribute must remain
        # untouched so we don't lie about the previous failure's cause.
        assert bridge._last_ai_error == "previous_real_ai_error"
