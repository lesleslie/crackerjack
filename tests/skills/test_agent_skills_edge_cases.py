"""Edge-case and failure-path tests for crackerjack.skills.agent_skills.

Targets the ~186-statement module that registers and dispatches agent
skills.  Happy paths are already covered in test_agent_skills.py; this
file focuses on the negative branches that drive coverage: timeouts,
exceptions, missing-skill lookups, and the inferred-metadata helpers.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    Priority,
    SubAgent,
)
from crackerjack.skills.agent_skills import (
    AgentSkill,
    AgentSkillRegistry,
    SkillCategory,
    SkillExecutionResult,
    SkillMetadata,
)


# --------------------------------------------------------------------------- #
# Local fixtures (scoped to this file to avoid coupling to test_agent_skills)
# --------------------------------------------------------------------------- #


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    return tmp_path / "edge_project"


@pytest.fixture
def ctx(project_path: Path) -> AgentContext:
    return AgentContext(
        project_path=project_path,
        temp_dir=project_path / "temp",
        subprocess_timeout=10,
    )


@pytest.fixture
def complexity_issue() -> Issue:
    return Issue(
        type=IssueType.COMPLEXITY,
        severity=Priority.HIGH,
        message="too complex",
        file_path="m.py",
        line_number=10,
    )


@pytest.fixture
def metadata() -> SkillMetadata:
    return SkillMetadata(
        name="TestAgent",
        description="desc",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
        confidence_threshold=0.7,
    )


def _agent_with_execute(
    name: str,
    *,
    return_value: object | None = None,
    side_effect: BaseException | None = None,
    supports: set[IssueType] | None = None,
    can_handle: float = 0.9,
) -> MagicMock:
    """Build a mock SubAgent that exposes ``execute`` (not ``analyze_and_fix``)."""
    agent = MagicMock(spec=SubAgent)
    agent.name = name
    if side_effect is not None:
        agent.execute = AsyncMock(side_effect=side_effect)
    else:
        agent.execute = AsyncMock(return_value=return_value)
    agent.can_handle = AsyncMock(return_value=can_handle)
    agent.get_supported_types = Mock(return_value=supports or {IssueType.COMPLEXITY})
    return agent


# --------------------------------------------------------------------------- #
# AgentSkill.can_handle — confidence below threshold
# --------------------------------------------------------------------------- #


@pytest.mark.unit
async def test_can_handle_below_threshold_returns_zero() -> None:
    """Agent confidence below metadata.confidence_threshold → 0.0."""
    agent = MagicMock(spec=SubAgent)
    agent.name = "LowConf"
    agent.can_handle = AsyncMock(return_value=0.5)  # threshold is 0.7
    agent.get_supported_types = Mock(return_value={IssueType.COMPLEXITY})

    md = SkillMetadata(
        name="LowConf",
        description="x",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
        confidence_threshold=0.7,
    )
    skill = AgentSkill(agent, md)

    issue = Issue(type=IssueType.COMPLEXITY, severity=Priority.LOW, message="x")
    confidence = await skill.can_handle(issue)

    assert confidence == 0.0
    agent.can_handle.assert_awaited_once_with(issue)


@pytest.mark.unit
async def test_can_handle_unsupported_type_does_not_call_agent() -> None:
    """Issue type not in supported_types → returns 0.0 without invoking agent."""
    agent = MagicMock(spec=SubAgent)
    agent.name = "X"
    agent.can_handle = AsyncMock(return_value=0.99)
    agent.get_supported_types = Mock(return_value={IssueType.COMPLEXITY})

    md = SkillMetadata(
        name="X",
        description="x",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )
    skill = AgentSkill(agent, md)

    issue = Issue(type=IssueType.SECURITY, severity=Priority.LOW, message="x")
    assert await skill.can_handle(issue) == 0.0
    agent.can_handle.assert_not_called()


# --------------------------------------------------------------------------- #
# AgentSkill.execute — error/timeout/result-shape branches
# --------------------------------------------------------------------------- #


@pytest.mark.unit
async def test_execute_raises_when_agent_has_neither_method() -> None:
    """Agent lacking both execute() and analyze_and_fix() → AttributeError surfaced."""
    agent = MagicMock(spec=SubAgent)
    agent.name = "Bare"
    # No execute / no analyze_and_fix attributes on the instance.
    del agent.execute
    del agent.analyze_and_fix
    agent.can_handle = AsyncMock(return_value=0.9)
    agent.get_supported_types = Mock(return_value={IssueType.COMPLEXITY})

    md = SkillMetadata(
        name="Bare",
        description="x",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )
    skill = AgentSkill(agent, md)

    issue = Issue(type=IssueType.COMPLEXITY, severity=Priority.LOW, message="x")
    result = await skill.execute(issue)

    assert result.success is False
    assert result.issues_handled == 0
    assert any("execute()" in r or "analyze_and_fix" in r for r in result.recommendations)
    # execution_count is incremented only on the success dict/object paths,
    # not on the AttributeError path.
    assert md.execution_count == 0


@pytest.mark.unit
async def test_execute_timeout_returns_failure_result() -> None:
    """asyncio.TimeoutError → SkillExecutionResult with success=False, no count bump."""
    agent = _agent_with_execute(
        "Slow",
        return_value=FixResult(success=True, confidence=0.9),
    )
    # Make execute() hang past the timeout.
    async def _hang(_issue: object) -> FixResult:
        await asyncio.sleep(0.5)
        return FixResult(success=True)  # pragma: no cover - never reached

    agent.execute = AsyncMock(side_effect=_hang)

    md = SkillMetadata(
        name="Slow",
        description="x",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )
    skill = AgentSkill(agent, md)

    issue = Issue(type=IssueType.COMPLEXITY, severity=Priority.LOW, message="x")
    result = await skill.execute(issue, timeout=0.05)

    assert result.success is False
    assert result.confidence == 0.0
    assert result.issues_handled == 0
    assert any("timed out" in r for r in result.recommendations)
    assert md.execution_count == 0  # not bumped on timeout


@pytest.mark.unit
async def test_execute_generic_exception_returns_failure() -> None:
    """Unhandled exception in agent.execute → SkillExecutionResult(success=False)."""
    boom = RuntimeError("kaboom")
    agent = _agent_with_execute("Boom", side_effect=boom)
    md = SkillMetadata(
        name="Boom",
        description="x",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )
    skill = AgentSkill(agent, md)

    issue = Issue(type=IssueType.COMPLEXITY, severity=Priority.LOW, message="x")
    result = await skill.execute(issue)

    assert result.success is False
    assert result.issues_handled == 0
    assert any("kaboom" in r for r in result.recommendations)
    assert md.execution_count == 0


@pytest.mark.unit
async def test_execute_dict_result_path() -> None:
    """Agent returning a dict (not FixResult) populates fields from dict keys."""
    agent = _agent_with_execute(
        "DictAgent",
        return_value={
            "success": True,
            "confidence": 0.42,
            "fixes_applied": ["f1"],
            "recommendations": ["r1"],
            "files_modified": ["a.py"],
        },
    )
    md = SkillMetadata(
        name="DictAgent",
        description="x",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )
    skill = AgentSkill(agent, md)

    issue = Issue(type=IssueType.COMPLEXITY, severity=Priority.LOW, message="x")
    result = await skill.execute(issue)

    assert result.success is True
    assert result.confidence == 0.42
    assert result.fixes_applied == ["f1"]
    assert result.recommendations == ["r1"]
    assert result.files_modified == ["a.py"]
    assert md.execution_count == 1
    # success_rate moves toward 1.0
    assert md.success_rate > 0.9


@pytest.mark.unit
async def test_execute_failure_does_not_bump_success_rate() -> None:
    """success_rate is an EMA on successes; a failure should not change it."""
    agent = _agent_with_execute(
        "FailAgent",
        return_value=FixResult(success=False, confidence=0.0),
    )
    md = SkillMetadata(
        name="FailAgent",
        description="x",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )
    skill = AgentSkill(agent, md)

    issue = Issue(type=IssueType.COMPLEXITY, severity=Priority.LOW, message="x")
    result = await skill.execute(issue)

    assert result.success is False
    assert md.execution_count == 1
    # success_rate unchanged (initial 1.0)
    assert md.success_rate == 1.0


@pytest.mark.unit
async def test_execute_list_of_issues_passes_batch() -> None:
    """Passing a list of issues to execute() forwards the list to the agent."""
    captured: dict[str, object] = {}

    async def _capture(arg: object) -> FixResult:
        captured["arg"] = arg
        return FixResult(success=True, confidence=0.5)

    agent = MagicMock(spec=SubAgent)
    agent.name = "ListAgent"
    agent.execute = AsyncMock(side_effect=_capture)
    agent.can_handle = AsyncMock(return_value=0.9)
    agent.get_supported_types = Mock(return_value={IssueType.COMPLEXITY})

    md = SkillMetadata(
        name="ListAgent",
        description="x",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )
    skill = AgentSkill(agent, md)

    issues = [
        Issue(type=IssueType.COMPLEXITY, severity=Priority.LOW, message="a"),
        Issue(type=IssueType.COMPLEXITY, severity=Priority.LOW, message="b"),
    ]
    result = await skill.execute(issues)

    assert result.issues_handled == 2
    # When more than one issue, the agent receives the list.
    assert captured["arg"] == issues


@pytest.mark.unit
async def test_execute_uses_analyze_and_fix_when_no_execute() -> None:
    """Agents with analyze_and_fix (no execute) still work."""
    agent = MagicMock(spec=SubAgent)
    agent.name = "LegacyAgent"
    # No execute attribute on the instance.
    if hasattr(agent, "execute"):
        del agent.execute
    agent.analyze_and_fix = AsyncMock(
        return_value=FixResult(
            success=True,
            confidence=0.7,
            fixes_applied=["x"],
            files_modified=["m.py"],
        ),
    )
    agent.can_handle = AsyncMock(return_value=0.9)
    agent.get_supported_types = Mock(return_value={IssueType.COMPLEXITY})

    md = SkillMetadata(
        name="LegacyAgent",
        description="x",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )
    skill = AgentSkill(agent, md)

    issue = Issue(type=IssueType.COMPLEXITY, severity=Priority.LOW, message="x")
    result = await skill.execute(issue)

    assert result.success is True
    assert result.fixes_applied == ["x"]


# --------------------------------------------------------------------------- #
# AgentSkill.batch_execute
# --------------------------------------------------------------------------- #


@pytest.mark.unit
async def test_batch_execute_filters_unsupported_issues() -> None:
    """batch_execute only runs the agent for issues whose type it supports."""
    agent = _agent_with_execute(
        "Filter",
        return_value=FixResult(success=True, confidence=0.5),
    )
    md = SkillMetadata(
        name="Filter",
        description="x",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},  # only complexity
    )
    skill = AgentSkill(agent, md)

    issues = [
        Issue(type=IssueType.COMPLEXITY, severity=Priority.LOW, message="c"),
        Issue(type=IssueType.SECURITY, severity=Priority.LOW, message="s"),
    ]
    results = await skill.batch_execute(issues)

    # Only one issue was actually executed.
    assert len(results) == 1
    assert agent.execute.await_count == 1


@pytest.mark.unit
async def test_batch_execute_handles_exception_in_one_task() -> None:
    """An exception raised in a child task becomes a failure SkillExecutionResult."""

    async def _explode(_issue: object) -> FixResult:
        raise RuntimeError("nope")

    agent = MagicMock(spec=SubAgent)
    agent.name = "Flaky"
    agent.execute = AsyncMock(side_effect=_explode)
    agent.can_handle = AsyncMock(return_value=0.9)
    agent.get_supported_types = Mock(return_value={IssueType.COMPLEXITY})

    md = SkillMetadata(
        name="Flaky",
        description="x",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )
    skill = AgentSkill(agent, md)

    issues = [
        Issue(type=IssueType.COMPLEXITY, severity=Priority.LOW, message="a"),
        Issue(type=IssueType.COMPLEXITY, severity=Priority.LOW, message="b"),
    ]
    results = await skill.batch_execute(issues)

    assert len(results) == 2
    assert all(r.success is False for r in results)


# --------------------------------------------------------------------------- #
# AgentSkill.get_info
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_get_info_returns_expected_shape() -> None:
    agent = _agent_with_execute("InfoAgent")
    md = SkillMetadata(
        name="InfoAgent",
        description="desc",
        category=SkillCategory.SECURITY,
        supported_types={IssueType.SECURITY},
    )
    skill = AgentSkill(agent, md)

    info = skill.get_info()
    assert info["skill_id"] == skill.skill_id
    assert info["agent_name"] == "InfoAgent"
    assert info["metadata"]["name"] == "InfoAgent"
    assert info["metadata"]["category"] == "security"


# --------------------------------------------------------------------------- #
# AgentSkillRegistry
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_registry_get_skill_returns_none_for_missing_id() -> None:
    registry = AgentSkillRegistry()
    assert registry.get_skill("does-not-exist") is None


@pytest.mark.unit
def test_registry_list_all_skills() -> None:
    registry = AgentSkillRegistry()
    agent = _agent_with_execute("L")
    md = SkillMetadata(
        name="L",
        description="x",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )
    registry.register(AgentSkill(agent, md))

    listing = registry.list_all_skills()
    assert len(listing) == 1
    assert listing[0]["metadata"]["name"] == "L"


@pytest.mark.unit
def test_registry_get_statistics_empty() -> None:
    stats = AgentSkillRegistry().get_statistics()
    assert stats["total_skills"] == 0
    assert stats["avg_success_rate"] == 0.0
    assert stats["total_executions"] == 0
    # Indexes still include every category and type.
    assert len(stats["skills_by_category"]) == len(SkillCategory)
    assert set(stats["skills_by_category"]) == {c.value for c in SkillCategory}


@pytest.mark.unit
async def test_find_best_skill_no_candidates_returns_none(
    complexity_issue: Issue,
) -> None:
    """No skills registered for the issue's type → None."""
    registry = AgentSkillRegistry()
    assert await registry.find_best_skill(complexity_issue) is None


