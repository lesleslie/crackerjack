from unittest.mock import patch

from crackerjack.executors.process_monitor import ProcessMonitor


def test_get_process_metrics_handles_permission_error() -> None:
    monitor = ProcessMonitor(check_interval=1.0)

    with patch(
        "crackerjack.executors.process_monitor.subprocess.run",
        side_effect=PermissionError("Operation not permitted"),
    ):
        metrics = monitor._get_process_metrics(1234, elapsed=5.0)

    assert metrics is None
