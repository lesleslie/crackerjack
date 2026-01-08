#!/usr/bin/env python3

import sys
from pathlib import Path

from rich.console import Console

from crackerjack.services.lsp_client import LSPClient


def main(console: Console | None = None) -> int:
    console = console or Console()

    files_to_check = sys.argv[1:] if len(sys.argv) > 1 else []

    if not files_to_check:
        files_to_check = _get_project_files()

    if not files_to_check:
        console.print("🔍 No Python files to check")
        return 0

    lsp_client = LSPClient()

    if not lsp_client.is_server_running():
        return _fallback_to_zuban_check(console, files_to_check)

    return _check_files_with_lsp(console, lsp_client, files_to_check)


def _get_project_files() -> list[str]:
    project_path = Path.cwd()
    lsp_client = LSPClient()
    return lsp_client.get_project_files(project_path)


def _fallback_to_zuban_check(console: Console, files_to_check: list[str]) -> int:
    console.print("⚠️ Zuban LSP server not running, falling back to direct zuban check")

    import subprocess

    try:
        result = subprocess.run(
            ["zuban", "check"] + files_to_check,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            console.print(result.stderr, style="red")
        return result.returncode
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        console.print(f"❌ Error running zuban: {e}", style="red")
        return 1


def _check_files_with_lsp(
    console: Console, lsp_client: LSPClient, files_to_check: list[str]
) -> int:
    server_info = lsp_client.get_server_info()
    if server_info:
        console.print(f"🔍 Using Zuban LSP server (PID: {server_info['pid']})")

    diagnostics = lsp_client.check_files(files_to_check)

    output = lsp_client.format_diagnostics(diagnostics)
    console.print(output)

    has_errors = any(diags for diags in diagnostics.values())
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
