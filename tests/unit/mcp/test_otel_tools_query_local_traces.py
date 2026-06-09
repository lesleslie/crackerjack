"""Unit tests for Crackerjack query_local_traces OTel tool.

Tests _call_akosha_mcp_tool and the registered query_local_traces tool,
verifying correct delegation to Akosha HotStore MCP endpoint.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCallAkoshaMcpTool:
    """Tests for _call_akosha_mcp_tool helper.

    httpx is lazy-imported inside the function, so we patch httpx.AsyncClient directly.
    """

    @pytest.mark.asyncio
    async def test_builds_correct_jsonrpc_request(self) -> None:
        """Should build correct JSONRPC 2.0 request to Akosha MCP endpoint."""
        from crackerjack.mcp.tools.otel_tools import _call_akosha_mcp_tool

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {"type": "text", "text": '{"outcome": "success"}'},
                    ]
                },
            }
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_instance

            result = await _call_akosha_mcp_tool(
                "query_local_traces",
                {"task_class": "test"},
            )

            mock_instance.post.assert_called_once()
            call_args = mock_instance.post.call_args
            assert call_args[0][0] == "http://localhost: 8682/mcp"
            json_body = call_args[1]["json"]
            assert json_body["jsonrpc"] == "2.0"
            assert json_body["method"] == "tools/call"
            assert json_body["params"]["name"] == "query_local_traces"
            assert json_body["params"]["arguments"] == {"task_class": "test"}

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_invalid_response(self) -> None:
        """Should return empty list when response is not a valid dict."""
        from crackerjack.mcp.tools.otel_tools import _call_akosha_mcp_tool

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value="invalid")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_instance

            result = await _call_akosha_mcp_tool("test_tool", {})

            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_missing_result(self) -> None:
        """Should return empty list when response has no result."""
        from crackerjack.mcp.tools.otel_tools import _call_akosha_mcp_tool

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"jsonrpc": "2.0", "id": 1})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_instance

            result = await _call_akosha_mcp_tool("test_tool", {})

            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_missing_content(self) -> None:
        """Should return empty list when result has no content."""
        from crackerjack.mcp.tools.otel_tools import _call_akosha_mcp_tool

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={"jsonrpc": "2.0", "id": 1, "result": {}}
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_instance

            result = await _call_akosha_mcp_tool("test_tool", {})

            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_httpx_error(self) -> None:
        """Should return empty list on HTTP error."""
        import httpx

        from crackerjack.mcp.tools.otel_tools import _call_akosha_mcp_tool

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(
                side_effect=httpx.HTTPError("network error")
            )
            mock_client_cls.return_value = mock_instance

            result = await _call_akosha_mcp_tool("test_tool", {})

            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_generic_exception(self) -> None:
        """Should return empty list on any other exception."""
        from crackerjack.mcp.tools.otel_tools import _call_akosha_mcp_tool

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(side_effect=OSError("unexpected"))
            mock_client_cls.return_value = mock_instance

            result = await _call_akosha_mcp_tool("test_tool", {})

            assert result == []

    @pytest.mark.asyncio
    async def test_uses_custom_endpoint_from_env_var(self) -> None:
        """Should use AKOSHA_MCP_ENDPOINT env var when set."""
        from crackerjack.mcp.tools.otel_tools import _call_akosha_mcp_tool

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": []},
            }
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_instance

            import os

            os.environ["AKOSHA_MCP_ENDPOINT"] = "http://custom-akosha:9999"

            try:
                result = await _call_akosha_mcp_tool("test_tool", {})

                call_args = mock_instance.post.call_args
                assert call_args[0][0] == "http://custom-akosha:9999/mcp"
            finally:
                del os.environ["AKOSHA_MCP_ENDPOINT"]

    @pytest.mark.asyncio
    async def test_default_endpoint_is_localhost_8682(self) -> None:
        """Should default to http://localhost:8682 when env var is not set."""
        from crackerjack.mcp.tools.otel_tools import _call_akosha_mcp_tool

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": []},
            }
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_instance

            import os

            os.environ.pop("AKOSHA_MCP_ENDPOINT", None)

            result = await _call_akosha_mcp_tool("test_tool", {})

            call_args = mock_instance.post.call_args
            assert call_args[0][0] == "http://localhost: 8682/mcp"