@pytest.mark.unit
async def test_find_best_skill_no_valid_pair_returns_none(
    complexity_issue: Issue,
) -> None:
    """Skills exist for the type but none report confidence > 0 → None."""
    registry = AgentSkillRegistry()
    agent = MagicMock(spec=SubAgent)
    agent.name = "ZeroConf"
    agent.can_handle = AsyncMock(return_value=0.0)  # below threshold
    agent.get_supported_types = Mock(return_value={IssueType.COMPLEXITY})

    md = SkillMetadata(
        name="ZeroConf",
        description="x",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
        confidence_threshold=0.5,
    )
    registry.register(AgentSkill(agent, md))

    assert await registry.find_best_skill(complexity_issue) is None


@pytest.mark.unit
def test_register_agent_generates_metadata_when_none_provided(ctx: AgentContext) -> None:
    """Without explicit metadata, registry infers name/category/tags from agent."""

    class _AutoAgent(SubAgent):
        name = "security_checker"

        async def can_handle(self, issue: Issue) -> float:  # pragma: no cover
            return 0.5

        async def analyze_and_fix(self, issue: Issue) -> FixResult:  # pragma: no cover
            return FixResult(success=True)

        def get_supported_types(self) -> set[IssueType]:
            return {IssueType.SECURITY}

    registry = AgentSkillRegistry()
    skill = registry.register_agent(_AutoAgent, ctx)  # type: ignore[arg-type]

    # Inferred from "security" in name.
    assert skill.metadata.category == SkillCategory.SECURITY
    # Description mentions the supported types.
    assert "security" in skill.metadata.description.lower()
    # Inferred tags include words from the agent name + issue-type value.
    assert "security" in skill.metadata.tags
    assert "security" in skill.metadata.tags  # appears via both


