"""Web hooks: stylelint, eslint, tsc, html-validate.

Phase 4 ships CLI-only hooks with JSON output parsing. When the CLI is missing,
`WebHookError` is raised with installation instructions — Swift/Kotlin precedent
(no Python fallbacks). This keeps the false-positive surface small (Python
fallbacks for brace counting etc. are naive and false-positive on real files).

Per Phase 4 spec amendments:
- `web.eslint_tsc` was split into `web.eslint` + `web.tsc` (independent
  pass/fail, independent timeouts).
- `_resolve(project_root, tool)` is the single resolver; replaces the
  inverted `cli_name != "npx"` guard.
- Modern `npx --no` spelling replaces the legacy `--no-install` alias.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path

from crackerjack.adapters.base import Hook

logger = logging.getLogger(__name__)

HookIssue = tuple[Path, int, str]


class WebHookError(RuntimeError):
    """Raised when a Web hook cannot run (CLI missing)."""


def _resolve(project_root: Path, tool: str) -> tuple[str, ...] | None:
    """Resolve how to invoke `tool` for `project_root`.

    Order: `node_modules/.bin/<tool>` → `node_modules/.bin/<tool>/<tool>`
    (pnpm/yarn wrapped-bin layout) → `PATH` → `npx --no <tool>` → `None`.
    Returns the argv tuple, or `None` if the tool is unresolvable.
    """
    nm_bin = project_root / "node_modules" / ".bin" / tool
    if nm_bin.is_file():
        return (str(nm_bin),)
    wrapped = nm_bin / tool
    if wrapped.is_file():
        return (str(wrapped),)
    on_path = shutil.which(tool)
    if on_path is not None:
        return (on_path,)
    if shutil.which("npx") is not None:
        return ("npx", "--no", tool)
    return None


def _build_hook(
    name: str,
    project_root: Path,
    tool: str,
    *extra_args: str,
    timeout_seconds: int = 300,
) -> Hook:
    """Resolve `tool` and build a `Hook`. Raise `WebHookError` if unresolvable."""
    cmd = _resolve(project_root, tool)
    if cmd is None:
        raise WebHookError(
            f"Cannot resolve {tool!r} for project {project_root}. "
            f"Install Node.js (https://nodejs.org) and run "
            f"`npm install --save-dev {tool}`."
        )
    argv = (*cmd, *extra_args, str(project_root))
    return Hook(name=name, cli_command=argv, fallback=None, timeout_seconds=timeout_seconds)


def web_hooks(project_root: Path) -> tuple[Hook, ...]:
    """Build the four Web hooks for `project_root`."""
    return (
        _build_hook("web.stylelint", project_root, "stylelint", "**/*.css"),
        _build_hook("web.eslint", project_root, "eslint", ".", "--ext", ".ts,.tsx,.js,.jsx"),
        _build_hook("web.tsc", project_root, "tsc", "--noEmit", timeout_seconds=600),
        _build_hook("web.html_validate", project_root, "html-validate", "**/*.html"),
    )


# --- JSON / line-oriented output parsers ---


def _parse_stylelint_json(stdout: str, project_root: Path) -> list[HookIssue]:
    """Parse `stylelint -f json` output into `HookIssue` triples."""
    try:
        payload = json.loads(stdout) if stdout.strip() else []
    except json.JSONDecodeError:
        return []
    issues: list[HookIssue] = []
    for entry in payload:
        path = Path(entry.get("source", str(project_root)))
        for warning in entry.get("warnings", []):
            issues.append((path, int(warning.get("line", 0)), str(warning.get("text", ""))))
    return issues


def _parse_eslint_json(stdout: str, project_root: Path) -> list[HookIssue]:
    """Parse `eslint -f json` output into `HookIssue` triples."""
    try:
        payload = json.loads(stdout) if stdout.strip() else []
    except json.JSONDecodeError:
        return []
    issues: list[HookIssue] = []
    for entry in payload:
        path = Path(entry.get("filePath", str(project_root)))
        for msg in entry.get("messages", []):
            issues.append((path, int(msg.get("line", 0)), str(msg.get("message", ""))))
    return issues


def _parse_html_validate_json(stdout: str, project_root: Path) -> list[HookIssue]:
    """Parse `html-validate -f json` output into `HookIssue` triples."""
    try:
        payload = json.loads(stdout) if stdout.strip() else []
    except json.JSONDecodeError:
        return []
    issues: list[HookIssue] = []
    for entry in payload:
        path = Path(entry.get("filePath", str(project_root)))
        for msg in entry.get("messages", []):
            issues.append((path, int(msg.get("line", 0)), str(msg.get("message", ""))))
    return issues


_TSC_LINE = re.compile(r"^(?P<path>[^()]+)\((?P<line>\d+),(?P<col>\d+)\):\s+(?P<severity>error|warning)\s+(?P<code>TS\d+):\s+(?P<msg>.+)$")


def _parse_tsc_output(stdout: str, project_root: Path) -> list[HookIssue]:
    """Parse `tsc --noEmit` line-oriented output into `HookIssue` triples."""
    issues: list[HookIssue] = []
    for line in stdout.splitlines():
        m = _TSC_LINE.match(line.strip())
        if m:
            path = Path(m.group("path"))
            issues.append((path, int(m.group("line")), f"{m.group('code')}: {m.group('msg')}"))
    return issues


__all__ = [
    "HookIssue",
    "WebHookError",
    "_parse_eslint_json",
    "_parse_html_validate_json",
    "_parse_stylelint_json",
    "_parse_tsc_output",
    "_resolve",
    "web_hooks",
]
