"""Unit tests for MCP state.

Tests state management, session tracking, issue handling,
stage management, and checkpoint functionality.
"""

import json
import time
from pathlib import Path

import pytest

from crackerjack.mcp.state import (
    Issue,
    Priority,
    SessionState,
    StageResult,
    StageStatus,
    StateManager,
)


@pytest.mark.unit
class TestStageStatusEnum:
    """Test StageStatus enum."""

    def test_stage_status_values(self):
        """Test StageStatus enum values."""
        assert StageStatus.PENDING == "pending"
        assert StageStatus.RUNNING == "running"
        assert StageStatus.COMPLETED == "completed"
        assert StageStatus.FAILED == "failed"
        assert StageStatus.ERROR == "error"


@pytest.mark.unit
class TestPriorityEnum:
    """Test Priority enum."""

    def test_priority_values(self):
        """Test Priority enum values."""
        assert Priority.CRITICAL == "critical"
        assert Priority.HIGH == "high"
        assert Priority.MEDIUM == "medium"
        assert Priority.LOW == "low"


@pytest.mark.unit
class TestIssue:
    """Test Issue dataclass."""

    def test_issue_initialization(self):
        """Test Issue initialization."""
        issue = Issue(
            id="issue1",
            type="syntax_error",
            message="Invalid syntax",
            file_path="/path/to/file.py",
            line_number=42,
        )

        assert issue.id == "issue1"
        assert issue.type == "syntax_error"
        assert issue.message == "Invalid syntax"
        assert issue.file_path == "/path/to/file.py"
        assert issue.line_number == 42
        assert issue.priority == Priority.MEDIUM
        assert issue.stage == ""
        assert issue.suggested_fix is None
        assert issue.auto_fixable is False

    def test_issue_with_all_fields(self):
        """Test Issue with all fields specified."""
        issue = Issue(
            id="issue1",
            type="type_error",
            message="Type mismatch",
            file_path="/path/to/file.py",
            line_number=10,
            priority=Priority.HIGH,
            stage="type_checking",
            suggested_fix="Add type annotation",
            auto_fixable=True,
        )

        assert issue.priority == Priority.HIGH
        assert issue.stage == "type_checking"
        assert issue.suggested_fix == "Add type annotation"
        assert issue.auto_fixable is True

    def test_issue_to_dict(self):
        """Test Issue to_dict method."""
        issue = Issue(
            id="issue1",
            type="error",
            message="Test error",
            file_path="/test.py",
        )

        data = issue.to_dict()

        assert data["id"] == "issue1"
        assert data["type"] == "error"
        assert data["message"] == "Test error"
        assert data["file_path"] == "/test.py"


@pytest.mark.unit
class TestStageResult:
    """Test StageResult dataclass."""

    def test_stage_result_initialization(self):
        """Test StageResult initialization."""
        start_time = time.time()
        result = StageResult(
            stage="linting",
            status=StageStatus.RUNNING,
            start_time=start_time,
        )

        assert result.stage == "linting"
        assert result.status == StageStatus.RUNNING
        assert result.start_time == start_time
        assert result.end_time is None
        assert result.duration is None
        assert result.issues_found == []
        assert result.fixes_applied == []
        assert result.error_message is None

    def test_stage_result_with_end_time(self):
        """Test StageResult with end_time calculates duration."""
        start_time = time.time()
        end_time = start_time + 10.5

        result = StageResult(
            stage="testing",
            status=StageStatus.COMPLETED,
            start_time=start_time,
            end_time=end_time,
        )

        assert result.duration == 10.5

    def test_stage_result_to_dict(self):
        """Test StageResult to_dict method."""
        issue = Issue(
            id="issue1",
            type="error",
            message="Test",
            file_path="/test.py",
        )
        result = StageResult(
            stage="testing",
            status=StageStatus.COMPLETED,
            start_time=time.time(),
            issues_found=[issue],
            fixes_applied=["fix1", "fix2"],
        )

        data = result.to_dict()

        assert data["stage"] == "testing"
        assert data["status"] == StageStatus.COMPLETED
        assert len(data["issues_found"]) == 1
        assert data["fixes_applied"] == ["fix1", "fix2"]


