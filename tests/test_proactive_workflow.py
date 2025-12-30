import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest

from crackerjack.core.proactive_workflow import (
    ArchitecturalAssessment,
    ProactiveWorkflowPipeline,
)


@dataclass
class DummyOptions:
    commit: bool = False
    interactive: bool = False
    no_config_updates: bool = False
    verbose: bool = False
    clean: bool = False
    test: bool = False
    benchmark: bool = False
    test_workers: int = 0
    test_timeout: int = 0
    publish: object | None = None
    bump: object | None = None
    all: object | None = None
    ai_agent: bool = False
    start_mcp_server: bool = False
    create_pr: bool = False
    skip_hooks: bool = False
    async_mode: bool = False
    experimental_hooks: bool = False
    enable_pyrefly: bool = False
    enable_ty: bool = False
    cleanup: object | None = None
    no_git_tags: bool = False
    skip_version_check: bool = False
    cleanup_pypi: bool = False
    coverage: bool = False
    keep_releases: int = 10
    track_progress: bool = False
    fast: bool = False
    comp: bool = False
    fast_iteration: bool = False
    tool: str | None = None
    changed_only: bool = False
    advanced_batch: str | None = None
    monitor_dashboard: str | None = None
    skip_config_merge: bool = False
    disable_global_locks: bool = False
    global_lock_timeout: int = 600
    global_lock_cleanup: bool = True
    global_lock_dir: str | None = None
    generate_docs: bool = False
    docs_format: str = "markdown"
    validate_docs: bool = False
    update_docs_index: bool = False


def test_run_complete_workflow_with_planning_basic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test basic functionality of run_complete_workflow_with_planning."""
    pipeline = ProactiveWorkflowPipeline(project_path=tmp_path)

    async def fake_assessment() -> ArchitecturalAssessment:
        return ArchitecturalAssessment(
            needs_planning=False,
            complexity_score=0,
            potential_issues=[],
            recommended_strategy="standard",
        )

    monkeypatch.setattr(pipeline, "_assess_codebase_architecture", fake_assessment)

    result = asyncio.run(pipeline.run_complete_workflow_with_planning(DummyOptions()))
    assert result is True
