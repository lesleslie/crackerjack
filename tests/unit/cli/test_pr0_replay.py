from __future__ import annotations

import json
from pathlib import Path

import pytest
from rich.console import Console

from crackerjack.cli.replay import main as replay_main
from crackerjack.cli.replay import render_replay
from crackerjack.core.ai_fix_sinks import JsonlSink


RUN_ID = "2026-07-07-1200-abcd"


def _populate_run(tmp_path: Path, run_id: str) -> None:
    sink = JsonlSink(base_dir=tmp_path)
    import asyncio

    from crackerjack.core.ai_fix_events import (
        AgentDispatched,
        FixSessionFinished,
        FixSessionStarted,
        IssueResolved,
        IterationFinished,
        IterationStarted,
        RunFinished,
        RunStarted,
    )

    async def emit() -> None:
        await sink.handle(RunStarted(run_id=run_id, iteration=0, stage="comprehensive", initial_issue_count=3))
        await sink.handle(IterationStarted(run_id=run_id, iteration=0, strategy="balanced", issue_count=3))
        await sink.handle(
            AgentDispatched(
                run_id=run_id,
                iteration=0,
                agent="RefactoringAgent",
                action="fix",
                file="a.py",
                issue_type="TYPE_ERROR",
            )
        )
        await sink.handle(
            FixSessionStarted(
                run_id=run_id,
                iteration=0,
                issue_signature="sig-1",
                file="a.py",
                issue_type="TYPE_ERROR",
            )
        )
        await sink.handle(
            IssueResolved(
                run_id=run_id,
                iteration=0,
                agent="RefactoringAgent",
                file="a.py",
                duration_s=1.5,
                issue_type="TYPE_ERROR",
            )
        )
        await sink.handle(
            FixSessionFinished(
                run_id=run_id,
                iteration=0,
                issue_signature="sig-1",
                file="a.py",
                success=True,
                final_tier=1,
                total_duration_s=1.5,
                no_op_count=0,
            )
        )
        await sink.handle(
            IterationFinished(run_id=run_id, iteration=0, resolved=1, failed=0, success=True)
        )
        await sink.handle(
            RunFinished(run_id=run_id, iteration=0, success=True, total_iterations=1)
        )
        sink.close()

    asyncio.run(emit())


class TestReplayRenders:
    def test_replay_returns_0_for_existing_run(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _populate_run(tmp_path, RUN_ID)
        rc = render_replay(RUN_ID, base_dir=tmp_path, console=Console(force_terminal=False))
        assert rc == 0

    def test_replay_returns_1_for_missing_run(self, tmp_path: Path) -> None:
        rc = render_replay("nonexistent", base_dir=tmp_path, console=Console(force_terminal=False))
        assert rc == 1

    def test_replay_prints_summary_table(self, tmp_path: Path) -> None:
        _populate_run(tmp_path, RUN_ID)
        # Use a recording console so we can introspect output.
        console = Console(force_terminal=False, width=120, record=True)
        render_replay(RUN_ID, base_dir=tmp_path, console=console)
        output = console.export_text()
        # The summary table should mention the run-level metrics we emit.
        assert "iterations started" in output
        assert "issues resolved" in output
        assert "fix sessions" in output


class TestReplayCliMain:
    def test_main_with_missing_run(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc = replay_main(["nonexistent", "--base-dir", str(tmp_path)])
        assert rc == 1

    def test_main_with_existing_run(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _populate_run(tmp_path, RUN_ID)
        rc = replay_main([RUN_ID, "--base-dir", str(tmp_path)])
        assert rc == 0
        captured = capsys.readouterr()
        # The output should contain the resolved-event marker.
        assert "resolved" in captured.out or "RUN FINISHED" in captured.out