@pytest.mark.unit
class TestSessionState:
    """Test SessionState dataclass."""

    def test_session_state_initialization(self):
        """Test SessionState initialization."""
        start_time = time.time()
        state = SessionState(
            session_id="abc123",
            start_time=start_time,
        )

        assert state.session_id == "abc123"
        assert state.start_time == start_time
        assert state.current_stage is None
        assert state.stages == {}
        assert state.global_issues == []
        assert state.fixes_applied == []
        assert state.metadata == {}

    def test_session_state_with_data(self):
        """Test SessionState with data."""
        issue = Issue(id="i1", type="error", message="Test", file_path="/test.py")
        stage_result = StageResult(
            stage="test",
            status=StageStatus.COMPLETED,
            start_time=time.time(),
        )

        state = SessionState(
            session_id="abc123",
            start_time=time.time(),
            current_stage="testing",
            stages={"test": stage_result},
            global_issues=[issue],
            fixes_applied=["fix1"],
            metadata={"key": "value"},
        )

        assert state.current_stage == "testing"
        assert "test" in state.stages
        assert len(state.global_issues) == 1
        assert state.fixes_applied == ["fix1"]
        assert state.metadata == {"key": "value"}

    def test_session_state_to_dict(self):
        """Test SessionState to_dict method."""
        stage_result = StageResult(
            stage="test",
            status=StageStatus.COMPLETED,
            start_time=time.time(),
        )
        state = SessionState(
            session_id="abc123",
            start_time=time.time(),
            stages={"test": stage_result},
        )

        data = state.to_dict()

        assert data["session_id"] == "abc123"
        assert "stages" in data
        assert "test" in data["stages"]


@pytest.mark.unit
class TestStateManagerInitialization:
    """Test StateManager initialization."""

    def test_initialization_default(self, tmp_path):
        """Test default initialization."""
        manager = StateManager(state_dir=tmp_path)

        assert manager.state_dir == tmp_path
        assert tmp_path.exists()
        assert isinstance(manager.session_state, SessionState)
        assert len(manager.session_state.session_id) == 8

    def test_initialization_creates_directories(self, tmp_path):
        """Test initialization creates necessary directories."""
        state_dir = tmp_path / "state"

        manager = StateManager(state_dir=state_dir)

        assert state_dir.exists()
        assert manager.checkpoints_dir.exists()


@pytest.mark.unit
class TestStateManagerStages:
    """Test StateManager stage management."""

    @pytest.mark.asyncio
    async def test_start_stage(self, tmp_path):
        """Test starting a stage."""
        manager = StateManager(state_dir=tmp_path)

        await manager.start_stage("linting")

        assert manager.session_state.current_stage == "linting"
        assert "linting" in manager.session_state.stages
        assert manager.session_state.stages["linting"].status == StageStatus.RUNNING

    @pytest.mark.asyncio
    async def test_complete_stage(self, tmp_path):
        """Test completing a stage."""
        manager = StateManager(state_dir=tmp_path)

        await manager.start_stage("linting")
        await manager.complete_stage("linting")

        assert manager.session_state.current_stage is None
        assert manager.session_state.stages["linting"].status == StageStatus.COMPLETED
        assert manager.session_state.stages["linting"].end_time is not None

    @pytest.mark.asyncio
    async def test_complete_stage_with_issues(self, tmp_path):
        """Test completing stage with issues."""
        manager = StateManager(state_dir=tmp_path)
        issue = Issue(id="i1", type="error", message="Test", file_path="/test.py")

        await manager.start_stage("linting")
        await manager.complete_stage("linting", issues=[issue])

        assert len(manager.session_state.stages["linting"].issues_found) == 1
        assert len(manager.session_state.global_issues) == 1

    @pytest.mark.asyncio
    async def test_complete_stage_with_fixes(self, tmp_path):
        """Test completing stage with fixes."""
        manager = StateManager(state_dir=tmp_path)

        await manager.start_stage("linting")
        await manager.complete_stage("linting", fixes=["fix1", "fix2"])

        assert manager.session_state.stages["linting"].fixes_applied == ["fix1", "fix2"]
        assert manager.session_state.fixes_applied == ["fix1", "fix2"]

    @pytest.mark.asyncio
    async def test_fail_stage(self, tmp_path):
        """Test failing a stage."""
        manager = StateManager(state_dir=tmp_path)

        await manager.start_stage("testing")
        await manager.fail_stage("testing", "Test failed")

        assert manager.session_state.stages["testing"].status == StageStatus.FAILED
        assert manager.session_state.stages["testing"].error_message == "Test failed"
        assert manager.session_state.current_stage is None

    @pytest.mark.asyncio
    async def test_update_stage_status(self, tmp_path):
        """Test updating stage status."""
        manager = StateManager(state_dir=tmp_path)

        await manager.update_stage_status("testing", "running")

        assert "testing" in manager.session_state.stages
        assert manager.session_state.stages["testing"].status == StageStatus.RUNNING

    @pytest.mark.asyncio
    async def test_update_stage_status_completed(self, tmp_path):
        """Test updating stage status to completed sets end_time."""
        manager = StateManager(state_dir=tmp_path)

        await manager.update_stage_status("testing", "running")
        await manager.update_stage_status("testing", "completed")

        assert manager.session_state.stages["testing"].end_time is not None


