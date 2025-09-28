import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from crackerjack.adapters.lsp_client import ZubanLSPClient


class TestZubanLSPClient:
    """Tests for ZubanLSPClient.

    This module contains comprehensive tests for the ZubanLSPClient class including:
    - Instantiation and basic functionality
    - Connection management
    - LSP protocol methods
    - Error handling
    """

    @pytest.fixture
    def client(self):
        """Create a ZubanLSPClient instance for testing."""
        return ZubanLSPClient(host="127.0.0.1", port=8677)

    def test_module_imports_successfully(self):
        """Test that the module can be imported without errors."""
        import crackerjack.adapters.lsp_client
        assert crackerjack.adapters.lsp_client is not None

    def test_client_instantiation(self, client):
        """Test successful instantiation of ZubanLSPClient."""
        assert client is not None
        assert isinstance(client, ZubanLSPClient)
        assert client.host == "127.0.0.1"
        assert client.port == 8677
        assert client._socket is None
        assert client._reader is None
        assert client._writer is None
        assert client._request_id == 0
        assert not client._initialized

    def test_next_request_id(self, client):
        """Test request ID generation."""
        assert client._next_request_id() == 1
        assert client._next_request_id() == 2
        assert client._request_id == 2

    @pytest.mark.asyncio
    async def test_connect_success(self, client):
        """Test successful connection."""
        with patch('asyncio.open_connection') as mock_open:
            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_open.return_value = (mock_reader, mock_writer)

            result = await client.connect()

            assert result is True
            assert client._reader is mock_reader
            assert client._writer is mock_writer
            mock_open.assert_called_once_with("127.0.0.1", 8677)

    @pytest.mark.asyncio
    async def test_connect_failure(self, client):
        """Test connection failure handling."""
        with patch('asyncio.open_connection') as mock_open:
            mock_open.side_effect = OSError("Connection failed")

            result = await client.connect()

            assert result is False
            assert client._reader is None
            assert client._writer is None

    @pytest.mark.asyncio
    async def test_disconnect_basic(self, client):
        """Test basic disconnect functionality."""
        # Set up mock writer
        mock_writer = AsyncMock()
        client._writer = mock_writer
        client._reader = AsyncMock()

        await client.disconnect()

        mock_writer.close.assert_called_once()
        mock_writer.wait_closed.assert_called_once()
        assert client._writer is None
        assert client._reader is None
        assert not client._initialized

    @pytest.mark.asyncio
    async def test_disconnect_with_shutdown(self, client):
        """Test disconnect with proper shutdown sequence."""
        mock_writer = AsyncMock()
        client._writer = mock_writer
        client._reader = AsyncMock()
        client._initialized = True

        with patch.object(client, '_send_request') as mock_request, \
             patch.object(client, '_send_notification') as mock_notification:

            await client.disconnect()

            mock_request.assert_called_once_with("shutdown")
            mock_notification.assert_called_once_with("exit")

    @pytest.mark.asyncio
    async def test_initialize_success(self, client):
        """Test successful initialization."""
        root_path = Path("/test/project")
        expected_response = {"capabilities": {"textDocument": {}}}

        with patch.object(client, '_send_request') as mock_request, \
             patch.object(client, '_send_notification') as mock_notification:

            mock_request.return_value = expected_response

            result = await client.initialize(root_path)

            assert result == expected_response
            assert client._initialized is True
            mock_request.assert_called_once()
            mock_notification.assert_called_once_with("initialized")

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, client):
        """Test initialization when already initialized."""
        client._initialized = True
        root_path = Path("/test/project")

        result = await client.initialize(root_path)

        assert result == {"status": "already_initialized"}

    @pytest.mark.asyncio
    async def test_text_document_did_open_success(self, client):
        """Test successful document open notification."""
        test_file = Path("/tmp/test.py")
        test_content = "print('hello')"

        with patch.object(test_file, 'exists', return_value=True), \
             patch.object(test_file, 'read_text', return_value=test_content), \
             patch.object(client, '_send_notification') as mock_notification:

            await client.text_document_did_open(test_file)

            mock_notification.assert_called_once()
            call_args = mock_notification.call_args
            assert call_args[0][0] == "textDocument/didOpen"
            assert "textDocument" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_text_document_did_open_file_not_exists(self, client):
        """Test document open with non-existent file."""
        test_file = Path("/nonexistent/test.py")

        with patch.object(test_file, 'exists', return_value=False), \
             patch.object(client, '_send_notification') as mock_notification:

            await client.text_document_did_open(test_file)

            mock_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_text_document_did_change(self, client):
        """Test document change notification."""
        test_file = Path("/tmp/test.py")
        test_content = "print('modified')"

        with patch.object(client, '_send_notification') as mock_notification:

            await client.text_document_did_change(test_file, test_content, version=3)

            mock_notification.assert_called_once()
            call_args = mock_notification.call_args
            assert call_args[0][0] == "textDocument/didChange"
            assert "textDocument" in call_args[0][1]
            assert call_args[0][1]["textDocument"]["version"] == 3

    @pytest.mark.asyncio
    async def test_text_document_did_close(self, client):
        """Test document close notification."""
        test_file = Path("/tmp/test.py")

        with patch.object(client, '_send_notification') as mock_notification:

            await client.text_document_did_close(test_file)

            mock_notification.assert_called_once()
            call_args = mock_notification.call_args
            assert call_args[0][0] == "textDocument/didClose"
            assert "textDocument" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_diagnostics(self, client):
        """Test diagnostics retrieval."""
        result = await client.get_diagnostics()

        assert isinstance(result, list)
        assert len(result) == 0  # Currently returns empty list

    @pytest.mark.asyncio
    async def test_context_manager(self, client):
        """Test async context manager functionality."""
        with patch.object(client, 'connect', return_value=True) as mock_connect, \
             patch.object(client, 'disconnect') as mock_disconnect:

            async with client as ctx_client:
                assert ctx_client is client
                mock_connect.assert_called_once()

            mock_disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_format(self, client):
        """Test LSP message formatting."""
        mock_writer = AsyncMock()
        client._writer = mock_writer

        test_message = {"jsonrpc": "2.0", "method": "test"}

        await client._send_message(test_message)

        mock_writer.write.assert_called_once()
        mock_writer.drain.assert_called_once()

        # Verify the message format includes Content-Length header
        written_data = mock_writer.write.call_args[0][0]
        assert b"Content-Length:" in written_data
        assert b"\r\n\r\n" in written_data
        assert b'"jsonrpc": "2.0"' in written_data

    def test_host_port_configuration(self):
        """Test custom host and port configuration."""
        custom_client = ZubanLSPClient(host="localhost", port=9999)

        assert custom_client.host == "localhost"
        assert custom_client.port == 9999