@pytest.mark.unit
def test_register_all_agents_swallows_exceptions(ctx: AgentContext) -> None:
    """register_all_agents skips agents whose instantiation/registration fails."""

    class _GoodAgent(SubAgent):
        name = "good"

        async def can_handle(self, issue: Issue) -> float:  # pragma: no cover
            return 0.5

        async def analyze_and_fix(self, issue: Issue) -> FixResult:  # pragma: no cover
            return FixResult(success=True)

        def get_supported_types(self) -> set[IssueType]:
            return set()

    class _BadAgent(SubAgent):
        name = "bad"

        def __init__(self, context: AgentContext) -> None:
            raise RuntimeError("nope")

        async def can_handle(self, issue: Issue) -> float:  # pragma: no cover
            return 0.5

        async def analyze_and_fix(self, issue: Issue) -> FixResult:  # pragma: no cover
            return FixResult(success=True)

        def get_supported_types(self) -> set[IssueType]:
            return set()

    # Seed the module-level agent_registry with a good and a bad agent.
    from crackerjack.agents.base import agent_registry

    agent_registry.register(_GoodAgent)
    agent_registry.register(_BadAgent)
    try:
        registry = AgentSkillRegistry()
        skills = registry.register_all_agents(ctx)
        # Only the good agent registers successfully.
        names = {s.metadata.name for s in skills}
        assert "good" in names
        assert "bad" not in names
    finally:
        # Clean up the global registry so other tests aren't affected.
        agent_registry._agents.pop(_GoodAgent.__name__, None)
        agent_registry._agents.pop(_BadAgent.__name__, None)


