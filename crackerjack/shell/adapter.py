from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Any

from oneiric.shell import AdminShell, ShellConfig
from rich.console import Console
from rich.table import Table

from crackerjack.shell.session_compat import SessionEventEmitter

logger = logging.getLogger(__name__)


class CrackerjackShell(AdminShell):
    def __init__(self, app: Any, config: ShellConfig | None = None) -> None:
        super().__init__(app, config)
        self._add_crackerjack_namespace()
        self.console = Console()

        self.session_tracker = SessionEventEmitter(component_name="crackerjack")
        self._session_id: str | None = None

        self._project_root = Path.cwd()

    def _add_crackerjack_namespace(self) -> None:
        self.namespace.update(
            {
                "CrackerjackSettings": self._try_import(
                    "crackerjack.config.settings", "CrackerjackSettings"
                ),
                "config": self.app,
                "crack": lambda: asyncio.run(self._run_crack()),
                "test": lambda: asyncio.run(self._run_tests()),
                "lint": lambda: asyncio.run(self._run_lint()),
                "scan": lambda: asyncio.run(self._run_scan()),
                "format_code": lambda: asyncio.run(self._run_format()),
                "typecheck": lambda: asyncio.run(self._run_typecheck()),
                "show_adapters": lambda: asyncio.run(self._show_adapters()),
                "show_hooks": lambda: asyncio.run(self._show_hooks()),
            }
        )

    def _get_component_name(self) -> str:
        return "crackerjack"

    def _get_component_version(self) -> str:
        try:
            import importlib.metadata as importlib_metadata

            return importlib_metadata.version("crackerjack")
        except Exception:
            return "unknown"

    def _get_adapters_info(self) -> list[str]:  # type: ignore
        self._process_general_1()

    def _get_banner(self) -> str:
        version = self._get_component_version()
        adapters = ", ".join(self._get_adapters_info())

        session_status = "Enabled" if self.session_tracker.available else "Unavailable"

        return f"""

    def _get_adapters_info(self) -> list[str]:  # type: ignore

        try:
            if hasattr(self.app, "qa_adapters"):
                return list(self.app.qa_adapters.keys())
        except Exception:
            pass

        return ["pytest", "ruff", "mypy", "bandit"]
Crackerjack Admin Shell v{version}
{"=" * 60}
Quality & Testing Automation for Python Projects

Role: Inspector (validates other components)

Session Tracking: {session_status}
  Shell sessions tracked via Session-Buddy MCP
  Metadata: version, adapters, quality metrics

Available QA Adapters: {adapters}

Convenience Functions:
  crack()         - Run comprehensive quality checks
  test()          - Run test suite with coverage
  lint()          - Run linting (ruff check + format)
  scan()          - Run security scan (bandit)
  format_code()   - Format code with ruff
  typecheck()     - Run type checking (mypy)
  show_adapters() - Show enabled QA adapters
  show_hooks()    - Show configured pre-commit hooks

Available Objects:
  config          - Current CrackerjackSettings instance

Type 'help()' for Python help or %help_shell for shell commands
{"=" * 60}
"""

    async def _run_crack(self) -> None:
        self.console.print(
            "\n[bold cyan]Running comprehensive quality checks...[/bold cyan]\n"
        )

        checks = [
            ("Linting", self._run_lint),
            ("Type Checking", self._run_typecheck),
            ("Security Scan", self._run_scan),
            ("Tests", self._run_tests),
        ]

        results = []
        for name, check_func in checks:
            try:
                self.console.print(f"[yellow]Running {name}...[/yellow]")
                await check_func()
                results.append((name, "✓ PASS", "green"))
                self.console.print()
            except Exception as e:
                results.append((name, f"✗ FAIL: {e}", "red"))
                self.console.print()

        self.console.print("[bold]Quality Check Summary:[/bold]\n")

        table = Table(title="Quality Check Results")
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Details")

        for name, status, style in results:
            table.add_row(name, f"[{style}]{status}[/{style}]")

        self.console.print(table)

        failed = any("FAIL" in status for _, status, _ in results)
        if failed:
            self.console.print("\n[red]✗ Quality checks failed[/red]")
        else:
            self.console.print("\n[green]✓ All quality checks passed[/green]")

    async def _run_tests(self) -> None:
        self.console.print("[cyan]Running test suite...[/cyan]")

        cmd = ["pytest", "-v", "--cov=crackerjack", "--cov-report=term-missing"]

        result = subprocess.run(
            cmd,
            cwd=self._project_root,
            capture_output=True,
            text=True,
        )

        if result.stdout:
            lines = result.stdout.split("\n")
            for line in lines:
                if "passed" in line.lower() and "%" in line:
                    self.console.print(f"[green]{line}[/green]")
                elif "failed" in line.lower():
                    self.console.print(f"[red]{line}[/red]")
                elif "ERROR" in line or "FAILED" in line:
                    self.console.print(f"[red]{line}[/red]")
                else:
                    self.console.print(line)

        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd)

    async def _run_lint(self) -> None:
        self.console.print("[cyan]Running linting...[/cyan]")

        cmd_check = ["ruff", "check", "."]
        result_check = subprocess.run(
            cmd_check,
            cwd=self._project_root,
            capture_output=True,
            text=True,
        )

        if result_check.stdout:
            self.console.print(result_check.stdout)

        cmd_format = ["ruff", "format", "--check", "."]
        result_format = subprocess.run(
            cmd_format,
            cwd=self._project_root,
            capture_output=True,
            text=True,
        )

        if result_format.stdout:
            self.console.print(result_format.stdout)

        if result_check.returncode != 0 or result_format.returncode != 0:
            raise subprocess.CalledProcessError(
                max(result_check.returncode, result_format.returncode), cmd_check
            )

        self.console.print("[green]✓ Linting passed[/green]")

    async def _run_scan(self) -> None:
        self.console.print("[cyan]Running security scan...[/cyan]")

        cmd = ["bandit", "-r", "crackerjack/", "-f", "screen"]

        result = subprocess.run(
            cmd,
            cwd=self._project_root,
            capture_output=True,
            text=True,
        )

        if result.stdout:
            self.console.print(result.stdout)

        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd)

        self.console.print("[green]✓ Security scan passed[/green]")

    async def _run_format(self) -> None:
        self.console.print("[cyan]Formatting code...[/cyan]")

        cmd_format = ["ruff", "format", "."]
        result_format = subprocess.run(
            cmd_format,
            cwd=self._project_root,
            capture_output=True,
            text=True,
        )

        cmd_fix = ["ruff", "check", "--fix", "."]
        result_fix = subprocess.run(
            cmd_fix,
            cwd=self._project_root,
            capture_output=True,
            text=True,
        )

        if result_format.returncode != 0:
            raise subprocess.CalledProcessError(result_format.returncode, cmd_format)

        if result_fix.returncode != 0:
            if result_fix.stdout:
                self.console.print(
                    "[yellow]Some issues could not be auto-fixed:[/yellow]"
                )
                self.console.print(result_fix.stdout)

        self.console.print("[green]✓ Code formatted[/green]")

    async def _run_typecheck(self) -> None:
        self.console.print("[cyan]Running type checking...[/cyan]")

        cmd = ["mypy", "crackerjack/"]

        result = subprocess.run(
            cmd,
            cwd=self._project_root,
            capture_output=True,
            text=True,
        )

        if result.stdout:
            self.console.print(result.stdout)

        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd)

        self.console.print("[green]✓ Type checking passed[/green]")

    async def _show_adapters(self) -> None:
        from crackerjack.config import CrackerjackSettings, load_settings

        load_settings(CrackerjackSettings)
        adapters = self._get_adapters_info()

        table = Table(title="Enabled QA Adapters")
        table.add_column("Adapter", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Description")

        adapter_info = {
            "pytest": ("Active", "Test runner with coverage"),
            "ruff": ("Active", "Linter and formatter"),
            "mypy": ("Active", "Static type checker"),
            "bandit": ("Active", "Security linter"),
        }

        for adapter in adapters:
            status, desc = adapter_info.get(adapter, ("Unknown", "N/A"))
            table.add_row(adapter, status, desc)

        self.console.print(table)

    async def _show_hooks(self) -> None:
        self.console.print("[cyan]Checking pre-commit hooks...[/cyan]")

        import tomli

        pyproject_path = self._project_root / "pyproject.toml"

        if not pyproject_path.exists():
            self.console.print("[yellow]No pyproject.toml found[/yellow]")
            return

        with pyproject_path.open("rb") as f:
            data = tomli.load(f)

        hooks_config = data.get("tool", {}).get("pre-commit", {})

        if not hooks_config:
            self.console.print("[yellow]No pre-commit hooks configured[/yellow]")
            return

        table = Table(title="Pre-commit Hooks")
        table.add_column("Hook", style="cyan")
        table.add_column("Stage", style="yellow")
        table.add_column("Command")

        for hook_name, hook_config in hooks_config.items():
            if isinstance(hook_config, dict):
                stage = hook_config.get("stage", "unknown")
                command = hook_config.get("command", "N/A")
                table.add_row(hook_name, stage, command)

        self.console.print(table)

    async def _emit_session_start(self) -> None:
        try:
            metadata = {
                "version": self._get_component_version(),
                "adapters": self._get_adapters_info(),
                "component_type": "inspector",
                "project_root": str(self._project_root),
            }

            self._session_id = await self.session_tracker.emit_session_start(
                shell_type=self.__class__.__name__,
                metadata=metadata,
            )

            if self._session_id:
                logger.info(f"Crackerjack shell session started: {self._session_id}")
            else:
                logger.debug(
                    "Session tracking unavailable (Session-Buddy MCP not reachable)"
                )
        except Exception as e:
            logger.debug(f"Failed to emit session start: {e}")

    async def _emit_session_end(self) -> None:
        if not self._session_id:
            return

        try:
            await self.session_tracker.emit_session_end(
                session_id=self._session_id,
                metadata={},
            )
            logger.info(f"Crackerjack shell session ended: {self._session_id}")
        except Exception as e:
            logger.debug(f"Failed to emit session end: {e}")
        finally:
            self._session_id = None

    async def close(self) -> None:
        await self._emit_session_end()
        await self.session_tracker.close()
