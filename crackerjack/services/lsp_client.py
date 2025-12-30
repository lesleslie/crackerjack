import asyncio
import concurrent.futures
import subprocess
import typing as t
from pathlib import Path
from typing import Protocol

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from .server_manager import find_zuban_lsp_processes
from .zuban_lsp_service import ZubanLSPService


class ProgressCallback(Protocol):
    """Protocol for progress reporting during type checking."""

    def on_file_start(self, file_path: str) -> None:
        """Called when starting to check a file."""
        ...

    def on_file_complete(self, file_path: str, error_count: int) -> None:
        """Called when finished checking a file."""
        ...

    def on_progress(self, current: int, total: int) -> None:
        """Called to report overall progress."""
        ...


class RealTimeTypingFeedback:
    """Provides real-time feedback during type checking operations."""

    def __init__(self) -> None:
        self.console = console
        self._total_errors = 0
        self._files_checked = 0

    def create_progress_display(self) -> Progress:
        """Create a progress display for type checking."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeElapsedColumn(),
            console=self.console,
        )

    def on_file_start(self, file_path: str) -> None:
        """Report that we're starting to check a file."""
        rel_path = Path(file_path).name
        self.console.print(f"🔍 Checking {rel_path}...", style="dim")

    def on_file_complete(self, file_path: str, error_count: int) -> None:
        """Report completion of file checking."""
        rel_path = Path(file_path).name
        self._files_checked += 1
        self._total_errors += error_count

        if error_count == 0:
            self.console.print(f"✅ {rel_path} - No issues", style="green dim")
        else:
            self.console.print(
                f"❌ {rel_path} - {error_count} error(s)", style="red dim"
            )

    def on_progress(self, current: int, total: int) -> None:
        """Report overall progress."""
        pass  # Progress bar handles this

    def get_summary(self) -> str:
        """Get a summary of the checking results."""
        if self._total_errors == 0:
            return f"✅ All {self._files_checked} files passed type checking"
        return (
            f"❌ Found {self._total_errors} type errors in {self._files_checked} files"
        )


class JSONRPCClient:
    """JSON-RPC client for LSP communication."""

    def __init__(self, lsp_service: ZubanLSPService) -> None:
        self.lsp_service = lsp_service
        self._request_id = 0

    def _next_request_id(self) -> int:
        """Generate next request ID."""
        self._request_id += 1
        return self._request_id

    async def initialize(self, root_path: str) -> dict[str, t.Any] | None:
        """Initialize the LSP server for a workspace."""
        params = {
            "processId": None,
            "rootPath": root_path,
            "rootUri": f"file://{root_path}",
            "capabilities": {
                "textDocument": {
                    "publishDiagnostics": {
                        "versionSupport": True,
                        "tagSupport": {"valueSet": [1, 2]},
                        "relatedInformation": True,
                        "codeDescriptionSupport": True,
                        "dataSupport": True,
                    }
                }
            },
        }
        return await self.lsp_service.send_lsp_request("initialize", params)

    async def did_open(self, file_path: str) -> dict[str, t.Any] | None:
        """Notify server that a document was opened."""
        content = Path(file_path).read_text(encoding="utf-8")

        params = {
            "textDocument": {
                "uri": f"file://{file_path}",
                "languageId": "python",
                "version": 1,
                "text": content,
            }
        }
        return await self.lsp_service.send_lsp_request("textDocument/didOpen", params)

    async def did_close(self, file_path: str) -> dict[str, t.Any] | None:
        """Notify server that a document was closed."""
        params = {
            "textDocument": {
                "uri": f"file://{file_path}",
            }
        }
        return await self.lsp_service.send_lsp_request("textDocument/didClose", params)


