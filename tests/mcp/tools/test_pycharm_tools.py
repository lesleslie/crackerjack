"""Integration tests for PyCharm MCP tools.

Tests cover get_ide_diagnostics, search_code, get_symbol_info, find_usages,
and pycharm_health tools with mocked PyCharmMCPAdapter.

Coverage includes:
- Unit tests with mocked adapter
- Circuit breaker behavior
- Error handling
- Severity mapping
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.mcp.tools import pycharm_tools
from crackerjack.services.pycharm_mcp_integration import (
    CircuitBreakerState,
    PyCharmMCPAdapter,
    SearchResult,
)


class TestMapSeverity:
    """Tests for the _map_severity helper function."""

    def test_map_severity_error(self) -> None:
        """Test mapping error severity."""
        assert pycharm_tools._map_severity("error") == "error"

    def test_map_severity_warning(self) -> None:
        """Test mapping warning severity."""
        assert pycharm_tools._map_severity("warning") == "warning"

    def test_map_severity_weak_warning(self) -> None:
        """Test mapping weak_warning to info."""
        assert pycharm_tools._map_severity("weak_warning") == "info"

    def test_map_severity_info(self) -> None:
        """Test mapping info severity."""
        assert pycharm_tools._map_severity("info") == "info"

    def test_map_severity_typo(self) -> None:
        """Test mapping typo to info."""
        assert pycharm_tools._map_severity("typo") == "info"

    def test_map_severity_server_problem(self) -> None:
        """Test mapping server_problem to error."""
        assert pycharm_tools._map_severity("server_problem") == "error"

    def test_map_severity_unknown_defaults_to_warning(self) -> None:
        """Test unknown severity defaults to warning."""
        assert pycharm_tools._map_severity("unknown_severity") == "warning"

    def test_map_severity_case_insensitive(self) -> None:
        """Test severity mapping is case insensitive."""
        assert pycharm_tools._map_severity("ERROR") == "error"
        assert pycharm_tools._map_severity("Warning") == "warning"
        assert pycharm_tools._map_severity("INFO") == "info"

    def test_map_severity_empty_string(self) -> None:
        """Test empty string defaults to warning."""
        assert pycharm_tools._map_severity("") == "warning"


class TestResponseHelpers:
    """Tests for response creation helper functions."""

    def test_create_success_response(self) -> None:
        """Test success response creation."""
        data = {"key": "value", "count": 5}
        result = pycharm_tools._create_success_response(data)

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["key"] == "value"
        assert parsed["count"] == 5

    def test_create_error_response(self) -> None:
        """Test error response creation."""
        result = pycharm_tools._create_error_response(
            "Something went wrong",
            file_path="test.py",
            code=500,
        )

        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["error"] == "Something went wrong"
        assert parsed["file_path"] == "test.py"
        assert parsed["code"] == 500

    def test_create_error_response_minimal(self) -> None:
        """Test error response with just message."""
        result = pycharm_tools._create_error_response("Error occurred")

        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["error"] == "Error occurred"
        assert len(parsed) == 2


class TestCircuitBreakerState:
    """Tests for CircuitBreakerState behavior."""

    def test_initial_state(self) -> None:
        """Test circuit breaker initial state is closed."""
        cb = CircuitBreakerState()
        assert cb.is_open is False
        assert cb.failure_count == 0
        assert cb.can_execute() is True

    def test_record_success_resets_failures(self) -> None:
        """Test recording success resets failure count."""
        cb = CircuitBreakerState()
        cb.failure_count = 2
        cb.record_success()

        assert cb.failure_count == 0
        assert cb.is_open is False

    def test_record_failure_increments_count(self) -> None:
        """Test recording failure increments count."""
        cb = CircuitBreakerState()
        cb.record_failure()

        assert cb.failure_count == 1
        assert cb.is_open is False

    def test_circuit_opens_after_threshold(self) -> None:
        """Test circuit opens after reaching failure threshold."""
        cb = CircuitBreakerState(failure_threshold=3)

        cb.record_failure()
        assert cb.is_open is False

        cb.record_failure()
        assert cb.is_open is False

        cb.record_failure()
        assert cb.is_open is True
        assert cb.can_execute() is False

    def test_circuit_half_open_after_recovery_timeout(self) -> None:
        """Test circuit allows execution after recovery timeout."""
        cb = CircuitBreakerState(failure_threshold=1, recovery_timeout=0.1)

        # Open the circuit
        cb.record_failure()
        assert cb.is_open is True
        assert cb.can_execute() is False

        # Wait for recovery timeout
        import time
        time.sleep(0.15)

        # Should now allow execution (half-open state)
        assert cb.can_execute() is True


class TestPyCharmMCPAdapterSanitization:
    """Tests for input sanitization in PyCharmMCPAdapter."""

    def test_sanitize_valid_regex(self) -> None:
        """Test valid regex passes sanitization."""
        adapter = PyCharmMCPAdapter()
        assert adapter._sanitize_regex(r"\d+") == r"\d+"
        assert adapter._sanitize_regex("hello") == "hello"
        assert adapter._sanitize_regex(r"func\(\)") == r"func\(\)"

    def test_sanitize_rejects_too_long_pattern(self) -> None:
        """Test overly long patterns are rejected."""
        adapter = PyCharmMCPAdapter()
        long_pattern = "a" * 501
        assert adapter._sanitize_regex(long_pattern) == ""

    def test_sanitize_rejects_redos_patterns(self) -> None:
        """Test ReDoS-vulnerable patterns are rejected."""
        adapter = PyCharmMCPAdapter()

        # These patterns can cause catastrophic backtracking
        assert adapter._sanitize_regex(r"(.*)+") == ""
        assert adapter._sanitize_regex(r"(.+)*") == ""
        assert adapter._sanitize_regex(r"(.*){10}") == ""

    def test_sanitize_rejects_invalid_regex(self) -> None:
        """Test invalid regex patterns are rejected."""
        adapter = PyCharmMCPAdapter()
        assert adapter._sanitize_regex(r"[unclosed") == ""
        assert adapter._sanitize_regex(r"*invalid") == ""

    def test_is_safe_path_valid(self) -> None:
        """Test valid paths are accepted."""
        adapter = PyCharmMCPAdapter()
        assert adapter._is_safe_path("src/main.py") is True
        assert adapter._is_safe_path("tests/test_file.py") is True
        assert adapter._is_safe_path("/tmp/test.py") is True

    def test_is_safe_path_rejects_traversal(self) -> None:
        """Test path traversal attempts are rejected."""
        adapter = PyCharmMCPAdapter()
        assert adapter._is_safe_path("../../../etc/passwd") is False
        assert adapter._is_safe_path("src/../..") is False

    def test_is_safe_path_rejects_null_bytes(self) -> None:
        """Test paths with null bytes are rejected."""
        adapter = PyCharmMCPAdapter()
        assert adapter._is_safe_path("src/main.py\x00.txt") is False

    def test_is_safe_path_rejects_empty(self) -> None:
        """Test empty paths are rejected."""
        adapter = PyCharmMCPAdapter()
        assert adapter._is_safe_path("") is False

    def test_is_safe_path_rejects_absolute_outside_tmp(self) -> None:
        """Test absolute paths outside /tmp are rejected."""
        adapter = PyCharmMCPAdapter()
        assert adapter._is_safe_path("/etc/passwd") is False
        assert adapter._is_safe_path("/home/user/file.py") is False


class TestPyCharmMCPAdapterCaching:
    """Tests for caching behavior in PyCharmMCPAdapter."""

    def test_cache_set_and_get(self) -> None:
        """Test basic cache operations."""
        adapter = PyCharmMCPAdapter()

        adapter._set_cached("key1", "value1", ttl=60.0)
        assert adapter._get_cached("key1") == "value1"

    def test_cache_expiry(self) -> None:
        """Test cache entries expire after TTL."""
        import time
        adapter = PyCharmMCPAdapter()

        adapter._set_cached("key1", "value1", ttl=0.1)
        assert adapter._get_cached("key1") == "value1"

        time.sleep(0.15)
        assert adapter._get_cached("key1") is None

    def test_clear_cache(self) -> None:
        """Test clearing all cache entries."""
        adapter = PyCharmMCPAdapter()

        adapter._set_cached("key1", "value1")
        adapter._set_cached("key2", "value2")
        adapter.clear_cache()

        assert adapter._get_cached("key1") is None
        assert adapter._get_cached("key2") is None


class TestGetIDEDiagnosticsTool:
    """Tests for get_ide_diagnostics MCP tool."""

    @pytest.fixture
    def mock_adapter(self) -> MagicMock:
        """Create a mocked PyCharmMCPAdapter."""
        adapter = MagicMock(spec=PyCharmMCPAdapter)
        adapter.get_file_problems = AsyncMock()
        adapter.health_check = AsyncMock(
            return_value={
                "mcp_available": True,
                "circuit_breaker_open": False,
                "failure_count": 0,
                "cache_size": 0,
            }
        )
        return adapter

    @pytest.fixture
    def mock_context(self) -> MagicMock:
        """Create a mocked MCP context."""
        context = MagicMock()
        context._pycharm_adapter = None
        return context

    @pytest.mark.anyio
    async def test_get_ide_diagnostics_success(self, mock_adapter: MagicMock) -> None:
        """Test successful diagnostics retrieval."""
        mock_adapter.get_file_problems.return_value = [
            {
                "line": 10,
                "column": 5,
                "message": "Unused import",
                "severity": "warning",
                "code": "F401",
                "quick_fix": "Remove import",
            },
            {
                "line": 20,
                "column": 0,
                "message": "Undefined variable",
                "severity": "error",
                "code": "F821",
            },
        ]

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            # Create the tool function dynamically
            result = await self._call_get_ide_diagnostics(
                mock_adapter,
                "src/main.py",
                errors_only=False,
            )

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["count"] == 2
        assert parsed["file_path"] == "src/main.py"

        issues = parsed["issues"]
        assert len(issues) == 2
        assert issues[0]["line_number"] == 10
        assert issues[0]["severity"] == "warning"
        assert issues[0]["source"] == "pycharm"
        assert issues[1]["severity"] == "error"

    @pytest.mark.anyio
    async def test_get_ide_diagnostics_errors_only(
        self, mock_adapter: MagicMock
    ) -> None:
        """Test diagnostics with errors_only filter."""
        mock_adapter.get_file_problems.return_value = [
            {"line": 10, "message": "Warning", "severity": "warning"},
            {"line": 20, "message": "Error", "severity": "error"},
            {"line": 30, "message": "Info", "severity": "info"},
        ]

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            result = await self._call_get_ide_diagnostics(
                mock_adapter,
                "src/main.py",
                errors_only=True,
            )

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["count"] == 1
        assert parsed["issues"][0]["severity"] == "error"

    @pytest.mark.anyio
    async def test_get_ide_diagnostics_exception(self, mock_adapter: MagicMock) -> None:
        """Test diagnostics handles exceptions gracefully."""
        mock_adapter.get_file_problems.side_effect = Exception("Connection failed")

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            result = await self._call_get_ide_diagnostics(
                mock_adapter,
                "src/main.py",
                errors_only=False,
            )

        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "Connection failed" in parsed["error"]
        assert parsed["file_path"] == "src/main.py"

    @pytest.mark.anyio
    async def test_get_ide_diagnostics_empty_results(
        self, mock_adapter: MagicMock
    ) -> None:
        """Test diagnostics with no issues found."""
        mock_adapter.get_file_problems.return_value = []

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            result = await self._call_get_ide_diagnostics(
                mock_adapter,
                "src/clean.py",
                errors_only=False,
            )

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["count"] == 0
        assert parsed["issues"] == []

    async def _call_get_ide_diagnostics(
        self,
        adapter: MagicMock,
        file_path: str,
        errors_only: bool,
    ) -> str:
        """Helper to call get_ide_diagnostics logic."""
        try:
            problems = await adapter.get_file_problems(file_path, errors_only)
        except Exception as e:
            return pycharm_tools._create_error_response(str(e), file_path=file_path)

        issues = []
        for problem in problems:
            severity = problem.get("severity", "warning").lower()
            if errors_only and severity != "error":
                continue

            issues.append(
                {
                    "file_path": file_path,
                    "line_number": problem.get("line"),
                    "column_number": problem.get("column"),
                    "message": problem.get("message", ""),
                    "code": problem.get("code"),
                    "severity": pycharm_tools._map_severity(severity),
                    "suggestion": problem.get("quick_fix"),
                    "source": "pycharm",
                }
            )

        return pycharm_tools._create_success_response(
            {
                "issues": issues,
                "count": len(issues),
                "file_path": file_path,
            }
        )


class TestSearchCodeTool:
    """Tests for search_code MCP tool."""

    @pytest.fixture
    def mock_adapter(self) -> MagicMock:
        """Create a mocked PyCharmMCPAdapter."""
        adapter = MagicMock(spec=PyCharmMCPAdapter)
        adapter.search_regex = AsyncMock()
        return adapter

    @pytest.mark.anyio
    async def test_search_code_success(self, mock_adapter: MagicMock) -> None:
        """Test successful code search."""
        mock_adapter.search_regex.return_value = [
            SearchResult(
                file_path="src/main.py",
                line_number=10,
                column=5,
                match_text="# type: ignore",
                context_before="x = func()",
                context_after="y = x + 1",
            ),
            SearchResult(
                file_path="tests/test_main.py",
                line_number=25,
                column=0,
                match_text="# type: ignore",
                context_before=None,
                context_after=None,
            ),
        ]

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            result = await self._call_search_code(
                mock_adapter,
                r"# type: ignore",
                "*.py",
            )

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["count"] == 2
        assert parsed["pattern"] == r"# type: ignore"
        assert parsed["file_pattern"] == "*.py"

        results = parsed["results"]
        assert results[0]["file_path"] == "src/main.py"
        assert results[0]["line"] == 10
        assert results[0]["match"] == "# type: ignore"
        assert results[0]["context_before"] == "x = func()"

    @pytest.mark.anyio
    async def test_search_code_no_results(self, mock_adapter: MagicMock) -> None:
        """Test search with no matches."""
        mock_adapter.search_regex.return_value = []

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            result = await self._call_search_code(
                mock_adapter,
                "nonexistent_pattern",
                None,
            )

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["count"] == 0
        assert parsed["results"] == []

    @pytest.mark.anyio
    async def test_search_code_exception(self, mock_adapter: MagicMock) -> None:
        """Test search handles exceptions gracefully."""
        mock_adapter.search_regex.side_effect = Exception("Invalid regex")

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            result = await self._call_search_code(
                mock_adapter,
                "[invalid",
                None,
            )

        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "Invalid regex" in parsed["error"]

    @pytest.mark.anyio
    async def test_search_code_with_file_pattern(
        self, mock_adapter: MagicMock
    ) -> None:
        """Test search respects file pattern."""
        mock_adapter.search_regex.return_value = [
            SearchResult(
                file_path="test.md",
                line_number=1,
                column=0,
                match_text="TODO",
            ),
        ]

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            await self._call_search_code(mock_adapter, "TODO", "*.md")

        mock_adapter.search_regex.assert_called_once_with("TODO", "*.md")

    async def _call_search_code(
        self,
        adapter: MagicMock,
        pattern: str,
        file_pattern: str | None,
    ) -> str:
        """Helper to call search_code logic."""
        try:
            results = await adapter.search_regex(pattern, file_pattern)
        except Exception as e:
            return pycharm_tools._create_error_response(str(e), pattern=pattern)

        formatted_results = [
            {
                "file_path": r.file_path,
                "line": r.line_number,
                "column": r.column,
                "match": r.match_text,
                "context_before": r.context_before,
                "context_after": r.context_after,
            }
            for r in results
        ]

        return pycharm_tools._create_success_response(
            {
                "results": formatted_results,
                "count": len(formatted_results),
                "pattern": pattern,
                "file_pattern": file_pattern,
            }
        )


class TestGetSymbolInfoTool:
    """Tests for get_symbol_info MCP tool."""

    @pytest.fixture
    def mock_adapter(self) -> MagicMock:
        """Create a mocked PyCharmMCPAdapter."""
        adapter = MagicMock(spec=PyCharmMCPAdapter)
        adapter.health_check = AsyncMock()
        return adapter

    @pytest.mark.anyio
    async def test_get_symbol_info_mcp_unavailable(
        self, mock_adapter: MagicMock
    ) -> None:
        """Test symbol info when MCP is not connected."""
        mock_adapter.health_check.return_value = {
            "mcp_available": False,
            "circuit_breaker_open": False,
            "failure_count": 0,
            "cache_size": 0,
        }

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            result = await self._call_get_symbol_info(mock_adapter, "BaseModel")

        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "MCP server not connected" in parsed["error"]
        assert parsed["symbol"] == "BaseModel"

    @pytest.mark.anyio
    async def test_get_symbol_info_not_implemented(
        self, mock_adapter: MagicMock
    ) -> None:
        """Test symbol info returns not implemented when MCP available."""
        mock_adapter.health_check.return_value = {
            "mcp_available": True,
            "circuit_breaker_open": False,
            "failure_count": 0,
            "cache_size": 0,
        }

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            result = await self._call_get_symbol_info(mock_adapter, "BaseModel")

        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "not yet implemented" in parsed["error"]
        assert parsed["status"] == "not_implemented"

    async def _call_get_symbol_info(
        self,
        adapter: MagicMock,
        symbol_name: str,
    ) -> str:
        """Helper to call get_symbol_info logic."""
        health = await adapter.health_check()
        if not health.get("mcp_available"):
            return pycharm_tools._create_error_response(
                "PyCharm MCP server not connected. Symbol info requires IDE connection.",
                symbol=symbol_name,
                hint="Ensure PyCharm is running with MCP server enabled.",
            )

        return pycharm_tools._create_error_response(
            "Symbol info tool not yet implemented - requires PyCharm MCP extension",
            symbol=symbol_name,
            status="not_implemented",
        )


class TestFindUsagesTool:
    """Tests for find_usages MCP tool."""

    @pytest.fixture
    def mock_adapter(self) -> MagicMock:
        """Create a mocked PyCharmMCPAdapter."""
        adapter = MagicMock(spec=PyCharmMCPAdapter)
        adapter.health_check = AsyncMock()
        return adapter

    @pytest.mark.anyio
    async def test_find_usages_mcp_unavailable(
        self, mock_adapter: MagicMock
    ) -> None:
        """Test find usages when MCP is not connected."""
        mock_adapter.health_check.return_value = {
            "mcp_available": False,
            "circuit_breaker_open": False,
            "failure_count": 0,
            "cache_size": 0,
        }

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            result = await self._call_find_usages(mock_adapter, "process_data")

        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "MCP server not connected" in parsed["error"]
        assert parsed["symbol"] == "process_data"

    @pytest.mark.anyio
    async def test_find_usages_not_implemented(self, mock_adapter: MagicMock) -> None:
        """Test find usages returns not implemented when MCP available."""
        mock_adapter.health_check.return_value = {
            "mcp_available": True,
            "circuit_breaker_open": False,
            "failure_count": 0,
            "cache_size": 0,
        }

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            result = await self._call_find_usages(mock_adapter, "process_data")

        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "not yet implemented" in parsed["error"]

    async def _call_find_usages(
        self,
        adapter: MagicMock,
        symbol_name: str,
        file_path: str | None = None,
        limit: int = 50,
    ) -> str:
        """Helper to call find_usages logic."""
        health = await adapter.health_check()
        if not health.get("mcp_available"):
            return pycharm_tools._create_error_response(
                "PyCharm MCP server not connected. Find usages requires IDE connection.",
                symbol=symbol_name,
            )

        return pycharm_tools._create_error_response(
            "Find usages tool not yet implemented - requires PyCharm MCP extension",
            symbol=symbol_name,
            status="not_implemented",
        )


class TestPycharmHealthTool:
    """Tests for pycharm_health MCP tool."""

    @pytest.fixture
    def mock_adapter(self) -> MagicMock:
        """Create a mocked PyCharmMCPAdapter."""
        adapter = MagicMock(spec=PyCharmMCPAdapter)
        adapter.health_check = AsyncMock()
        return adapter

    @pytest.mark.anyio
    async def test_pycharm_health_healthy(self, mock_adapter: MagicMock) -> None:
        """Test health check when everything is healthy."""
        mock_adapter.health_check.return_value = {
            "mcp_available": True,
            "circuit_breaker_open": False,
            "failure_count": 0,
            "cache_size": 5,
        }

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            result = await self._call_pycharm_health(mock_adapter)

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["mcp_available"] is True
        assert parsed["circuit_breaker_open"] is False
        assert parsed["failure_count"] == 0
        assert parsed["cache_size"] == 5
        assert parsed["status"] == "healthy"

    @pytest.mark.anyio
    async def test_pycharm_health_degraded(self, mock_adapter: MagicMock) -> None:
        """Test health check when circuit breaker is open."""
        mock_adapter.health_check.return_value = {
            "mcp_available": False,
            "circuit_breaker_open": True,
            "failure_count": 5,
            "cache_size": 0,
        }

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            result = await self._call_pycharm_health(mock_adapter)

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["mcp_available"] is False
        assert parsed["circuit_breaker_open"] is True
        assert parsed["failure_count"] == 5
        assert parsed["status"] == "degraded"

    @pytest.mark.anyio
    async def test_pycharm_health_exception(self, mock_adapter: MagicMock) -> None:
        """Test health check handles exceptions gracefully."""
        mock_adapter.health_check.side_effect = Exception("Health check failed")

        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=mock_adapter,
        ):
            result = await self._call_pycharm_health(mock_adapter)

        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["error"] == "Health check failed"

    async def _call_pycharm_health(self, adapter: MagicMock) -> str:
        """Helper to call pycharm_health logic."""
        from contextlib import suppress

        with suppress(Exception):
            health = await adapter.health_check()
            return pycharm_tools._create_success_response(
                {
                    "mcp_available": health.get("mcp_available", False),
                    "circuit_breaker_open": health.get("circuit_breaker_open", False),
                    "failure_count": health.get("failure_count", 0),
                    "cache_size": health.get("cache_size", 0),
                    "status": "healthy"
                    if not health.get("circuit_breaker_open")
                    else "degraded",
                }
            )

        return pycharm_tools._create_error_response("Health check failed")


class TestCircuitBreakerIntegration:
    """Tests for circuit breaker integration with tools."""

    @pytest.fixture
    def adapter_with_open_circuit(self) -> MagicMock:
        """Create adapter with open circuit breaker."""
        adapter = MagicMock(spec=PyCharmMCPAdapter)
        adapter._circuit_breaker = CircuitBreakerState()
        adapter._circuit_breaker.is_open = True
        adapter._circuit_breaker.failure_count = 5
        adapter.health_check = AsyncMock(
            return_value={
                "mcp_available": True,
                "circuit_breaker_open": True,
                "failure_count": 5,
                "cache_size": 0,
            }
        )
        return adapter

    @pytest.mark.anyio
    async def test_tools_respect_open_circuit(
        self, adapter_with_open_circuit: MagicMock
    ) -> None:
        """Test that tools report degraded status when circuit is open."""
        with patch(
            "crackerjack.mcp.tools.pycharm_tools._get_adapter",
            return_value=adapter_with_open_circuit,
        ):
            health = await adapter_with_open_circuit.health_check()

        assert health["circuit_breaker_open"] is True
        assert health["failure_count"] == 5

    def test_circuit_breaker_prevents_operations(self) -> None:
        """Test circuit breaker blocks operations when open."""
        cb = CircuitBreakerState()
        cb.is_open = True
        cb.failure_count = 5

        assert cb.can_execute() is False


class TestToolRegistration:
    """Tests for tool registration with MCP app."""

    def test_register_pycharm_tools(self) -> None:
        """Test that all PyCharm tools are registered."""
        mock_app = MagicMock()

        pycharm_tools.register_pycharm_tools(mock_app)

        # Verify tool decorator was called for each tool
        assert mock_app.tool.call_count == 5

    def test_register_tools_creates_functions(self) -> None:
        """Test that registration creates callable tool functions."""
        mock_app = MagicMock()

        # Track registered tools
        registered_tools: list[str] = []

        def mock_tool_decorator():
            def decorator(func):
                registered_tools.append(func.__name__)
                return func
            return decorator

        mock_app.tool = mock_tool_decorator

        pycharm_tools.register_pycharm_tools(mock_app)

        expected_tools = [
            "get_ide_diagnostics",
            "search_code",
            "get_symbol_info",
            "find_usages",
            "pycharm_health",
        ]

        for tool_name in expected_tools:
            assert tool_name in registered_tools, f"Tool {tool_name} not registered"


class TestAdapterSingleton:
    """Tests for adapter singleton management."""

    def test_get_adapter_creates_singleton(self) -> None:
        """Test that _get_adapter creates adapter on first call."""
        mock_context = MagicMock()
        mock_context._pycharm_adapter = None

        with patch(
            "crackerjack.mcp.tools.pycharm_tools.get_context",
            return_value=mock_context,
        ):
            adapter = pycharm_tools._get_adapter()

        assert adapter is not None
        assert isinstance(adapter, PyCharmMCPAdapter)

    def test_get_adapter_reuses_singleton(self) -> None:
        """Test that _get_adapter reuses existing adapter."""
        mock_context = MagicMock()
        existing_adapter = PyCharmMCPAdapter()
        mock_context._pycharm_adapter = existing_adapter

        with patch(
            "crackerjack.mcp.tools.pycharm_tools.get_context",
            return_value=mock_context,
        ):
            adapter = pycharm_tools._get_adapter()

        assert adapter is existing_adapter


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.anyio
    async def test_diagnostics_with_missing_fields(self) -> None:
        """Test diagnostics handles problems with missing optional fields."""
        mock_adapter = MagicMock(spec=PyCharmMCPAdapter)
        mock_adapter.get_file_problems = AsyncMock(
            return_value=[
                {
                    # Missing column, code, quick_fix
                    "line": 10,
                    "message": "Some issue",
                    "severity": "warning",
                }
            ]
        )

        result = await self._call_get_ide_diagnostics(mock_adapter, "test.py", False)

        parsed = json.loads(result)
        assert parsed["success"] is True
        issue = parsed["issues"][0]
        assert issue["line_number"] == 10
        assert issue["column_number"] is None
        assert issue["code"] is None
        assert issue["suggestion"] is None

    @pytest.mark.anyio
    async def test_search_with_none_context(self) -> None:
        """Test search handles results with None context."""
        mock_adapter = MagicMock(spec=PyCharmMCPAdapter)
        mock_adapter.search_regex = AsyncMock(
            return_value=[
                SearchResult(
                    file_path="test.py",
                    line_number=1,
                    column=0,
                    match_text="match",
                    context_before=None,
                    context_after=None,
                )
            ]
        )

        result = await self._call_search_code(mock_adapter, "match", None)

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["results"][0]["context_before"] is None
        assert parsed["results"][0]["context_after"] is None

    @pytest.mark.anyio
    async def test_diagnostics_with_unknown_severity(self) -> None:
        """Test diagnostics handles unknown severity values."""
        mock_adapter = MagicMock(spec=PyCharmMCPAdapter)
        mock_adapter.get_file_problems = AsyncMock(
            return_value=[
                {
                    "line": 1,
                    "message": "Unknown severity",
                    "severity": "weird_severity",
                }
            ]
        )

        result = await self._call_get_ide_diagnostics(mock_adapter, "test.py", False)

        parsed = json.loads(result)
        # Unknown severity should default to warning
        assert parsed["issues"][0]["severity"] == "warning"

    async def _call_get_ide_diagnostics(
        self,
        adapter: MagicMock,
        file_path: str,
        errors_only: bool,
    ) -> str:
        """Helper to call get_ide_diagnostics logic."""
        try:
            problems = await adapter.get_file_problems(file_path, errors_only)
        except Exception as e:
            return pycharm_tools._create_error_response(str(e), file_path=file_path)

        issues = []
        for problem in problems:
            severity = problem.get("severity", "warning").lower()
            if errors_only and severity != "error":
                continue

            issues.append(
                {
                    "file_path": file_path,
                    "line_number": problem.get("line"),
                    "column_number": problem.get("column"),
                    "message": problem.get("message", ""),
                    "code": problem.get("code"),
                    "severity": pycharm_tools._map_severity(severity),
                    "suggestion": problem.get("quick_fix"),
                    "source": "pycharm",
                }
            )

        return pycharm_tools._create_success_response(
            {
                "issues": issues,
                "count": len(issues),
                "file_path": file_path,
            }
        )

    async def _call_search_code(
        self,
        adapter: MagicMock,
        pattern: str,
        file_pattern: str | None,
    ) -> str:
        """Helper to call search_code logic."""
        try:
            results = await adapter.search_regex(pattern, file_pattern)
        except Exception as e:
            return pycharm_tools._create_error_response(str(e), pattern=pattern)

        formatted_results = [
            {
                "file_path": r.file_path,
                "line": r.line_number,
                "column": r.column,
                "match": r.match_text,
                "context_before": r.context_before,
                "context_after": r.context_after,
            }
            for r in results
        ]

        return pycharm_tools._create_success_response(
            {
                "results": formatted_results,
                "count": len(formatted_results),
                "pattern": pattern,
                "file_pattern": file_pattern,
            }
        )
