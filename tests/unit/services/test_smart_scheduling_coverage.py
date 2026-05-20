"""Coverage-focused tests for smart scheduling."""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import crackerjack.services.smart_scheduling as smart_scheduling_module
from crackerjack.services.smart_scheduling import SmartSchedulingService


@pytest.fixture
def console() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(tmp_path: Path, console: MagicMock) -> SmartSchedulingService:
    with patch(
        "crackerjack.services.smart_scheduling.Console",
        return_value=console,
    ):
        return SmartSchedulingService(tmp_path / "project", console=None)


def test_constructor_and_disabled_schedule(service: SmartSchedulingService) -> None:
    assert service.project_path.name == "project"
    assert service.cache_dir.exists()

    with patch.dict("os.environ", {"CRACKERJACK_INIT_SCHEDULE": "disabled"}):
        assert service.should_scheduled_init() is False


def test_commit_and_activity_schedules(service: SmartSchedulingService, console: MagicMock) -> None:
    with patch.dict(
        "os.environ",
        {
            "CRACKERJACK_INIT_SCHEDULE": "commit-based",
            "CRACKERJACK_INIT_COMMITS": "2",
        },
    ), patch.object(service, "_count_commits_since_init", return_value=3):
        assert service.should_scheduled_init() is True

    with patch.dict("os.environ", {"CRACKERJACK_INIT_SCHEDULE": "commit-based"}), patch.object(
        service,
        "_count_commits_since_init",
        return_value=1,
    ):
        assert service.should_scheduled_init() is False

    with patch.dict("os.environ", {"CRACKERJACK_INIT_SCHEDULE": "activity-based"}), patch.object(
        service,
        "_has_recent_activity",
        return_value=True,
    ), patch.object(service, "_days_since_init", return_value=8):
        assert service.should_scheduled_init() is True

    with patch.dict("os.environ", {"CRACKERJACK_INIT_SCHEDULE": "activity-based"}), patch.object(
        service,
        "_has_recent_activity",
        return_value=False,
    ), patch.object(service, "_days_since_init", return_value=8):
        assert service.should_scheduled_init() is False

    with patch.dict("os.environ", {"CRACKERJACK_INIT_SCHEDULE": "unknown"}), patch.object(
        service,
        "_check_weekly_schedule",
        return_value=True,
    ):
        assert service.should_scheduled_init() is True


def test_record_init_timestamp_and_last_init(service: SmartSchedulingService, console: MagicMock) -> None:
    timestamp_file = service.cache_dir / f"{service.project_path.name}.init_timestamp"

    service.record_init_timestamp()
    assert timestamp_file.exists()
    assert smart_scheduling_module.datetime.fromisoformat(timestamp_file.read_text().strip())

    timestamp_file.write_text("2024-01-01T00:00:00")
    assert service._get_last_init_timestamp() == datetime.fromisoformat("2024-01-01T00:00:00")

    timestamp_file.write_text("invalid")
    assert (datetime.now() - service._get_last_init_timestamp()) > timedelta(days=29)

    with patch.object(Path, "write_text", side_effect=OSError("disk full")):
        service.record_init_timestamp()
    console.print.assert_called()


def test_weekly_and_subprocess_helpers(service: SmartSchedulingService, console: MagicMock) -> None:
    timestamp_file = service.cache_dir / f"{service.project_path.name}.init_timestamp"
    timestamp_file.write_text("2024-12-01T00:00:00")

    class FakeNow:
        def __init__(self, dt: datetime) -> None:
            self.dt = dt

        def strftime(self, fmt: str) -> str:
            return "monday"

        def __sub__(self, other: datetime) -> timedelta:
            return timedelta(days=8)

    class FakeDatetime:
        @classmethod
        def now(cls) -> FakeNow:
            return FakeNow(datetime(2025, 1, 6, 12, 0, 0))

        @classmethod
        def fromisoformat(cls, value: str) -> datetime:
            return datetime.fromisoformat(value)

    with patch.object(smart_scheduling_module, "datetime", FakeDatetime), patch.dict(
        "os.environ",
        {"CRACKERJACK_INIT_DAY": "monday"},
    ):
        assert service._check_weekly_schedule() is True

    with patch.object(smart_scheduling_module, "datetime", FakeDatetime), patch.dict(
        "os.environ",
        {"CRACKERJACK_INIT_DAY": "tuesday"},
    ):
        assert service._check_weekly_schedule() is False

    with patch.object(
        smart_scheduling_module.subprocess,
        "run",
        return_value=SimpleNamespace(returncode=0, stdout="a\nb\n"),
    ):
        assert service._count_commits_since_init() == 2

    with patch.object(
        smart_scheduling_module.subprocess,
        "run",
        side_effect=subprocess.TimeoutExpired("git", 10),
    ):
        assert service._count_commits_since_init() == 0

    with patch.object(
        smart_scheduling_module.subprocess,
        "run",
        return_value=SimpleNamespace(returncode=0, stdout="recent commit\n"),
    ):
        assert service._has_recent_activity() is True

    with patch.object(
        smart_scheduling_module.subprocess,
        "run",
        side_effect=FileNotFoundError("git not found"),
    ):
        assert service._has_recent_activity() is False

    class DaysDatetime:
        @classmethod
        def now(cls) -> datetime:
            return datetime(2025, 1, 6, 12, 0, 0)

    with patch.object(smart_scheduling_module, "datetime", DaysDatetime), patch.object(
        service,
        "_get_last_init_timestamp",
        return_value=datetime(2024, 12, 29, 12, 0, 0),
    ):
        assert service._days_since_init() == 8