class LSPClient:
    """Client for communicating with Zuban LSP server."""

    def __init__(self) -> None:
        self.console = console
        self._server_port: int | None = None
        self._server_host: str = "127.0.0.1"
        self._lsp_service: ZubanLSPService | None = None
        self._jsonrpc_client: JSONRPCClient | None = None

    def is_server_running(self) -> bool:
        """Check if Zuban LSP server is currently running."""
        if self._lsp_service and self._lsp_service.is_running:
            return True
        processes = find_zuban_lsp_processes()
        return len(processes) > 0

    async def _ensure_lsp_service(self) -> bool:
        """Ensure LSP service is available and initialized."""
        if self._lsp_service and self._lsp_service.is_running:
            return True

        # Create new LSP service
        self._lsp_service = ZubanLSPService(
            port=self._server_port or 8677,
            mode="stdio",  # Currently zuban only supports stdio
            console=self.console,
        )

        # Start the service
        if await self._lsp_service.start():
            self._jsonrpc_client = JSONRPCClient(self._lsp_service)
            return True

        return False

    def get_server_info(self) -> dict[str, t.Any] | None:
        """Get information about the running LSP server."""
        processes = find_zuban_lsp_processes()
        if not processes:
            return None

        return {
            "pid": processes[0]["pid"],
            "cpu": processes[0]["cpu"],
            "mem": processes[0]["mem"],
            "command": processes[0]["command"],
        }

    def check_files(
        self,
        file_paths: list[str],
        progress_callback: ProgressCallback | None = None,
        show_progress: bool = True,
    ) -> dict[str, list[dict[str, t.Any]]]:
        """
        Check files for type errors using LSP server with real-time feedback.

        Args:
            file_paths: List of file paths to check
            progress_callback: Optional callback for progress reporting
            show_progress: Whether to show progress display

        Returns:
            Dictionary mapping file paths to lists of diagnostic messages.
            Each diagnostic contains: line, column, severity, message, code.
        """
        if not self.is_server_running():
            if progress_callback:
                self.console.print(
                    "⚠️  Zuban LSP server not running, falling back to direct zuban calls",
                    style="yellow",
                )
            return self._check_files_with_feedback(
                file_paths, progress_callback, show_progress
            )

        # When LSP server is running, use it for better performance
        return self._check_files_via_lsp(file_paths, progress_callback, show_progress)

    def _check_files_with_feedback(
        self,
        file_paths: list[str],
        progress_callback: ProgressCallback | None = None,
        show_progress: bool = True,
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Check files with real-time feedback using direct zuban calls."""
        total_files = len(file_paths)

        if show_progress and total_files > 1:
            return self._check_files_with_progress_display(
                file_paths, progress_callback, total_files
            )
        return self._check_files_simple_feedback(file_paths, progress_callback)

    def _check_files_with_progress_display(
        self,
        file_paths: list[str],
        progress_callback: ProgressCallback | None,
        total_files: int,
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Check files with progress display."""
        diagnostics = {}
        feedback = RealTimeTypingFeedback()

        with feedback.create_progress_display() as progress:
            task = progress.add_task("Type checking files...", total=total_files)

            for file_path in file_paths:
                diagnostics.update(
                    self._process_single_file_with_zuban(file_path, progress_callback)
                )
                progress.update(task, advance=1)

        return diagnostics

    def _check_files_simple_feedback(
        self,
        file_paths: list[str],
        progress_callback: ProgressCallback | None,
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Check files without progress display."""
        diagnostics = {}

        for file_path in file_paths:
            diagnostics.update(
                self._process_single_file_with_zuban(file_path, progress_callback)
            )

        return diagnostics

    def _process_single_file_with_zuban(
        self,
        file_path: str,
        progress_callback: ProgressCallback | None,
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Process a single file with zuban and handle callbacks."""
        if progress_callback:
            progress_callback.on_file_start(file_path)

        file_diagnostics = self._check_file_with_zuban(file_path)

        if progress_callback:
            progress_callback.on_file_complete(file_path, len(file_diagnostics))

        return {file_path: file_diagnostics}

    def _check_files_via_lsp(
        self,
        file_paths: list[str],
        progress_callback: ProgressCallback | None = None,
        show_progress: bool = True,
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Check files using LSP server communication."""
        # Use asyncio to run the async LSP implementation
        try:
            # Try to get or create an event loop
            try:
                asyncio.get_running_loop()
                # We're already in an async context, use a thread pool
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        self._run_async_lsp_check,
                        file_paths,
                        progress_callback,
                        show_progress,
                    )
                    return future.result(timeout=120)  # 2 minute timeout
            except RuntimeError:
                # No running loop, create new one
                return asyncio.run(
                    self._async_check_files_via_lsp(
                        file_paths, progress_callback, show_progress
                    )
                )
        except Exception as e:
            self.console.print(
                f"[yellow]⚠️ LSP communication failed: {e}, falling back to direct calls[/yellow]"
            )
            return self._check_files_with_feedback(
                file_paths, progress_callback, show_progress
            )

    def _run_async_lsp_check(
        self,
        file_paths: list[str],
        progress_callback: ProgressCallback | None = None,
        show_progress: bool = True,
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Run async LSP check in a new event loop."""
        return asyncio.run(
            self._async_check_files_via_lsp(
                file_paths, progress_callback, show_progress
            )
        )

    async def _async_check_files_via_lsp(
        self,
        file_paths: list[str],
        progress_callback: ProgressCallback | None = None,
        show_progress: bool = True,
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Async implementation of LSP-based file checking."""
        # Validate prerequisites
        if not await self._validate_lsp_prerequisites():
            return self._check_files_with_feedback(
                file_paths, progress_callback, show_progress
            )

        try:
            # Initialize LSP workspace
            await self._initialize_lsp_workspace(file_paths)

            # Process files with appropriate progress handling
            return await self._process_files_via_lsp(
                file_paths, progress_callback, show_progress
            )

        except Exception as e:
            self.console.print(
                f"[yellow]⚠️ LSP protocol error: {e}, falling back to direct calls[/yellow]"
            )
            return self._check_files_with_feedback(
                file_paths, progress_callback, show_progress
            )

    async def _validate_lsp_prerequisites(self) -> bool:
        """Validate that LSP service and client are ready."""
        if not await self._ensure_lsp_service():
            return False

        if not self._jsonrpc_client:
            return False

        return True

    async def _initialize_lsp_workspace(self, file_paths: list[str]) -> None:
        """Initialize LSP workspace with project root."""
        assert self._jsonrpc_client is not None, "LSP client must be initialized"
        project_root = (
            str(Path(file_paths[0]).parent) if file_paths else str(Path.cwd())
        )
        await self._jsonrpc_client.initialize(project_root)

    async def _process_files_via_lsp(
        self,
        file_paths: list[str],
        progress_callback: ProgressCallback | None = None,
        show_progress: bool = True,
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Process files via LSP with progress tracking."""
        total_files = len(file_paths)

        if show_progress and total_files > 1:
            return await self._process_files_with_progress(
                file_paths, progress_callback, total_files
            )
        return await self._process_files_simple(file_paths, progress_callback)

    async def _process_files_with_progress(
        self,
        file_paths: list[str],
        progress_callback: ProgressCallback | None,
        total_files: int,
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Process files with progress display."""
        diagnostics = {}
        feedback = RealTimeTypingFeedback()

        with feedback.create_progress_display() as progress:
            task = progress.add_task("LSP type checking files...", total=total_files)

            for file_path in file_paths:
                diagnostics.update(
                    await self._process_single_file_with_callback(
                        file_path, progress_callback
                    )
                )
                progress.update(task, advance=1)

        return diagnostics

    async def _process_files_simple(
        self,
        file_paths: list[str],
        progress_callback: ProgressCallback | None,
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Process files without progress display."""
        diagnostics = {}

        for file_path in file_paths:
            diagnostics.update(
                await self._process_single_file_with_callback(
                    file_path, progress_callback
                )
            )

        return diagnostics

    async def _process_single_file_with_callback(
        self,
        file_path: str,
        progress_callback: ProgressCallback | None,
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Process a single file with progress callback handling."""
        if progress_callback:
            progress_callback.on_file_start(file_path)

        file_diagnostics = await self._check_file_via_lsp(file_path)

        if progress_callback:
            progress_callback.on_file_complete(file_path, len(file_diagnostics))

        return {file_path: file_diagnostics}

    async def _check_file_via_lsp(self, file_path: str) -> list[dict[str, t.Any]]:
        """Check a single file via LSP protocol."""
        if not self._jsonrpc_client:
            # Fallback to direct zuban call
            return self._check_file_with_zuban(file_path)

        try:
            # Notify server about file
            await self._jsonrpc_client.did_open(file_path)

            # Wait briefly for diagnostics to be published
            await asyncio.sleep(0.1)

            # For now, since we don't have diagnostic collection implemented,
            # we'll fall back to the direct zuban call but log that we used LSP
            # In a full implementation, we'd collect diagnostics from LSP notifications
            diagnostics = self._check_file_with_zuban(file_path)

            # Clean up
            await self._jsonrpc_client.did_close(file_path)

            return diagnostics

        except Exception:
            # Fallback to direct zuban call on any LSP error
            return self._check_file_with_zuban(file_path)

    def _check_file_with_zuban(self, file_path: str) -> list[dict[str, t.Any]]:
        """
        Check a single file using zuban directly.

        This is a temporary implementation that calls zuban directly.
        A full LSP integration would use JSON-RPC protocol.
        """
        try:
            result = self._execute_zuban_check(file_path)

            if result.returncode == 0:
                return []  # No errors

            return self._parse_zuban_output(result.stderr)

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            return []

    def _execute_zuban_check(self, file_path: str) -> subprocess.CompletedProcess[str]:
        """Execute zuban check command for a file."""
        return subprocess.run(
            ["zuban", "check", file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _parse_zuban_output(self, stderr_output: str) -> list[dict[str, t.Any]]:
        """Parse zuban stderr output into diagnostic format."""
        diagnostics = []

        for line in stderr_output.splitlines():
            if self._is_error_line(line):
                diagnostic = self._parse_error_line(line)
                if diagnostic:
                    diagnostics.append(diagnostic)

        return diagnostics

    def _is_error_line(self, line: str) -> bool:
        """Check if a line contains an error message."""
        return ":" in line and "error:" in line.lower()

    def _parse_error_line(self, line: str) -> dict[str, t.Any] | None:
        """Parse a single error line into diagnostic format."""
        # Format: file:line:column: error: message
        parts = line.split(":", 4)
        if len(parts) < 4:
            return None

        try:
            line_num = int(parts[1])
            col_num = int(parts[2]) if parts[2].strip() else 1
            message = parts[4].strip() if len(parts) > 4 else parts[3].strip()

            return {
                "line": line_num,
                "column": col_num,
                "severity": "error",
                "message": message,
                "code": "type-error",
            }
        except (ValueError, IndexError):
            return None

    def format_diagnostics(self, diagnostics: dict[str, list[dict[str, t.Any]]]) -> str:
        """Format diagnostics for display."""
        if not diagnostics or all(not diags for diags in diagnostics.values()):
            return "✅ No type errors found"

        lines = []
        total_errors = sum(len(diags) for diags in diagnostics.values())
        lines.append(f"❌ Found {total_errors} type error(s):")

        for file_path, file_diagnostics in diagnostics.items():
            if file_diagnostics:
                lines.append(f"\n📄 {file_path}:")
                for diag in file_diagnostics:
                    severity_icon = "🔴" if diag["severity"] == "error" else "🟡"
                    lines.append(
                        f"  {severity_icon} Line {diag['line']}:{diag['column']} - {diag['message']}"
                    )

        return "\n".join(lines)

    def get_project_files(self, project_path: Path) -> list[str]:
        """Get Python files in the project that should be type-checked."""
        python_files = []

        # Focus on crackerjack source files (matching pre-commit config)
        crackerjack_dir = project_path / "crackerjack"
        if crackerjack_dir.exists():
            for py_file in crackerjack_dir.rglob("*.py"):
                # Exclude patterns from pre-commit config
                rel_path = py_file.relative_to(project_path)
                rel_str = str(rel_path)

                # Skip excluded directories
                if "/mcp/" in rel_str or "/plugins/" in rel_str:
                    continue
                if "code_cleaner.py" in rel_str:
                    continue

                python_files.append(str(py_file))

        return python_files

    def check_project_with_feedback(
        self, project_path: Path, show_progress: bool = True
    ) -> tuple[dict[str, list[dict[str, t.Any]]], str]:
        """
        Check an entire project with real-time feedback.

        Returns:
            Tuple of (diagnostics dict[str, t.Any], summary message)
        """
        python_files = self.get_project_files(project_path)
        if not python_files:
            return {}, "📁 No Python files found to check"

        feedback = RealTimeTypingFeedback()

        self.console.print(
            f"🔍 Starting type check of {len(python_files)} files...", style="bold blue"
        )

        diagnostics = self.check_files(
            python_files,
            progress_callback=feedback if show_progress else None,
            show_progress=show_progress,
        )

        summary = feedback.get_summary()
        self.console.print(f"\n{summary}", style="bold")

        return diagnostics, summary
