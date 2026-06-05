"""Tests for ZubanLSPClient."""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestZubanLSPClient:
    """Test ZubanLSPClient TCP-based LSP client."""

    def test_initialization(self):
        """Test client initialization with default host/port."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        assert client.host == "127.0.0.1"
        assert client.port == 8677
        assert client._socket is None
        assert client._reader is None
        assert client._writer is None
        assert client._request_id == 0
        assert client._initialized is False

    def test_initialization_custom_host_port(self):
        """Test client initialization with custom host/port."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient(host="192.168.1.1", port=9000)
        assert client.host == "192.168.1.1"
        assert client.port == 9000

    def test_next_request_id(self):
        """Test request ID incrementing."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        assert client._next_request_id() == 1
        assert client._next_request_id() == 2
        assert client._next_request_id() == 3

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection to LSP server."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()

        mock_reader = AsyncMock()
        mock_writer = AsyncMock()

        with patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait_for:
            mock_wait_for.return_value = (mock_reader, mock_writer)

            result = await client.connect(timeout=5.0)

            assert result is True

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure handling."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()

        with patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait_for:
            mock_wait_for.side_effect = TimeoutError()

            result = await client.connect(timeout=5.0)

            assert result is False

    @pytest.mark.asyncio
    async def test_connect_os_error(self):
        """Test connection OS error handling."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()

        with patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait_for:
            mock_wait_for.side_effect = OSError("Connection refused")

            result = await client.connect(timeout=5.0)

            assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_not_initialized(self):
        """Test disconnect when not initialized."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        client._writer = AsyncMock()
        client._reader = AsyncMock()

        await client.disconnect()

        assert client._writer is None
        assert client._reader is None
        assert client._initialized is False

    @pytest.mark.asyncio
    async def test_disconnect_initialized(self):
        """Test disconnect when initialized sends shutdown/exit."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        mock_writer = AsyncMock()
        client._writer = mock_writer
        client._initialized = True

        with patch.object(client, "_send_request", new_callable=AsyncMock) as mock_send_req, \
             patch.object(client, "_send_notification", new_callable=AsyncMock) as mock_send_notif:

            await client.disconnect()

            mock_send_req.assert_called_once_with("shutdown")
            mock_send_notif.assert_called_once_with("exit")

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self):
        """Test initialize when already initialized."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        client._initialized = True

        result = await client.initialize(Path("/test/path"))

        assert result == {"status": "already_initialized"}

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Test successful initialization."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()

        with patch.object(client, "_send_request", new_callable=AsyncMock) as mock_send_req, \
             patch.object(client, "_send_notification", new_callable=AsyncMock) as mock_send_notif:

            mock_send_req.return_value = {"error": None}
            mock_send_notif.return_value = None

            result = await client.initialize(Path("/test/path"))

            assert result["error"] is None
            assert client._initialized is True
            mock_send_notif.assert_called_once_with("initialized")

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Test initialization failure."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()

        with patch.object(client, "_send_request", new_callable=AsyncMock) as mock_send_req:
            mock_send_req.return_value = {"error": "Failed"}

            result = await client.initialize(Path("/test/path"))

            assert result["error"] == "Failed"
            assert client._initialized is False

    @pytest.mark.asyncio
    async def test_text_document_did_open_file_not_exists(self):
        """Test textDocument/didOpen with non-existent file."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        non_existent = Path("/nonexistent/file.py")

        with patch.object(client, "_send_notification", new_callable=AsyncMock) as mock_send:
            await client.text_document_did_open(non_existent)

            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_text_document_did_open_success(self, tmp_path):
        """Test textDocument/didOpen sends correct notification."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        with patch.object(client, "_send_notification", new_callable=AsyncMock) as mock_send:
            await client.text_document_did_open(test_file)

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            method = call_args[0][0]
            params = call_args[0][1]

            assert method == "textDocument/didOpen"
            assert "textDocument" in params
            assert params["textDocument"]["languageId"] == "python"
            assert "text" in params["textDocument"]

    @pytest.mark.asyncio
    async def test_text_document_did_change(self, tmp_path):
        """Test textDocument/didChange sends correct notification."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        test_file = tmp_path / "test.py"

        with patch.object(client, "_send_notification", new_callable=AsyncMock) as mock_send:
            await client.text_document_did_change(test_file, "new content", version=3)

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            method = call_args[0][0]
            params = call_args[0][1]

            assert method == "textDocument/didChange"
            assert params["textDocument"]["version"] == 3

    @pytest.mark.asyncio
    async def test_text_document_did_close(self, tmp_path):
        """Test textDocument/didClose sends correct notification."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        test_file = tmp_path / "test.py"

        with patch.object(client, "_send_notification", new_callable=AsyncMock) as mock_send:
            await client.text_document_did_close(test_file)

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            method = call_args[0][0]

            assert method == "textDocument/didClose"

    @pytest.mark.asyncio
    async def test_get_diagnostics_returns_empty(self):
        """Test get_diagnostics returns empty list by default."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()

        result = await client.get_diagnostics()

        assert result == []

    @pytest.mark.asyncio
    async def test_send_request_no_writer(self):
        """Test _send_request returns None without writer."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        client._writer = None

        result = await client._send_request("test")

        assert result is None

    @pytest.mark.asyncio
    async def test_send_request_success(self):
        """Test _send_request success path."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        client._writer = AsyncMock()
        client._reader = AsyncMock()

        with patch.object(client, "_send_message", new_callable=AsyncMock), \
             patch.object(client, "_read_response", new_callable=AsyncMock) as mock_read:

            mock_read.return_value = {"id": 1, "result": {"status": "ok"}}

            result = await client._send_request("test", {"key": "value"})

            assert result == {"id": 1, "result": {"status": "ok"}}

    @pytest.mark.asyncio
    async def test_send_request_timeout(self):
        """Test _send_request handles timeout."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        client._writer = AsyncMock()
        client._reader = AsyncMock()

        with patch.object(client, "_send_message", new_callable=AsyncMock), \
             patch.object(client, "_read_response", new_callable=AsyncMock) as mock_read:

            mock_read.side_effect = TimeoutError()

            result = await client._send_request("test", {"key": "value"})

            assert result == {"error": "timeout", "id": 1}

    @pytest.mark.asyncio
    async def test_send_notification_no_writer(self):
        """Test _send_notification returns None without writer."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        client._writer = None

        result = await client._send_notification("test")

        assert result is None

    @pytest.mark.asyncio
    async def test_send_notification_success(self):
        """Test _send_notification success."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        client._writer = AsyncMock()

        with patch.object(client, "_send_message", new_callable=AsyncMock) as mock_send:
            await client._send_notification("test", {"param": "value"})

            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test _send_message writes correct LSP format."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        client._writer = AsyncMock()

        message = {"jsonrpc": "2.0", "method": "test"}
        await client._send_message(message)

        client._writer.write.assert_called_once()
        client._writer.drain.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_response_returns_none_when_no_reader(self):
        """Test _read_response returns None when no reader."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        client._reader = None

        result = await client._read_response(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_read_message_returns_none_when_no_reader(self):
        """Test _read_message returns None when no reader."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        client._reader = None

        result = await client._read_message()

        assert result is None

    @pytest.mark.asyncio
    async def test_read_message_invalid_header(self):
        """Test _read_message handles invalid header."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()
        client._reader = AsyncMock()
        client._reader.readline.return_value = b"Invalid Header\r\n"

        result = await client._read_message()

        assert result is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager protocol."""
        from crackerjack.adapters.lsp._client import ZubanLSPClient

        client = ZubanLSPClient()

        with patch.object(client, "connect", new_callable=AsyncMock) as mock_connect, \
             patch.object(client, "disconnect", new_callable=AsyncMock) as mock_disconnect:

            mock_connect.return_value = True

            async with client as c:
                assert c == client

            mock_disconnect.assert_called_once()
