"""LSP client wrapper for Zuban communication."""

import asyncio
import json
import logging
import socket
import typing as t
from pathlib import Path

logger = logging.getLogger("crackerjack.lsp_client")


class ZubanLSPClient:
    """Minimal LSP client for zuban communication."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8677) -> None:
        """Initialize LSP client.

        Args:
            host: LSP server host
            port: LSP server port
        """
        self.host = host
        self.port = port
        self._socket: socket.socket | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._request_id = 0
        self._initialized = False

    def _next_request_id(self) -> int:
        """Generate next request ID."""
        self._request_id += 1
        return self._request_id

    async def connect(self, timeout: float = 5.0) -> bool:
        """Connect to zuban LSP server.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if connected successfully
        """
        try:
            # Attempt TCP connection
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=timeout
            )

            logger.info(f"Connected to Zuban LSP server at {self.host}:{self.port}")
            return True

        except (TimeoutError, OSError) as e:
            logger.warning(f"Failed to connect to LSP server: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from LSP server."""
        if self._writer:
            try:
                # Send shutdown request
                if self._initialized:
                    await self._send_request("shutdown")
                    await self._send_notification("exit")

                self._writer.close()
                await self._writer.wait_closed()

            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self._writer = None
                self._reader = None
                self._initialized = False

    async def initialize(self, root_path: Path) -> dict[str, t.Any] | None:
        """Send initialize request.

        Args:
            root_path: Workspace root path

        Returns:
            Initialize response from server
        """
        if self._initialized:
            return {"status": "already_initialized"}

        params = {
            "processId": None,
            "rootPath": str(root_path),
            "rootUri": f"file://{root_path}",
            "capabilities": {
                "textDocument": {
                    "publishDiagnostics": {
                        "versionSupport": True,
                        "tagSupport": {"valueSet": [1, 2]},
                        "relatedInformation": True,
                    }
                },
                "workspace": {
                    "workspaceFolders": True,
                    "configuration": True,
                },
            },
            "workspaceFolders": [
                {"uri": f"file://{root_path}", "name": root_path.name}
            ],
        }

        response = await self._send_request("initialize", params)
        if response and not response.get("error"):
            # Send initialized notification
            await self._send_notification("initialized")
            self._initialized = True
            logger.info("LSP client initialized successfully")

        return response

    async def text_document_did_open(self, file_path: Path) -> None:
        """Notify server of opened document.

        Args:
            file_path: Path to opened file
        """
        if not file_path.exists():
            logger.warning(f"File does not exist: {file_path}")
            return

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.warning(f"Could not read file as UTF-8: {file_path}")
            return

        params = {
            "textDocument": {
                "uri": f"file://{file_path}",
                "languageId": "python",
                "version": 1,
                "text": content,
            }
        }

        await self._send_notification("textDocument/didOpen", params)

    async def text_document_did_change(
        self, file_path: Path, content: str, version: int = 2
    ) -> None:
        """Notify server of document changes.

        Args:
            file_path: Path to changed file
            content: New file content
            version: Document version number
        """
        params = {
            "textDocument": {
                "uri": f"file://{file_path}",
                "version": version,
            },
            "contentChanges": [{"text": content}],
        }

        await self._send_notification("textDocument/didChange", params)

    async def text_document_did_close(self, file_path: Path) -> None:
        """Notify server of closed document.

        Args:
            file_path: Path to closed file
        """
        params = {
            "textDocument": {
                "uri": f"file://{file_path}",
            }
        }

        await self._send_notification("textDocument/didClose", params)

    async def get_diagnostics(self, timeout: float = 2.0) -> list[dict[str, t.Any]]:
        """Retrieve current diagnostics from server.

        Args:
            timeout: Timeout for waiting for diagnostics

        Returns:
            List of diagnostic messages
        """
        # For now, return empty list[t.Any] as diagnostics are typically pushed via notifications
        # In a full implementation, we'd maintain a diagnostics store updated by notifications
        return []

    async def _send_request(
        self, method: str, params: dict[str, t.Any] | None = None, timeout: float = 10.0
    ) -> dict[str, t.Any] | None:
        """Send LSP request and wait for response.

        Args:
            method: LSP method name
            params: Request parameters
            timeout: Response timeout

        Returns:
            Response from server
        """
        if not self._writer or not self._reader:
            return None

        request_id = self._next_request_id()
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }

        if params is not None:
            request["params"] = params

        try:
            # Send request
            await self._send_message(request)

            # Wait for response
            response = await asyncio.wait_for(
                self._read_response(request_id), timeout=timeout
            )

            return response

        except TimeoutError:
            logger.warning(f"LSP request {method} timed out")
            return {"error": "timeout", "id": request_id}
        except Exception as e:
            logger.error(f"LSP request {method} failed: {e}")
            return {"error": str(e), "id": request_id}

    async def _send_notification(
        self, method: str, params: dict[str, t.Any] | None = None
    ) -> None:
        """Send LSP notification (no response expected).

        Args:
            method: LSP method name
            params: Notification parameters
        """
        if not self._writer:
            return

        notification: dict[str, t.Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }

        if params is not None:
            notification["params"] = params

        try:
            await self._send_message(notification)
        except Exception as e:
            logger.error(f"LSP notification {method} failed: {e}")

    async def _send_message(self, message: dict[str, t.Any]) -> None:
        """Send LSP message with proper formatting.

        Args:
            message: Message to send
        """
        if not self._writer:
            return

        content_bytes = json.dumps(message).encode("utf-8")
        content_length = len(content_bytes)

        # LSP protocol: Content-Length header + \r\n\r\n + JSON
        header = f"Content-Length: {content_length}\r\n\r\n"
        full_message = header.encode("ascii") + content_bytes

        self._writer.write(full_message)
        await self._writer.drain()

    async def _read_response(self, expected_id: int) -> dict[str, t.Any] | None:
        """Read LSP response for specific request ID.

        Args:
            expected_id: Expected request ID

        Returns:
            Response message
        """
        while True:
            message = await self._read_message()
            if not message:
                return None

            # Check if this is the response we're waiting for
            if message.get("id") == expected_id:
                return message

            # If it's a different response or notification, log and continue
            if "id" in message:
                logger.debug(
                    f"Received response for ID {message['id']}, expected {expected_id}"
                )
            else:
                logger.debug(
                    f"Received notification: {message.get('method', 'unknown')}"
                )

    async def _read_message(self) -> dict[str, t.Any] | None:
        """Read complete LSP message.

        Returns:
            Parsed message dictionary
        """
        if not self._reader:
            return None

        try:
            # Read Content-Length header
            header_line = await self._reader.readline()
            header_str = header_line.decode("ascii").strip()

            if not header_str.startswith("Content-Length:"):
                logger.warning(f"Invalid LSP header: {header_str}")
                return None

            content_length = int(header_str.split(":", 1)[1].strip())

            # Read separator line
            separator = await self._reader.readline()
            if separator.strip():
                logger.warning("Expected empty separator line")

            # Read JSON content
            content_bytes = await self._reader.readexactly(content_length)
            content = content_bytes.decode()

            json_result = json.loads(content)
            return t.cast(dict[str, t.Any] | None, json_result)

        except Exception as e:
            logger.error(f"Failed to read LSP message: {e}")
            return None

    async def __aenter__(self) -> "ZubanLSPClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
        """Async context manager exit."""
        await self.disconnect()