# --------------------------------------------------------------------------- #
# _infer_category / _infer_tags / _generate_metadata
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("refactor_helper", SkillCategory.CODE_QUALITY),
        ("complexity_reducer", SkillCategory.CODE_QUALITY),
        ("test_runner", SkillCategory.TESTING),
        ("security_scanner", SkillCategory.SECURITY),
        ("performance_profiler", SkillCategory.PERFORMANCE),
        ("doc_writer", SkillCategory.DOCUMENTATION),
        ("architect_designer", SkillCategory.ARCHITECTURE),
        ("semantic_searcher", SkillCategory.SEMANTIC),
        ("proactive_monitor", SkillCategory.PROACTIVE),
        ("mystery_agent", SkillCategory.CODE_QUALITY),  # fallback
    ],
)
def test_infer_category_branches(name: str, expected: SkillCategory) -> None:
    registry = AgentSkillRegistry()
    assert registry._infer_category(name) is expected


@pytest.mark.unit
def test_infer_tags_combines_words_and_types() -> None:
    registry = AgentSkillRegistry()
    tags = registry._infer_tags(
        "code_helper_v2",
        {IssueType.SECURITY, IssueType.COMPLEXITY},
    )
    # Long words from the agent name get included.
    assert "code" in tags
    assert "helper" in tags
    # Short words like "v2" (len 2) are excluded.
    assert "v2" not in tags
    # Issue-type values are added.
    assert "security" in tags
    assert "complexity" in tags


