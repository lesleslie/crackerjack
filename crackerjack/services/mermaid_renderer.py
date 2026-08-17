from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

console = Console()

# Match a fenced ```mermaid block. Captures the body.
MERMAID_FENCE_RE = re.compile(
    r"^```mermaid\b[^\n]*\n(.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True)
class MermaidBlock:
    """A fenced mermaid block found in a `.md` file."""

    file: Path
    line: int
    code: str


@dataclass(frozen=True)
class MermaidValidationError:
    """A mermaid block that failed to parse."""

    file: Path
    line: int
    error: str

    @property
    def relpath(self) -> str:
        try:
            return str(self.file.resolve().relative_to(Path.cwd().resolve()))
        except ValueError:
            return str(self.file)


# Paths we skip when scanning. The .venv/.git/etc. defaults are honored by
# `iter_markdown_files`; the docs extras are about ignoring generated /
# vendored material that doesn't ship with the project.
DEFAULT_SKIP_DIRS = (
    ".venv",
    "venv",
    "env",
    ".git",
    "node_modules",
    "dist",
    "build",
    ".egg-info",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".worktrees",
    ".claude",
)


def iter_markdown_files(
    root: Path,
    skip_dirs: tuple[str, ...] = DEFAULT_SKIP_DIRS,
) -> list[Path]:
    """Return all `.md` files under `root`, skipping default noisiness."""
    root = root.resolve()
    out: list[Path] = []
    for path in root.rglob("*.md"):
        if any(part in skip_dirs for part in path.parts):
            continue
        out.append(path)
    return out


def extract_mermaid_blocks(path: Path) -> list[MermaidBlock]:
    """Parse a `.md` file and return every fenced ```mermaid block."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    blocks: list[MermaidBlock] = []
    for match in MERMAID_FENCE_RE.finditer(text):
        start = match.start()
        # Line numbers are 1-indexed for human display.
        line = text.count("\n", 0, start) + 1
        blocks.append(MermaidBlock(file=path, line=line, code=match.group(1)))
    return blocks


def _locate_mermaid_core() -> Path | None:
    """Return the absolute path to `mermaid/dist/mermaid.core.mjs`, if reachable.

    Resolves the `mmdc` symlink to find the homebrew / npm prefix. The Node.js
    runner takes this path as argv[2] and uses dynamic `import()` to load it
    (Node ESM does NOT honor NODE_PATH for static imports in v18+).
    """
    bin_path = shutil.which("mmdc")
    if not bin_path:
        return None
    real = Path(bin_path).resolve()
    # Homebrew layout: /usr/local/Cellar/mermaid-cli/<v>/libexec/lib/node_modules
    # Walk up to find the parent that contains node_modules/@mermaid-js/mermaid-cli.
    for candidate in real.parents:
        nm = candidate / "node_modules"
        if nm.is_dir() and (nm / "@mermaid-js" / "mermaid-cli").is_dir():
            core = (
                nm
                / "@mermaid-js"
                / "mermaid-cli"
                / "node_modules"
                / "mermaid"
                / "dist"
                / "mermaid.core.mjs"
            )
            if core.is_file():
                return core
    return None


def validate_mermaid_blocks(
    blocks: list[MermaidBlock],
    timeout: float = 30.0,
) -> list[MermaidValidationError]:
    """Run mermaid.parse() on each block via Node.js subprocess.

    Returns a list of MermaidValidationError. Empty list means every block
    passed. The Node.js runner is `crackerjack/bin/validate-mermaid.mjs`,
    which uses `mermaid.parse()` (lexer-only, no chrome needed).
    """
    if not blocks:
        return []

    runner = Path(__file__).parent.parent / "bin" / "validate-mermaid.mjs"
    if not runner.exists():
        raise FileNotFoundError(f"validate-mermaid.mjs not found at {runner}")

    mermaid_core = _locate_mermaid_core()
    if not mermaid_core:
        raise RuntimeError(
            "could not find mermaid/dist/mermaid.core.mjs; install "
            "@mermaid-js/mermaid-cli (e.g. `brew install mermaid-cli`) "
            "or set a path that exposes mmdc on PATH"
        )

    payload = json.dumps(
        [
            {"file": str(b.file), "line": b.line, "code": b.code}
            for b in blocks
        ]
    )

    try:
        completed = subprocess.run(
            ["node", str(runner), str(mermaid_core)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "node is not on PATH; install Node.js to run the mermaid CI guard"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"validate-mermaid.mjs timed out after {timeout}s on {len(blocks)} "
            f"blocks"
        ) from e

    if completed.returncode != 0:
        raise RuntimeError(
            f"validate-mermaid.mjs exited {completed.returncode}: "
            f"{completed.stderr.strip()[:500]}"
        )

    try:
        results = json.loads(completed.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"validate-mermaid.mjs returned invalid JSON: {e}; "
            f"stdout={completed.stdout[:200]!r}"
        ) from e

    errors: list[MermaidValidationError] = []
    for entry in results:
        if entry.get("status") == "error":
            errors.append(
                MermaidValidationError(
                    file=Path(entry["file"]),
                    line=entry["line"],
                    error=entry.get("error", "<unknown error>"),
                )
            )
    return errors


def find_broken_mermaid_blocks(
    root: Path | None = None,
    paths: list[Path] | None = None,
) -> list[MermaidValidationError]:
    """Top-level entry point: scan `.md` files and return parse failures.

    Pass either `root` (scan recursively) or `paths` (defaults to Path.cwd()).
    """
    if paths is None:
        if root is None:
            root = Path.cwd()
        paths = iter_markdown_files(root)
    all_blocks: list[MermaidBlock] = []
    for path in paths:
        all_blocks.extend(extract_mermaid_blocks(path))
    return validate_mermaid_blocks(all_blocks)


def print_errors(errors: list[MermaidValidationError]) -> None:
    """Pretty-print the broken blocks for `crackerjack docs check-mermaid`."""
    if not errors:
        console.print("[green]✓ All mermaid blocks parse cleanly.[/green]")
        return
    console.print(f"[red]✗ {len(errors)} broken mermaid block(s):[/red]")
    for err in errors:
        console.print(f"  [red]{err.relpath}:{err.line}[/red]  {err.error}")