@pytest.mark.unit
class TestStateManagerIssues:
    """Test StateManager issue handling."""

    @pytest.mark.asyncio
    async def test_add_issue(self, tmp_path):
        """Test adding an issue."""
        manager = StateManager(state_dir=tmp_path)
        issue = Issue(id="i1", type="error", message="Test", file_path="/test.py")

        await manager.add_issue(issue)

        assert len(manager.session_state.global_issues) == 1
        assert manager.session_state.global_issues[0].id == "i1"

    def test_remove_issue(self, tmp_path):
        """Test removing an issue."""
        manager = StateManager(state_dir=tmp_path)
        issue = Issue(id="i1", type="error", message="Test", file_path="/test.py")
        manager.session_state.global_issues = [issue]

        removed = manager.remove_issue("i1")

        assert removed is True
        assert len(manager.session_state.global_issues) == 0

    def test_remove_issue_nonexistent(self, tmp_path):
        """Test removing non-existent issue."""
        manager = StateManager(state_dir=tmp_path)

        removed = manager.remove_issue("nonexistent")

        assert removed is False

    def test_get_issues_by_priority(self, tmp_path):
        """Test getting issues by priority."""
        manager = StateManager(state_dir=tmp_path)
        issue1 = Issue(
            id="i1",
            type="error",
            message="Test",
            file_path="/test.py",
            priority=Priority.HIGH,
        )
        issue2 = Issue(
            id="i2",
            type="error",
            message="Test",
            file_path="/test.py",
            priority=Priority.LOW,
        )
        manager.session_state.global_issues = [issue1, issue2]

        high_issues = manager.get_issues_by_priority(Priority.HIGH)

        assert len(high_issues) == 1
        assert high_issues[0].id == "i1"

    def test_get_issues_by_type(self, tmp_path):
        """Test getting issues by type."""
        manager = StateManager(state_dir=tmp_path)
        issue1 = Issue(
            id="i1", type="syntax_error", message="Test", file_path="/test.py"
        )
        issue2 = Issue(id="i2", type="type_error", message="Test", file_path="/test.py")
        manager.session_state.global_issues = [issue1, issue2]

        syntax_errors = manager.get_issues_by_type("syntax_error")

        assert len(syntax_errors) == 1
        assert syntax_errors[0].id == "i1"

    def test_get_auto_fixable_issues(self, tmp_path):
        """Test getting auto-fixable issues."""
        manager = StateManager(state_dir=tmp_path)
        issue1 = Issue(
            id="i1",
            type="error",
            message="Test",
            file_path="/test.py",
            auto_fixable=True,
        )
        issue2 = Issue(
            id="i2",
            type="error",
            message="Test",
            file_path="/test.py",
            auto_fixable=False,
        )
        manager.session_state.global_issues = [issue1, issue2]

        auto_fixable = manager.get_auto_fixable_issues()

        assert len(auto_fixable) == 1
        assert auto_fixable[0].id == "i1"


@pytest.mark.unit
class TestStateManagerSummary:
    """Test StateManager session summary."""

    @pytest.mark.asyncio
    async def test_get_session_summary_empty(self, tmp_path):
        """Test session summary with no data."""
        manager = StateManager(state_dir=tmp_path)

        summary = manager.get_session_summary()

        assert "session_id" in summary
        assert "duration" in summary
        assert summary["total_issues"] == 0
        assert summary["total_fixes"] == 0

    @pytest.mark.asyncio
    async def test_get_session_summary_with_data(self, tmp_path):
        """Test session summary with data."""
        manager = StateManager(state_dir=tmp_path)

        await manager.start_stage("testing")
        await manager.complete_stage("testing", fixes=["fix1"])

        issue = Issue(
            id="i1",
            type="error",
            message="Test",
            file_path="/test.py",
            priority=Priority.HIGH,
        )
        await manager.add_issue(issue)

        summary = manager.get_session_summary()

        assert summary["total_issues"] == 1
        assert summary["total_fixes"] == 1
        assert summary["issues_by_priority"]["high"] == 1
        assert summary["issues_by_type"]["error"] == 1
        assert summary["stages"]["testing"] == "completed"