@pytest.mark.unit
def test_generate_metadata_assembles_skill_metadata(ctx: AgentContext) -> None:
    """_generate_metadata combines inference for category, description, and tags."""

    class _SampleAgent(SubAgent):
        name = "performance_profiler"

        async def can_handle(self, issue: Issue) -> float:  # pragma: no cover
            return 0.5

        async def analyze_and_fix(self, issue: Issue) -> FixResult:  # pragma: no cover
            return FixResult(success=True)

        def get_supported_types(self) -> set[IssueType]:
            return {IssueType.PERFORMANCE}

    agent = _SampleAgent(ctx)
    registry = AgentSkillRegistry()
    md = registry._generate_metadata(agent)

    assert md.name == "performance_profiler"
    assert md.category == SkillCategory.PERFORMANCE
    assert md.supported_types == {IssueType.PERFORMANCE}
    assert "performance" in md.description.lower()
    assert "performance" in md.tags
    assert "profiler" in md.tags


# --------------------------------------------------------------------------- #
# SkillExecutionResult — to_dict structure
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_skill_execution_result_to_dict_round_trip() -> None:
    result = SkillExecutionResult(
        skill_name="S",
        success=False,
        confidence=0.1,
        issues_handled=2,
        fixes_applied=["a", "b"],
        recommendations=["r"],
        files_modified=["f.py"],
        execution_time_ms=42,
    )
    data = result.to_dict()
    assert data == {
        "skill_name": "S",
        "success": False,
        "confidence": 0.1,
        "issues_handled": 2,
        "fixes_applied": ["a", "b"],
        "recommendations": ["r"],
        "files_modified": ["f.py"],
        "execution_time_ms": 42,
    }


@pytest.mark.unit
def test_skill_metadata_default_field_values() -> None:
    """SkillMetadata dataclass defaults are correctly applied."""
    md = SkillMetadata(
        name="x",
        description="y",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )
    assert md.confidence_threshold == 0.7
    assert md.avg_confidence == 0.8
    assert md.execution_count == 0
    assert md.success_rate == 1.0
    assert md.tags == set()
