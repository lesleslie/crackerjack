"""Unit tests for QwenCodeBridge.

Covers the bridge wrapper: agent mapping / thresholds, agent availability,
external agent consultation (cache hit, unavailable, success path, dispatch
to every named agent), AI-fixer enablement, AI result validation, file-fix
application, and ``consult_on_issue`` happy / error / low-confidence / dry-run
/ unexpected-exception / AI-unavailable paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    Priority,
)
from crackerjack.agents.qwen_code_bridge import (
    EXTERNAL_CONSULTATION_THRESHOLD,
    QWEN_CODE_AGENT_MAPPING,
    QwenCodeBridge,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def context(tmp_path: Path) -> AgentContext:
    return AgentContext(project_path=tmp_path)


@pytest.fixture
def bridge(context: AgentContext) -> QwenCodeBridge:
    return QwenCodeBridge(context)


@pytest.fixture
def sample_issue() -> Issue:
    return Issue(
        id="issue-123",
        type=IssueType.SECURITY,
        severity=Priority.HIGH,
        message="Possible hardcoded secret",
        file_path="/tmp/example.py",
        line_number=42,
        details=["line 42: SECRET = 'abc'"],
    )


@pytest.fixture
def issue_no_path() -> Issue:
    return Issue(
        id="issue-456",
        type=IssueType.COMPLEXITY,
        severity=Priority.MEDIUM,
        message="Cyclomatic complexity > 15",
        file_path=None,
        line_number=None,
        details=[],
    )


def _make_ai_fixer(ai_result: dict[str, Any]) -> MagicMock:
    """Create a mock object that quacks like FallbackChainCodeFixer."""
    fixer = MagicMock()
    fixer.init = AsyncMock()
    fixer.fix_code_issue = AsyncMock(return_value=ai_result)
    return fixer


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestModuleConstants:
    def test_threshold_value(self) -> None:
        assert EXTERNAL_CONSULTATION_THRESHOLD == 0.8

    def test_mapping_covers_expected_types(self) -> None:
        # Sanity: every IssueType that has entries maps to non-empty lists of strings
        for issue_type, agents in QWEN_CODE_AGENT_MAPPING.items():
            assert isinstance(agents, list)
            assert agents, f"empty agent list for {issue_type}"
            assert all(isinstance(name, str) for name in agents)

    def test_mapping_includes_complexity(self) -> None:
        assert IssueType.COMPLEXITY in QWEN_CODE_AGENT_MAPPING
        assert "refactoring-specialist" in QWEN_CODE_AGENT_MAPPING[IssueType.COMPLEXITY]

    def test_mapping_includes_security(self) -> None:
        assert "security-auditor" in QWEN_CODE_AGENT_MAPPING[IssueType.SECURITY]


# ---------------------------------------------------------------------------
# Init + threshold + mapping helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQwenCodeBridgeInit:
    def test_init_creates_attributes(self, bridge: QwenCodeBridge, context: AgentContext) -> None:
        assert bridge.context is context
        assert bridge.ai_fixer is None
        assert bridge._consultation_cache == {}
        # ai availability is module-level; either True or False is fine, just truthy/falsy semantics
        assert isinstance(bridge._ai_available, bool)

    def test_init_logs_warning_when_ai_unavailable(
        self,
        context: AgentContext,
    ) -> None:
        with patch("crackerjack.agents.qwen_code_bridge._qwen_ai_available", False):
            bridge = QwenCodeBridge(context)
        # No exception means logger.warning was called (or skipped) - just assert construction
        assert bridge._ai_available is False

    def test_init_does_not_create_ai_fixer(self, bridge: QwenCodeBridge) -> None:
        assert bridge.ai_fixer is None

    def test_get_agent_mapping_returns_module_constant(self, bridge: QwenCodeBridge) -> None:
        assert bridge._get_agent_mapping() is QWEN_CODE_AGENT_MAPPING

    def test_get_consultation_threshold(self, bridge: QwenCodeBridge) -> None:
        assert bridge._get_consultation_threshold() == EXTERNAL_CONSULTATION_THRESHOLD


# ---------------------------------------------------------------------------
# should_consult_external_agent / get_recommended_external_agents
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestShouldConsultExternalAgent:
    @pytest.mark.parametrize(
        "confidence",
        [EXTERNAL_CONSULTATION_THRESHOLD, 0.9, 0.99, 1.0],
    )
    def test_high_confidence_never_consults(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
        confidence: float,
    ) -> None:
        assert bridge.should_consult_external_agent(sample_issue, confidence) is False

    def test_low_confidence_consults_for_known_type(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        # SECURITY is in the mapping
        assert bridge.should_consult_external_agent(sample_issue, 0.5) is True

    def test_low_confidence_skips_for_unknown_type(self, bridge: QwenCodeBridge) -> None:
        # REGEX_VALIDATION is not in the mapping
        issue = Issue(
            id="reg-1",
            type=IssueType.REGEX_VALIDATION,
            severity=Priority.LOW,
            message="regex issue",
        )
        assert bridge.should_consult_external_agent(issue, 0.3) is False

    def test_boundary_below_threshold_consults(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        # Just under threshold -> consult (only for known types)
        assert bridge.should_consult_external_agent(sample_issue, 0.79) is True


@pytest.mark.unit
class TestGetRecommendedExternalAgents:
    def test_known_type_returns_agents(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        agents = bridge.get_recommended_external_agents(sample_issue)
        assert "security-auditor" in agents

    def test_unknown_type_returns_empty_list(self, bridge: QwenCodeBridge) -> None:
        issue = Issue(
            id="reg-1",
            type=IssueType.REGEX_VALIDATION,
            severity=Priority.LOW,
            message="regex",
        )
        assert bridge.get_recommended_external_agents(issue) == []


# ---------------------------------------------------------------------------
# verify_agent_availability
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestVerifyAgentAvailability:
    def test_returns_true_when_agent_file_exists(
        self,
        bridge: QwenCodeBridge,
        tmp_path: Path,
    ) -> None:
        with patch.object(bridge, "_agent_path", tmp_path):
            (tmp_path / "python-pro.md").write_text("# python-pro")
            assert bridge.verify_agent_availability("python-pro") is True

    def test_returns_false_when_agent_file_missing(
        self,
        bridge: QwenCodeBridge,
        tmp_path: Path,
    ) -> None:
        with patch.object(bridge, "_agent_path", tmp_path):
            assert bridge.verify_agent_availability("nonexistent-agent") is False


# ---------------------------------------------------------------------------
# consult_external_agent
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConsultExternalAgent:
    async def test_unavailable_agent_returns_unavailable_status(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
        tmp_path: Path,
    ) -> None:
        with patch.object(bridge, "_agent_path", tmp_path):
            result = await bridge.consult_external_agent(
                sample_issue,
                "missing-agent",
            )
        assert result == {"status": "unavailable", "recommendations": []}
        # Failed consultations must not pollute the cache
        assert bridge._consultation_cache == {}

    async def test_cache_hit_skips_generation(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        cached = {
            "status": "success",
            "agent": "security-auditor",
            "issue_type": "security",
            "recommendations": ["cached-rec"],
            "patterns": [],
            "validation_steps": [],
            "confidence": 0.99,
        }
        with patch.object(bridge, "verify_agent_availability", return_value=True), patch.object(
            bridge,
            "_generate_agent_consultation",
            new=AsyncMock(return_value={"status": "different"}),
        ) as gen:
            bridge._consultation_cache[
                f"security-auditor:{sample_issue.type.value}:{sample_issue.file_path}:{sample_issue.line_number}"
            ] = cached
            result = await bridge.consult_external_agent(sample_issue, "security-auditor")
        assert result is cached
        gen.assert_not_called()

    async def test_successful_consultation_is_cached(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        consultation = {
            "status": "success",
            "agent": "security-auditor",
            "issue_type": "security",
            "recommendations": ["do X"],
            "patterns": [],
            "validation_steps": [],
            "confidence": 0.9,
        }
        with patch.object(bridge, "verify_agent_availability", return_value=True), patch.object(
            bridge,
            "_generate_agent_consultation",
            new=AsyncMock(return_value=consultation),
        ):
            result = await bridge.consult_external_agent(sample_issue, "security-auditor")
        assert result == consultation
        assert len(bridge._consultation_cache) == 1

    async def test_non_successful_consultation_is_not_cached(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        consultation = {
            "status": "error",
            "agent": "security-auditor",
            "recommendations": [],
        }
        with patch.object(bridge, "verify_agent_availability", return_value=True), patch.object(
            bridge,
            "_generate_agent_consultation",
            new=AsyncMock(return_value=consultation),
        ):
            result = await bridge.consult_external_agent(sample_issue, "security-auditor")
        assert result is consultation
        assert bridge._consultation_cache == {}


# ---------------------------------------------------------------------------
# _generate_agent_consultation dispatch
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGenerateAgentConsultationDispatch:
    async def test_dispatches_to_crackerjack_architect(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        with patch.object(
            bridge,
            "_consult_crackerjack_architect",
            new=AsyncMock(return_value={"recommendations": ["a"]}),
        ) as m:
            result = await bridge._generate_agent_consultation(
                sample_issue,
                "crackerjack-architect",
            )
        m.assert_awaited_once()
        assert "a" in result["recommendations"]

    async def test_dispatches_to_python_pro(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        with patch.object(
            bridge,
            "_consult_python_pro",
            new=AsyncMock(return_value={"recommendations": ["b"]}),
        ) as m:
            result = await bridge._generate_agent_consultation(sample_issue, "python-pro")
        m.assert_awaited_once()
        assert "b" in result["recommendations"]

    async def test_dispatches_to_security_auditor(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        with patch.object(
            bridge,
            "_consult_security_auditor",
            new=AsyncMock(return_value={"recommendations": ["c"]}),
        ) as m:
            result = await bridge._generate_agent_consultation(
                sample_issue,
                "security-auditor",
            )
        m.assert_awaited_once()
        assert "c" in result["recommendations"]

    async def test_dispatches_to_refactoring_specialist(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        with patch.object(
            bridge,
            "_consult_refactoring_specialist",
            new=AsyncMock(return_value={"patterns": ["p"]}),
        ) as m:
            result = await bridge._generate_agent_consultation(
                sample_issue,
                "refactoring-specialist",
            )
        m.assert_awaited_once()
        assert "p" in result["patterns"]

    async def test_dispatches_to_test_specialist(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        with patch.object(
            bridge,
            "_consult_test_specialist",
            new=AsyncMock(return_value={"patterns": ["t"]}),
        ) as m:
            result = await bridge._generate_agent_consultation(
                sample_issue,
                "crackerjack-test-specialist",
            )
        m.assert_awaited_once()
        assert "t" in result["patterns"]

    async def test_unknown_agent_falls_back_to_generic(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        with patch.object(
            bridge,
            "_consult_generic_agent",
            new=AsyncMock(return_value={"recommendations": ["g"]}),
        ) as m:
            result = await bridge._generate_agent_consultation(
                sample_issue,
                "no-such-agent",
            )
        m.assert_awaited_once()
        assert "g" in result["recommendations"]
        # Generic dispatch should be passed the agent name
        _, kwargs = m.call_args
        assert kwargs.get("agent_name") == "no-such-agent" or m.call_args[0][1] == "no-such-agent"

    async def test_consultation_envelope_includes_agent_and_type(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        with patch.object(bridge, "_consult_generic_agent", new=AsyncMock(return_value={})):
            result = await bridge._generate_agent_consultation(
                sample_issue,
                "no-such-agent",
            )
        assert result["status"] == "success"
        assert result["agent"] == "no-such-agent"
        assert result["issue_type"] == sample_issue.type.value
        assert result["recommendations"] == []
        assert result["patterns"] == []
        assert result["validation_steps"] == []
        assert result["confidence"] == 0.9


# ---------------------------------------------------------------------------
# Per-agent consultation helpers - shape assertions
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPerAgentConsultationHelpers:
    async def test_crackerjack_architect(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        result = await bridge._consult_crackerjack_architect(sample_issue)
        assert "Apply clean code principles" in result["recommendations"][0]
        assert "extract_method" in result["patterns"]
        assert "run_complexity_check" in result["validation_steps"]

    async def test_python_pro(self, bridge: QwenCodeBridge, sample_issue: Issue) -> None:
        result = await bridge._consult_python_pro(sample_issue)
        assert "Python 3.13" in result["recommendations"][0]
        assert "type_annotations" in result["patterns"]
        assert "run_type_checking" in result["validation_steps"]

    async def test_security_auditor(self, bridge: QwenCodeBridge, sample_issue: Issue) -> None:
        result = await bridge._consult_security_auditor(sample_issue)
        assert "hardcoded" in result["recommendations"][0].lower()
        assert "secure_temp_files" in result["patterns"]
        assert "run_security_scan" in result["validation_steps"]

    async def test_refactoring_specialist(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        result = await bridge._consult_refactoring_specialist(sample_issue)
        assert "complex" in result["recommendations"][0].lower()
        assert "extract_method" in result["patterns"]
        assert "measure_complexity_reduction" in result["validation_steps"]

    async def test_test_specialist(self, bridge: QwenCodeBridge, sample_issue: Issue) -> None:
        result = await bridge._consult_test_specialist(sample_issue)
        assert "async" in result["recommendations"][0].lower()
        assert "synchronous_tests" in result["patterns"]
        assert "run_test_suite" in result["validation_steps"]

    async def test_generic_agent(self, bridge: QwenCodeBridge, sample_issue: Issue) -> None:
        result = await bridge._consult_generic_agent(sample_issue, "ad-hoc-agent")
        assert "ad-hoc-agent" in result["recommendations"][0]
        assert result["patterns"] == ["domain_specific_patterns"]
        assert result["validation_steps"] == ["validate_domain_requirements"]


# ---------------------------------------------------------------------------
# _ensure_ai_fixer
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEnsureAiFixer:
    async def test_raises_when_ai_not_available(self, bridge: QwenCodeBridge) -> None:
        bridge._ai_available = False
        with pytest.raises(RuntimeError, match="Qwen AI adapter not available"):
            await bridge._ensure_ai_fixer()

    async def test_creates_ai_fixer_when_available(self, bridge: QwenCodeBridge) -> None:
        bridge._ai_available = True
        bridge.ai_fixer = None
        fake = MagicMock()
        fake.init = AsyncMock()
        with patch(
            "crackerjack.adapters.ai.unified.FallbackChainCodeFixer",
            return_value=fake,
        ):
            result = await bridge._ensure_ai_fixer()
        assert result is fake
        fake.init.assert_awaited_once()
        assert bridge.ai_fixer is fake

    async def test_returns_existing_ai_fixer(self, bridge: QwenCodeBridge) -> None:
        bridge._ai_available = True
        existing = MagicMock()
        bridge.ai_fixer = existing
        # Even if init would be needed, the cached instance is returned without
        # touching the underlying class
        with patch(
            "crackerjack.adapters.ai.unified.FallbackChainCodeFixer",
        ) as ctor:
            result = await bridge._ensure_ai_fixer()
        assert result is existing
        ctor.assert_not_called()


# ---------------------------------------------------------------------------
# _extract_ai_response_fields
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractAiResponseFields:
    def test_defaults_when_keys_missing(self, bridge: QwenCodeBridge) -> None:
        fixed, explanation, confidence, changes, side_effects = (
            bridge._extract_ai_response_fields({})
        )
        assert fixed == ""
        assert explanation == "No explanation"
        assert confidence == 0.0
        assert changes == []
        assert side_effects == []

    def test_returns_typed_values(self, bridge: QwenCodeBridge) -> None:
        fixed, explanation, confidence, changes, side_effects = (
            bridge._extract_ai_response_fields(
                {
                    "fixed_code": 123,  # coerced to str
                    "explanation": "ok",
                    "confidence": "0.85",  # coerced to float
                    "changes_made": ["c1"],
                    "potential_side_effects": ["s1"],
                },
            )
        )
        assert fixed == "123"
        assert explanation == "ok"
        assert confidence == 0.85
        assert changes == ["c1"]
        assert side_effects == ["s1"]


# ---------------------------------------------------------------------------
# _validate_ai_result
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateAiResult:
    async def test_returns_none_when_ai_result_failed(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        ai_result = {"success": False, "error": "boom"}
        result = await bridge._validate_ai_result(ai_result, sample_issue)
        assert result is None

    async def test_returns_none_when_confidence_below_threshold(
        self,
        bridge: QwenCodeBridge,
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
        bridge: QwenCodeBridge,
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


# ---------------------------------------------------------------------------
# _apply_fix_to_file + _apply_ai_fix
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestApplyFixToFile:
    async def test_passes_through_to_file_modifier(
        self,
        bridge: QwenCodeBridge,
    ) -> None:
        expected = {"success": True}
        with patch.object(
            bridge.file_modifier,
            "apply_fix",
            new=AsyncMock(return_value=expected),
        ) as m:
            result = await bridge._apply_fix_to_file(
                "/tmp/a.py",
                "x = 1",
                dry_run=True,
            )
        assert result is expected
        m.assert_awaited_once_with(
            file_path="/tmp/a.py",
            fixed_content="x = 1",
            dry_run=True,
            create_backup=True,
        )


@pytest.mark.unit
class TestApplyAiFix:
    async def test_successful_fix_returns_fix_result(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        with patch.object(
            bridge,
            "_apply_fix_to_file",
            new=AsyncMock(return_value={"success": True}),
        ):
            result = await bridge._apply_ai_fix(
                file_path="/tmp/a.py",
                fixed_code="x = 1",
                confidence=0.9,
                changes_made=["c1"],
                potential_side_effects=["s1"],
                fix_type="security",
                issue=sample_issue,
                dry_run=False,
            )
        assert result.success is True
        assert result.confidence == 0.9
        assert result.files_modified == ["/tmp/a.py"]
        assert result.recommendations[0] == sample_issue.message
        # The remaining recommendations should include changes/side-effects
        assert any("c1" in r for r in result.recommendations)
        assert any("s1" in r for r in result.recommendations)

    async def test_file_mod_failure_returns_failure_result(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        with patch.object(
            bridge,
            "_apply_fix_to_file",
            new=AsyncMock(return_value={"success": False, "error": "disk full"}),
        ):
            result = await bridge._apply_ai_fix(
                file_path="/tmp/a.py",
                fixed_code="x = 1",
                confidence=0.9,
                changes_made=[],
                potential_side_effects=[],
                fix_type="security",
                issue=sample_issue,
                dry_run=False,
            )
        assert result.success is False
        assert result.files_modified == []
        assert result.fixes_applied == []
        assert "disk full" in result.recommendations[0]


# ---------------------------------------------------------------------------
# consult_on_issue end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConsultOnIssue:
    async def test_happy_path_writes_file(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
        tmp_path: Path,
    ) -> None:
        bridge._ai_available = True
        fake_fixer = _make_ai_fixer(
            {
                "success": True,
                "fixed_code": "SECRET = os.environ['S']",
                "explanation": "use env var",
                "confidence": 0.9,
                "changes_made": ["replace literal"],
                "potential_side_effects": ["env must be set"],
            },
        )
        bridge.ai_fixer = fake_fixer
        target = tmp_path / "victim.py"
        target.write_text("SECRET = 'abc'\n", encoding="utf-8")
        sample_issue.file_path = str(target)

        with patch.object(bridge, "_apply_fix_to_file", new=AsyncMock(return_value={"success": True})):
            result = await bridge.consult_on_issue(sample_issue)

        assert result.success is True
        assert result.confidence == 0.9
        assert result.files_modified == [str(target)]
        fake_fixer.fix_code_issue.assert_awaited_once()

    async def test_ai_error_response_returns_failure(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        bridge._ai_available = True
        bridge.ai_fixer = _make_ai_fixer(
            {"success": False, "error": "rate limited"},
        )
        result = await bridge.consult_on_issue(sample_issue)
        assert result.success is False
        assert result.confidence == 0.0
        assert "rate limited" in result.recommendations[0]

    async def test_low_confidence_returns_low_confidence_response(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        bridge._ai_available = True
        bridge.ai_fixer = _make_ai_fixer(
            {
                "success": True,
                "fixed_code": "x = 1",
                "explanation": "weak",
                "confidence": 0.4,
            },
        )
        result = await bridge.consult_on_issue(sample_issue)
        assert result.success is False
        assert result.confidence == 0.4
        assert "0.40" in result.recommendations[0]
        assert result.files_modified == []

    async def test_dry_run_does_not_write_file(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
        tmp_path: Path,
    ) -> None:
        bridge._ai_available = True
        bridge.ai_fixer = _make_ai_fixer(
            {
                "success": True,
                "fixed_code": "x = 1",
                "explanation": "ok",
                "confidence": 0.95,
                "changes_made": ["c1"],
            },
        )
        target = tmp_path / "victim.py"
        target.write_text("x = 2\n", encoding="utf-8")
        sample_issue.file_path = str(target)

        with patch.object(bridge, "_apply_fix_to_file", new=AsyncMock()) as m:
            result = await bridge.consult_on_issue(sample_issue, dry_run=True)
        m.assert_not_called()
        # File must remain unchanged
        assert target.read_text(encoding="utf-8") == "x = 2\n"
        assert result.success is True
        assert result.files_modified == []
        assert result.remaining_issues == [sample_issue.id]

    async def test_empty_fixed_code_falls_through_to_dry_run(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
        tmp_path: Path,
    ) -> None:
        """An empty fixed_code in non-dry-run mode should not write anything."""
        bridge._ai_available = True
        bridge.ai_fixer = _make_ai_fixer(
            {
                "success": True,
                "fixed_code": "",
                "explanation": "nothing to change",
                "confidence": 0.9,
                "changes_made": ["noop"],
            },
        )
        target = tmp_path / "victim.py"
        target.write_text("x = 1\n", encoding="utf-8")
        sample_issue.file_path = str(target)

        with patch.object(bridge, "_apply_fix_to_file", new=AsyncMock()) as m:
            result = await bridge.consult_on_issue(sample_issue)
        m.assert_not_called()
        assert result.success is True
        assert result.files_modified == []

    async def test_unexpected_exception_is_caught(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        bridge._ai_available = True
        bridge.ai_fixer = MagicMock()
        bridge.ai_fixer.init = AsyncMock()
        bridge.ai_fixer.fix_code_issue = AsyncMock(side_effect=RuntimeError("kaboom"))

        result = await bridge.consult_on_issue(sample_issue)
        assert result.success is False
        assert result.confidence == 0.0
        assert "kaboom" in result.recommendations[0]
        assert result.files_modified == []

    async def test_ai_adapter_unavailable_returns_runtime_error(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        bridge._ai_available = False
        result = await bridge.consult_on_issue(sample_issue)
        assert result.success is False
        assert result.confidence == 0.0
        assert "Qwen AI adapter not available" in result.recommendations[0]

    async def test_issue_without_file_path_uses_unknown(
        self,
        bridge: QwenCodeBridge,
        issue_no_path: Issue,
    ) -> None:
        bridge._ai_available = True
        bridge.ai_fixer = _make_ai_fixer(
            {
                "success": True,
                "fixed_code": "x = 1",
                "explanation": "ok",
                "confidence": 0.9,
                "changes_made": ["c"],
            },
        )
        with patch.object(bridge, "_apply_fix_to_file", new=AsyncMock(return_value={"success": True})):
            result = await bridge.consult_on_issue(issue_no_path)
        # file_path defaults to "unknown"; the call should still complete
        assert result.success is True
        assert "unknown" in result.files_modified[0]
        # The fixer should have been called with file_path="unknown"
        bridge.ai_fixer.fix_code_issue.assert_awaited_once()
        call_kwargs = bridge.ai_fixer.fix_code_issue.call_args.kwargs
        assert call_kwargs["file_path"] == "unknown"
        assert call_kwargs["fix_type"] == issue_no_path.type.value

    async def test_issue_with_details_joins_snippet(
        self,
        bridge: QwenCodeBridge,
        sample_issue: Issue,
    ) -> None:
        bridge._ai_available = True
        bridge.ai_fixer = _make_ai_fixer(
            {
                "success": True,
                "fixed_code": "x = 1",
                "explanation": "ok",
                "confidence": 0.9,
                "changes_made": ["c"],
            },
        )
        with patch.object(bridge, "_apply_fix_to_file", new=AsyncMock(return_value={"success": True})):
            await bridge.consult_on_issue(sample_issue)
        call_kwargs = bridge.ai_fixer.fix_code_issue.call_args.kwargs
        # sample_issue.details has one entry, joined with newline
        assert "SECRET = 'abc'" in call_kwargs["code_context"]
        assert call_kwargs["issue_description"] == sample_issue.message


# ---------------------------------------------------------------------------
# create_enhanced_fix_result
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateEnhancedFixResult:
    def test_no_consultations_returns_copy_of_base(
        self,
        bridge: QwenCodeBridge,
    ) -> None:
        base = FixResult(
            success=True,
            confidence=0.5,
            fixes_applied=["a"],
            remaining_issues=["i1"],
            recommendations=["r1"],
            files_modified=["f1"],
        )
        result = bridge.create_enhanced_fix_result(base, [])
        assert result is not base
        assert result.success is True
        assert result.confidence == 0.5
        assert result.fixes_applied == ["a"]
        assert result.remaining_issues == ["i1"]
        assert result.recommendations == ["r1"]
        assert result.files_modified == ["f1"]
        # mutating enhanced must not leak back to base
        result.fixes_applied.append("z")
        assert base.fixes_applied == ["a"]

    def test_successful_consultation_increases_confidence(
        self,
        bridge: QwenCodeBridge,
    ) -> None:
        base = FixResult(success=True, confidence=0.5)
        consultations = [
            {
                "status": "success",
                "agent": "python-pro",
                "recommendations": ["use X", "use Y"],
                "confidence": 0.9,
            },
        ]
        result = bridge.create_enhanced_fix_result(base, consultations)
        # Recommendations are appended as "[agent] rec"
        assert "[python-pro] use X" in result.recommendations
        assert "[python-pro] use Y" in result.recommendations
        # Confidence is recomputed via max(base, average(base, external))
        # max(0.5, (0.5 + 0.9) / 2) = max(0.5, 0.7) = 0.7
        assert result.confidence == pytest.approx(0.7)

    def test_failed_consultation_is_ignored(
        self,
        bridge: QwenCodeBridge,
    ) -> None:
        base = FixResult(success=True, confidence=0.5, recommendations=["base-rec"])
        consultations = [
            {
                "status": "error",
                "agent": "python-pro",
                "recommendations": ["should not appear"],
                "confidence": 0.99,
            },
        ]
        result = bridge.create_enhanced_fix_result(base, consultations)
        assert result.recommendations == ["base-rec"]
        assert result.confidence == 0.5

    def test_mixed_consultations_only_use_successful(
        self,
        bridge: QwenCodeBridge,
    ) -> None:
        base = FixResult(success=True, confidence=0.4, recommendations=[])
        consultations = [
            {
                "status": "error",
                "agent": "python-pro",
                "recommendations": ["bad"],
                "confidence": 0.99,
            },
            {
                "status": "success",
                "agent": "security-auditor",
                "recommendations": ["rotate keys"],
                "confidence": 0.8,
            },
        ]
        result = bridge.create_enhanced_fix_result(base, consultations)
        assert "[security-auditor] rotate keys" in result.recommendations
        assert not any("python-pro" in r for r in result.recommendations)
        # max(0.4, (0.4 + 0.8) / 2) = max(0.4, 0.6) = 0.6
        assert result.confidence == pytest.approx(0.6)

    def test_consultation_without_agent_uses_unknown_label(
        self,
        bridge: QwenCodeBridge,
    ) -> None:
        base = FixResult(success=True, confidence=0.5)
        consultations = [
            {
                "status": "success",
                # no "agent" key
                "recommendations": ["noop"],
                "confidence": 0.5,
            },
        ]
        result = bridge.create_enhanced_fix_result(base, consultations)
        assert "[unknown] noop" in result.recommendations

    def test_copies_all_mutable_fields(
        self,
        bridge: QwenCodeBridge,
    ) -> None:
        base = FixResult(
            success=False,
            confidence=0.0,
            fixes_applied=["f1"],
            remaining_issues=["r1"],
            recommendations=["rec1"],
            files_modified=["file1"],
        )
        enhanced = bridge.create_enhanced_fix_result(base, [])
        # The lists must be copies
        for attr in ("fixes_applied", "remaining_issues", "recommendations", "files_modified"):
            assert getattr(enhanced, attr) == getattr(base, attr)
            assert getattr(enhanced, attr) is not getattr(base, attr)