@pytest.mark.unit
class TestStateManagerCheckpoints:
    """Test StateManager checkpoint functionality."""

    @pytest.mark.asyncio
    async def test_save_checkpoint(self, tmp_path):
        """Test saving a checkpoint."""
        manager = StateManager(state_dir=tmp_path)

        await manager.save_checkpoint("test_checkpoint")

        checkpoint_file = manager.checkpoints_dir / "test_checkpoint.json"
        assert checkpoint_file.exists()

    @pytest.mark.asyncio
    async def test_save_checkpoint_with_data(self, tmp_path):
        """Test saving checkpoint with session data."""
        manager = StateManager(state_dir=tmp_path)
        await manager.start_stage("testing")

        await manager.save_checkpoint("test_checkpoint")

        checkpoint_file = manager.checkpoints_dir / "test_checkpoint.json"
        with checkpoint_file.open() as f:
            data = json.load(f)

        assert data["name"] == "test_checkpoint"
        assert "timestamp" in data
        assert "session_state" in data

    def test_load_checkpoint(self, tmp_path):
        """Test loading a checkpoint."""
        manager = StateManager(state_dir=tmp_path)
        original_session_id = manager.session_state.session_id

        # Save checkpoint
        checkpoint_file = manager.checkpoints_dir / "test_checkpoint.json"
        checkpoint_data = {
            "name": "test_checkpoint",
            "timestamp": time.time(),
            "session_state": {
                "session_id": "restored123",
                "start_time": time.time(),
                "current_stage": None,
                "stages": {},
                "global_issues": [],
                "fixes_applied": [],
                "metadata": {},
            },
        }
        with checkpoint_file.open("w") as f:
            json.dump(checkpoint_data, f)

        # Load checkpoint
        loaded = manager.load_checkpoint("test_checkpoint")

        assert loaded is True
        assert manager.session_state.session_id == "restored123"
        assert manager.session_state.session_id != original_session_id

    def test_load_checkpoint_nonexistent(self, tmp_path):
        """Test loading non-existent checkpoint."""
        manager = StateManager(state_dir=tmp_path)

        loaded = manager.load_checkpoint("nonexistent")

        assert loaded is False

    def test_list_checkpoints_empty(self, tmp_path):
        """Test listing checkpoints when none exist."""
        manager = StateManager(state_dir=tmp_path)

        checkpoints = manager.list_checkpoints()

        assert checkpoints == []

    @pytest.mark.asyncio
    async def test_list_checkpoints_with_data(self, tmp_path):
        """Test listing checkpoints."""
        manager = StateManager(state_dir=tmp_path)

        await manager.save_checkpoint("checkpoint1")
        await manager.save_checkpoint("checkpoint2")

        checkpoints = manager.list_checkpoints()

        assert len(checkpoints) >= 2
        assert all("name" in cp for cp in checkpoints)
        assert all("timestamp" in cp for cp in checkpoints)


@pytest.mark.unit
class TestStateManagerSession:
    """Test StateManager session lifecycle."""

    def test_start_session(self, tmp_path):
        """Test starting a session."""
        manager = StateManager(state_dir=tmp_path)

        manager.start_session()

        # Should save state
        state_file = manager.state_dir / "current_session.json"
        assert state_file.exists()

    def test_complete_session(self, tmp_path):
        """Test completing a session."""
        manager = StateManager(state_dir=tmp_path)

        manager.complete_session()

        assert manager.session_state.metadata["status"] == "completed"
        assert "completed_time" in manager.session_state.metadata

    @pytest.mark.asyncio
    async def test_reset_session(self, tmp_path):
        """Test resetting a session."""
        manager = StateManager(state_dir=tmp_path)
        original_session_id = manager.session_state.session_id

        await manager.start_stage("testing")
        await manager.reset_session()

        assert manager.session_state.session_id != original_session_id
        assert len(manager.session_state.stages) == 0


@pytest.mark.unit
class TestStateManagerPersistence:
    """Test StateManager state persistence."""

    def test_save_state_sync(self, tmp_path):
        """Test synchronous state saving."""
        manager = StateManager(state_dir=tmp_path)

        manager._save_state_sync()

        state_file = manager.state_dir / "current_session.json"
        assert state_file.exists()

    def test_save_state_sync_creates_json(self, tmp_path):
        """Test state file contains valid JSON."""
        manager = StateManager(state_dir=tmp_path)

        manager._save_state_sync()

        state_file = manager.state_dir / "current_session.json"
        with state_file.open() as f:
            data = json.load(f)

        assert "session_id" in data
        assert "start_time" in data

    def test_load_state_nonexistent(self, tmp_path):
        """Test loading non-existent state."""
        manager = StateManager(state_dir=tmp_path)

        loaded = manager._load_state()

        assert loaded is False

    def test_load_state_success(self, tmp_path):
        """Test loading existing state."""
        manager = StateManager(state_dir=tmp_path)

        # Save state first
        manager._save_state_sync()

        # Create new manager and load
        new_manager = StateManager(state_dir=tmp_path)
        loaded = new_manager._load_state()

        assert loaded is True
