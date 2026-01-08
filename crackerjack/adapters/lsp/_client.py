import asyncio
import json
import logging
import socket
import typing as t
from pathlib import Path

logger = logging.getLogger("crackerjack.lsp_client")


class ZubanLSPClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 8677) -> None:
        self.host = host
        self.port = port
        self._socket: socket.socket | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._request_id = 0
        self._initialized = False

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def connect(self, timeout: float = 5.0) -> bool:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=timeout
            )

            logger.info(f"Connected to Zuban LSP server at {self.host}:{self.port}")
            return True

        except (TimeoutError, OSError) as e:
            logger.warning(f"Failed to connect to LSP server: {e}")
            return False

    async def disconnect(self) -> None:
        if self._writer:
            try:
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
            await self._send_notification("initialized")
            self._initialized = True
            logger.info("LSP client initialized successfully")

        return response

    async def text_document_did_open(self, file_path: Path) -> None:
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
        params = {
            "textDocument": {
                "uri": f"file://{file_path}",
                "version": version,
            },
            "contentChanges": [{"text": content}],
        }

        await self._send_notification("textDocument/didChange", params)

    async def text_document_did_close(self, file_path: Path) -> None:
        params = {
            "textDocument": {
                "uri": f"file://{file_path}",
            }
        }

        await self._send_notification("textDocument/didClose", params)

    async def get_diagnostics(self, timeout: float = 2.0) -> list[dict[str, t.Any]]:
        return []

    async def _send_request(
        self, method: str, params: dict[str, t.Any] | None = None, timeout: float = 10.0
    ) -> dict[str, t.Any] | None:
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
            await self._send_message(request)

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
        if not self._writer:
            return

        content_bytes = json.dumps(message).encode("utf-8")
        content_length = len(content_bytes)

        header = f"Content-Length: {content_length}\r\n\r\n"
        full_message = header.encode("ascii") + content_bytes

        self._writer.write(full_message)
        await self._writer.drain()

    async def _read_response(self, expected_id: int) -> dict[str, t.Any] | None:
        while True:
            message = await self._read_message()
            if not message:
                return None

            if message.get("id") == expected_id:
                return message

            if "id" in message:
                logger.debug(
                    f"Received response for ID {message['id']}, expected {expected_id}"
                )
            else:
                logger.debug(
                    f"Received notification: {message.get('method', 'unknown')}"
                )

    async def _read_message(self) -> dict[str, t.Any] | None:
        if not self._reader:
            return None

        try:
            header_line = await self._reader.readline()
            header_str = header_line.decode("ascii").strip()

            if not header_str.startswith("Content-Length:"):
                logger.warning(f"Invalid LSP header: {header_str}")
                return None

            content_length = int(header_str.split(":", 1)[1].strip())

            separator = await self._reader.readline()
            if separator.strip():
                logger.warning("Expected empty separator line")

            content_bytes = await self._reader.readexactly(content_length)
            content = content_bytes.decode()

            json_result = json.loads(content)
            return t.cast(dict[str, t.Any] | None, json_result)

        except Exception as e:
            logger.error(f"Failed to read LSP message: {e}")
            return None

    async def __aenter__(self) -> "ZubanLSPClient":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
        await self.disconnect()
