"""WebSocket and network resource lifecycle management.

Provides comprehensive cleanup patterns for WebSocket connections,
HTTP clients, and network resources to prevent resource leaks.
"""

import asyncio
import contextlib
import logging
import socket
import subprocess
import time
import typing as t

import aiohttp
import websockets

from .resource_manager import ManagedResource, ResourceManager


class ManagedWebSocketConnection(ManagedResource):
    """WebSocket connection with automatic cleanup on error scenarios."""

    def __init__(
        self,
        websocket: t.Any,  # websockets protocols have import issues
        manager: ResourceManager | None = None,
    ) -> None:
        super().__init__(manager)
        self.websocket = websocket
        self.logger = logging.getLogger(__name__)

    async def cleanup(self) -> None:
        """Clean up WebSocket connection."""
        if not self._closed and not self.websocket.closed:
            self._closed = True

            try:
                await asyncio.wait_for(self.websocket.close(), timeout=5.0)
            except (TimeoutError, websockets.ConnectionClosed):
                # Expected when connection is already closed or times out
                pass
            except Exception as e:
                self.logger.warning(f"Error closing WebSocket connection: {e}")

    async def send_safe(self, message: str) -> bool:
        """Send message safely, returning True if successful."""
        if self._closed or self.websocket.closed:
            return False

        try:
            await self.websocket.send(message)
            return True
        except (websockets.ConnectionClosed, websockets.InvalidState):
            await self.cleanup()
            return False
        except Exception as e:
            self.logger.warning(f"Error sending WebSocket message: {e}")
            await self.cleanup()
            return False