class TestQueryLocalTracesToolRegistration:
    """Tests for query_local_traces via register_otel_tools.

    query_local_traces is registered via @mcp_app.tool() inside register_otel_tools.
    We test it by capturing what _call_akosha_mcp_tool receives.
    """

    @pytest.mark.asyncio
    async def test_correct_arguments_passed_to_akosha(self) -> None:
        """_call_akosha_mcp_tool should receive correct tool name and arguments."""
        from crackerjack.mcp.tools import otel_tools

        captured_calls: list[tuple[str, dict[str, Any]]] = []

        async def capture_call(tool_name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
            captured_calls.append((tool_name, arguments))
            return [
                {"outcome": "success", "duration_ms": 150, "selector": "least_loaded"}
            ]

        with patch(
            "crackerjack.mcp.tools.otel_tools._call_akosha_mcp_tool", new=capture_call
        ):
            mock_mcp_app = MagicMock()
            tools_registered: dict[str, Any] = {}

            def capture_tool():
                def decorator(fn: Any) -> Any:
                    tools_registered[fn.__name__] = fn
                    return fn

                return decorator

            mock_mcp_app.tool = capture_tool

            otel_tools.register_otel_tools(mock_mcp_app)

            result = await tools_registered["query_local_traces"](
                task_class="code_generation",
                time_range_minutes=30,
                limit=50,
            )

            assert len(captured_calls) == 1
            tool_name, arguments = captured_calls[0]
            assert tool_name == "query_local_traces"
            assert arguments["task_class"] == "code_generation"
            assert arguments["time_range_minutes"] == 30
            assert arguments["limit"] == 50
            assert "system_id" not in arguments

    @pytest.mark.asyncio
    async def test_system_id_included_when_provided(self) -> None:
        """system_id should be in arguments when not None."""
        from crackerjack.mcp.tools import otel_tools

        captured: dict[str, Any] = {}

        async def capture_call(tool_name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
            captured["arguments"] = arguments
            return []

        with patch(
            "crackerjack.mcp.tools.otel_tools._call_akosha_mcp_tool", new=capture_call
        ):
            mock_mcp_app = MagicMock()
            tools_registered: dict[str, Any] = {}

            def capture_tool():
                def decorator(fn: Any) -> Any:
                    tools_registered[fn.__name__] = fn
                    return fn

                return decorator

            mock_mcp_app.tool = capture_tool
            otel_tools.register_otel_tools(mock_mcp_app)

            await tools_registered["query_local_traces"](
                task_class="code_review",
                system_id="crackerjack",
            )

            assert captured["arguments"]["system_id"] == "crackerjack"

    @pytest.mark.asyncio
    async def test_system_id_excluded_when_none(self) -> None:
        """system_id should not be in arguments when None."""
        from crackerjack.mcp.tools import otel_tools

        captured: dict[str, Any] = {}

        async def capture_call(tool_name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
            captured["arguments"] = arguments
            return []

        with patch(
            "crackerjack.mcp.tools.otel_tools._call_akosha_mcp_tool", new=capture_call
        ):
            mock_mcp_app = MagicMock()
            tools_registered: dict[str, Any] = {}

            def capture_tool():
                def decorator(fn: Any) -> Any:
                    tools_registered[fn.__name__] = fn
                    return fn

                return decorator

            mock_mcp_app.tool = capture_tool
            otel_tools.register_otel_tools(mock_mcp_app)

            await tools_registered["query_local_traces"](task_class="reasoning")

            assert "system_id" not in captured["arguments"]

    @pytest.mark.asyncio
    async def test_default_time_range_is_60(self) -> None:
        """Default time_range_minutes should be 60."""
        from crackerjack.mcp.tools import otel_tools

        captured: dict[str, Any] = {}

        async def capture_call(tool_name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
            captured["arguments"] = arguments
            return []

        with patch(
            "crackerjack.mcp.tools.otel_tools._call_akosha_mcp_tool", new=capture_call
        ):
            mock_mcp_app = MagicMock()
            tools_registered: dict[str, Any] = {}

            def capture_tool():
                def decorator(fn: Any) -> Any:
                    tools_registered[fn.__name__] = fn
                    return fn

                return decorator

            mock_mcp_app.tool = capture_tool
            otel_tools.register_otel_tools(mock_mcp_app)

            # Call with only required task_class
            await tools_registered["query_local_traces"](task_class="quick_task")

            assert captured["arguments"]["time_range_minutes"] == 60

    @pytest.mark.asyncio
    async def test_default_limit_is_100(self) -> None:
        """Default limit should be 100."""
        from crackerjack.mcp.tools import otel_tools

        captured: dict[str, Any] = {}

        async def capture_call(tool_name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
            captured["arguments"] = arguments
            return []

        with patch(
            "crackerjack.mcp.tools.otel_tools._call_akosha_mcp_tool", new=capture_call
        ):
            mock_mcp_app = MagicMock()
            tools_registered: dict[str, Any] = {}

            def capture_tool():
                def decorator(fn: Any) -> Any:
                    tools_registered[fn.__name__] = fn
                    return fn

                return decorator

            mock_mcp_app.tool = capture_tool
            otel_tools.register_otel_tools(mock_mcp_app)

            await tools_registered["query_local_traces"](task_class="swarm_task")

            assert captured["arguments"]["limit"] == 100
