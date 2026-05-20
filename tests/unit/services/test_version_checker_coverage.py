"""Coverage-focused tests for version checking."""

from __future__ import annotations

import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.services.version_checker import VersionChecker, VersionInfo


@pytest.fixture
def checker() -> VersionChecker:
    with patch("crackerjack.services.version_checker.Console", return_value=MagicMock()):
        return VersionChecker()


@pytest.mark.asyncio
async def test_check_tool_updates_iterates_tools(checker: VersionChecker) -> None:
    checker.tools_to_check = {"ruff": lambda: "1.0.0", "uv": lambda: "0.1.0"}
    checker._check_single_tool = AsyncMock(
        side_effect=[
            VersionInfo("ruff", "1.0.0"),
            VersionInfo("uv", "0.1.0"),
        ],
    )

    results = await checker.check_tool_updates()

    assert list(results.keys()) == ["ruff", "uv"]
    assert results["ruff"].tool_name == "ruff"
    assert checker._check_single_tool.await_count == 2


@pytest.mark.asyncio
async def test_check_single_tool_branches(checker: VersionChecker) -> None:
    with patch.object(checker, "_fetch_latest_version", new=AsyncMock(return_value="1.2.0")):
        installed = await checker._check_single_tool("ruff", lambda: "1.0.0")
    assert installed.tool_name == "ruff"
    assert installed.update_available is True
    assert installed.latest_version == "1.2.0"

    missing = await checker._check_single_tool("ruff", lambda: None)
    assert missing.current_version == "not installed"

    async def raising_fetch(tool_name: str) -> str | None:
        raise RuntimeError("boom")

    with patch.object(checker, "_fetch_latest_version", new=raising_fetch):
        error = await checker._check_single_tool("ruff", lambda: "1.0.0")

    assert error.current_version == "unknown"
    assert "boom" in (error.error or "")


def test_version_compare_and_helpers(checker: VersionChecker) -> None:
    assert checker._version_compare("1.0.0", "1.0.1") == -1
    assert checker._version_compare("2.0.0", "1.0.0") == 1
    assert checker._version_compare("1.0.0", "1.0.0") == 0
    assert checker._version_compare("1.0", "1.0.0") == -1
    assert checker._version_compare("1.0.0", "1.0") == 1
    assert checker._version_compare("bad", "1.0.0") == 0

    info = checker._create_installed_version_info("ruff", "1.0.0", "1.2.0")
    assert info.update_available is True
    assert info.current_version == "1.0.0"

    missing = checker._create_missing_tool_info("ruff")
    assert missing.current_version == "not installed"

    error = checker._create_error_version_info("ruff", RuntimeError("failed"))
    assert error.current_version == "unknown"
    assert error.error == "failed"


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def json(self) -> dict[str, object]:
        return self.payload


class _FakeSession:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url: str) -> _FakeResponse:
        return _FakeResponse(self.payload)


class _FakePool:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def get_session_context(self) -> _FakeSession:
        return _FakeSession(self.payload)


@pytest.mark.asyncio
async def test_get_tool_version_and_fetch_latest_version(checker: VersionChecker) -> None:
    good_result = MagicMock(returncode=0, stdout="ruff 1.2.3\n")
    bad_result = MagicMock(returncode=1, stdout="")

    with patch("crackerjack.services.version_checker.subprocess.run", return_value=good_result):
        assert checker._get_tool_version("ruff") == "1.2.3"

    with patch("crackerjack.services.version_checker.subprocess.run", return_value=bad_result):
        assert checker._get_tool_version("ruff") is None

    with patch("crackerjack.services.version_checker.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
        assert checker._get_tool_version("ruff") is None

    with patch(
        "crackerjack.services.connection_pool.get_http_pool",
        new=AsyncMock(return_value=_FakePool({"info": {"version": "2.0.0"}})),
    ):
        assert await checker._fetch_latest_version("ruff") == "2.0.0"

    with patch("crackerjack.services.connection_pool.get_http_pool", side_effect=RuntimeError("network")):
        assert await checker._fetch_latest_version("ruff") is None

    assert await checker._fetch_latest_version("unknown") is None