class ManagedHTTPClient(ManagedResource):
    """HTTP client session with automatic cleanup."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        manager: ResourceManager | None = None,
    ) -> None:
        super().__init__(manager)
        self.session = session

    async def cleanup(self) -> None:
        """Clean up HTTP client session."""
        if not self._closed and not self.session.closed:
            self._closed = True

            try:
                await self.session.close()
            except Exception as e:
                logging.getLogger(__name__).warning(f"Error closing HTTP session: {e}")


class ManagedWebSocketServer(ManagedResource):
    """WebSocket server with comprehensive lifecycle management."""

    def __init__(
        self,
        port: int,
        host: str = "127.0.0.1",
        manager: ResourceManager | None = None,
    ) -> None:
        super().__init__(manager)
        self.port = port
        self.host = host
        self.server: t.Any | None = None  # websockets server type has import issues
        self.connections: set[ManagedWebSocketConnection] = set()
        self.logger = logging.getLogger(__name__)
        self._server_task: asyncio.Task[t.Any] | None = None

    async def start(
        self,
        handler: t.Callable[[t.Any], t.Awaitable[None]],
    ) -> None:
        """Start the WebSocket server."""
        if self.server:
            return

        # Wrap handler to manage connections
        async def managed_handler(
            websocket: t.Any,  # websocket protocol type
        ) -> None:
            managed_conn = ManagedWebSocketConnection(websocket, self.manager)
            self.connections.add(managed_conn)

            try:
                await handler(websocket)
            finally:
                self.connections.discard(managed_conn)
                await managed_conn.cleanup()

        self.server = await websockets.serve(
            managed_handler,
            self.host,
            self.port,
            # Configure timeouts and limits
            ping_interval=20,
            ping_timeout=10,
            close_timeout=10,
            max_size=2**20,  # 1MB
            max_queue=32,
        )

        self.logger.info(f"WebSocket server started on {self.host}:{self.port}")

    async def cleanup(self) -> None:
        """Clean up WebSocket server and all connections."""
        if self._closed:
            return
        self._closed = True

        # Close all active connections
        if self.connections:
            close_tasks = [
                asyncio.create_task(conn.cleanup()) for conn in list(self.connections)
            ]

            if close_tasks:
                await asyncio.gather(*close_tasks, return_exceptions=True)

        self.connections.clear()

        # Close server
        if self.server:
            try:
                self.server.close()
                await self.server.wait_closed()
                self.logger.info("WebSocket server closed successfully")
            except Exception as e:
                self.logger.warning(f"Error closing WebSocket server: {e}")
            finally:
                self.server = None

    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len([conn for conn in self.connections if not conn._closed])


class ManagedSubprocess(ManagedResource):
    """Subprocess with enhanced lifecycle management and resource cleanup."""

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        timeout: float = 30.0,
        manager: ResourceManager | None = None,
    ) -> None:
        super().__init__(manager)
        self.process = process
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        self._monitor_task: asyncio.Task[t.Any] | None = None

    async def start_monitoring(self) -> None:
        """Start monitoring the process for unexpected termination."""
        if self._monitor_task:
            return

        self._monitor_task = asyncio.create_task(self._monitor_process())

    async def _monitor_process(self) -> None:
        """Monitor process health and log unexpected terminations."""
        try:
            while self.process.poll() is None:
                await asyncio.sleep(5.0)

            # Process has terminated
            return_code = self.process.returncode
            if return_code != 0:
                self.logger.warning(
                    f"Process {self.process.pid} terminated with code {return_code}"
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.warning(f"Error monitoring process: {e}")

    async def cleanup(self) -> None:
        """Clean up subprocess with graceful termination."""
        if self._closed:
            return
        self._closed = True

        # Cancel monitoring
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Clean up process
        if self.process.poll() is None:
            try:
                # Try graceful termination first
                self.process.terminate()

                try:
                    self.process.wait(timeout=5.0)
                    self.logger.debug(
                        f"Process {self.process.pid} terminated gracefully"
                    )
                except subprocess.TimeoutExpired:
                    # Force kill if graceful termination fails
                    self.process.kill()
                    try:
                        self.process.wait(timeout=2.0)
                        self.logger.warning(f"Process {self.process.pid} force killed")
                    except subprocess.TimeoutExpired:
                        self.logger.error(
                            f"Process {self.process.pid} did not terminate after force kill"
                        )

            except ProcessLookupError:
                # Process already terminated
                pass
            except Exception as e:
                self.logger.warning(
                    f"Error cleaning up process {self.process.pid}: {e}"
                )

    def is_running(self) -> bool:
        """Check if the process is still running."""
        return not self._closed and self.process.poll() is None


class NetworkResourceManager:
    """Manager for network-related resources with health monitoring."""

    def __init__(self) -> None:
        self.resource_manager = ResourceManager()
        self.logger = logging.getLogger(__name__)

    async def create_websocket_server(
        self,
        port: int,
        host: str = "127.0.0.1",
    ) -> ManagedWebSocketServer:
        """Create a managed WebSocket server."""
        server = ManagedWebSocketServer(port, host, self.resource_manager)
        return server

    async def create_http_client(
        self,
        timeout: aiohttp.ClientTimeout | None = None,
        **kwargs: t.Any,
    ) -> ManagedHTTPClient:
        """Create a managed HTTP client session."""
        timeout = timeout or aiohttp.ClientTimeout(total=30.0)
        session = aiohttp.ClientSession(timeout=timeout, **kwargs)
        return ManagedHTTPClient(session, self.resource_manager)

    def create_subprocess(
        self,
        process: subprocess.Popen[bytes],
        timeout: float = 30.0,
    ) -> ManagedSubprocess:
        """Create a managed subprocess."""
        return ManagedSubprocess(process, timeout, self.resource_manager)

    async def check_port_available(self, port: int, host: str = "127.0.0.1") -> bool:
        """Check if a port is available for binding."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.0)
                result = sock.connect_ex((host, port))
                return result != 0  # Port is available if connection fails
        except Exception:
            return False

    async def wait_for_port(
        self,
        port: int,
        host: str = "127.0.0.1",
        timeout: float = 30.0,
        poll_interval: float = 0.5,
    ) -> bool:
        """Wait for a port to become available (service to start)."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            with contextlib.suppress(Exception):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1.0)
                    result = sock.connect_ex((host, port))
                    if result == 0:  # Connection successful
                        return True

            await asyncio.sleep(poll_interval)

        return False

    async def cleanup_all(self) -> None:
        """Clean up all managed network resources."""
        await self.resource_manager.cleanup_all()

    async def __aenter__(self) -> "NetworkResourceManager":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: type[BaseException] | None,
    ) -> None:
        await self.cleanup_all()


# Context manager helpers for common network resource patterns
@contextlib.asynccontextmanager
async def with_websocket_server(
    port: int,
    handler: t.Callable[[t.Any], t.Awaitable[None]],
    host: str = "127.0.0.1",
):
    """Context manager for a WebSocket server with automatic cleanup."""
    async with NetworkResourceManager() as manager:
        server = await manager.create_websocket_server(port, host)
        try:
            await server.start(handler)
            yield server
        finally:
            await server.cleanup()


@contextlib.asynccontextmanager
async def with_http_client(**kwargs: t.Any):
    """Context manager for an HTTP client with automatic cleanup."""
    async with NetworkResourceManager() as manager:
        client = await manager.create_http_client(**kwargs)
        try:
            yield client.session
        finally:
            await client.cleanup()


@contextlib.asynccontextmanager
async def with_managed_subprocess(
    command: list[str],
    timeout: float = 30.0,
    **popen_kwargs: t.Any,
):
    """Context manager for a subprocess with automatic cleanup."""
    async with NetworkResourceManager() as manager:
        # Ensure we get bytes output for consistent type handling
        process = subprocess.Popen[bytes](command, text=False, **popen_kwargs)
        managed_proc = manager.create_subprocess(process, timeout)
        try:
            await managed_proc.start_monitoring()
            yield managed_proc
        finally:
            await managed_proc.cleanup()


class WebSocketHealthMonitor:
    """Health monitor for WebSocket connections and servers."""

    def __init__(self, check_interval: float = 30.0) -> None:
        self.check_interval = check_interval
        self.monitored_servers: list[ManagedWebSocketServer] = []
        self.logger = logging.getLogger(__name__)
        self._monitor_task: asyncio.Task[t.Any] | None = None

    def add_server(self, server: ManagedWebSocketServer) -> None:
        """Add a server to health monitoring."""
        self.monitored_servers.append(server)

    def remove_server(self, server: ManagedWebSocketServer) -> None:
        """Remove a server from health monitoring."""
        if server in self.monitored_servers:
            self.monitored_servers.remove(server)

    async def start_monitoring(self) -> None:
        """Start health monitoring."""
        if self._monitor_task:
            return

        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while True:
                for server in self.monitored_servers.copy():
                    try:
                        await self._check_server_health(server)
                    except Exception as e:
                        self.logger.warning(f"Health check failed for server: {e}")

                await asyncio.sleep(self.check_interval)

        except asyncio.CancelledError:
            pass

    async def _check_server_health(self, server: ManagedWebSocketServer) -> None:
        """Check health of a specific server."""
        if server._closed:
            self.remove_server(server)
            return

        connection_count = server.get_connection_count()

        # Log health metrics
        self.logger.debug(
            f"Server {server.host}:{server.port} - "
            f"Active connections: {connection_count}"
        )

        # Could add more sophisticated health checks here:
        # - Memory usage monitoring
        # - Connection rate limiting
        # - Error rate monitoring
        # - Automatic restart on failure


# Global network resource cleanup
_global_network_managers: list[NetworkResourceManager] = []


def register_network_manager(manager: NetworkResourceManager) -> None:
    """Register a network resource manager for global cleanup."""
    _global_network_managers.append(manager)


async def cleanup_all_network_resources() -> None:
    """Clean up all globally registered network resource managers."""
    cleanup_tasks = [
        asyncio.create_task(manager.cleanup_all())
        for manager in _global_network_managers
    ]

    if cleanup_tasks:
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)

    _global_network_managers.clear()
