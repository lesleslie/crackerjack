"""Tests for ``crackerjack.integration.git_metrics_integration``.

The module is a typed stub — production callers should use the
``get_repository_health_dashboard`` MCP tool on the
``crackerjack-mahavishnu-git-analytics`` FastMCP server. The stub's
runtime body raises ``NotImplementedError``; these tests pin that
contract so the stub stays distinguishable from a fully-implemented
collector.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from crackerjack.integration.git_metrics_integration import (
    GitMetricsSessionCollector,
)


def test_module_exports_collector_class() -> None:
    from crackerjack.integration import git_metrics_integration

    assert git_metrics_integration.__all__ == ["GitMetricsSessionCollector"]


def test_collector_default_pkg_path_is_none() -> None:
    collector = GitMetricsSessionCollector()
    assert collector.pkg_path is None


def test_collector_accepts_explicit_pkg_path(tmp_path: Path) -> None:
    collector = GitMetricsSessionCollector(pkg_path=tmp_path)
    assert collector.pkg_path is tmp_path


@pytest.mark.asyncio
async def test_collect_session_metrics_raises_not_implemented() -> None:
    """The stub raises ``NotImplementedError`` with a redirect message."""
    collector = GitMetricsSessionCollector()
    with pytest.raises(NotImplementedError, match="get_repository_health_dashboard"):
        await collector.collect_session_metrics()


@pytest.mark.asyncio
async def test_collect_session_metrics_with_executor_raises() -> None:
    """Even with an executor provided, the stub refuses to run."""
    fake_executor: Any = object()  # not actually invoked
    collector = GitMetricsSessionCollector()
    with pytest.raises(NotImplementedError):
        await collector.collect_session_metrics(executor=fake_executor)
