from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import typing as t
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
    ".crackerjack",
    "uv",
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
    except OSError, UnicodeDecodeError:
        return []
    blocks: list[MermaidBlock] = []
    for match in MERMAID_FENCE_RE.finditer(text):
        start = match.start()
        # Line numbers are 1-indexed for human display.
        line = text.count("\n", 0, start) + 1
        blocks.append(MermaidBlock(file=path, line=line, code=match.group(1)))
    return blocks


# Allow-listed prefixes for the mermaid-cli install. The validator trusts
# only paths that resolve under one of these. This prevents an attacker
# from planting a directory tree on PATH and having it picked up by a
# parent-walk — the walker must still land in a trusted prefix.
DEFAULT_MERMAID_PREFIXES: tuple[str, ...] = (
    "/usr/local/Cellar/mermaid-cli/",
    "/opt/homebrew/Cellar/mermaid-cli/",
    "/usr/local/lib/node_modules/",
    "/opt/homebrew/lib/node_modules/",
)

# Allow-list for the jsdom install. Like mermaid, jsdom is dynamically
# imported and executed as code. We trust only the locally-vendored
# `node_modules/jsdom/` installed in the crackerjack repo by `npm install`
# (which pins the version in package.json). The path is `<repo>/node_modules/`.
DEFAULT_JSDOM_LOCATIONS: tuple[str, ...] = ("node_modules/jsdom/lib/api.js",)


def _locate_mermaid_core() -> Path | None:
    """Return the absolute path to `mermaid/dist/mermaid.core.mjs`, if reachable.

    Resolution order (fail-closed; returns None if no trusted path):

    1. ``CRACKERJACK_MERMAID_CORE`` env var (operator-pinned). Must pass
       the allow-list check.
    2. ``mmdc`` symlink resolution, validated against the allow-list.

    The Node.js runner takes the resolved path as argv[2] and uses dynamic
    ``import()`` to load it (Node ESM does NOT honor NODE_PATH for static
    imports in v18+). The path is then executed as code, so it must
    resolve to a verified, allow-listed install.
    """
    # 1. Explicit env var override (preferred for CI / production).
    env_override = os.environ.get("CRACKERJACK_MERMAID_CORE")
    if env_override:
        path = Path(env_override).resolve()
        if _is_trusted_mermaid_path(path):
            return path
        raise RuntimeError(
            f"CRACKERJACK_MERMAID_CORE={env_override} is not under a "
            f"trusted mermaid-cli prefix; refusing to import. Allowed "
            f"prefixes: {DEFAULT_MERMAID_PREFIXES}"
        )

    # 2. Walk from `mmdc` on PATH, but only return matches inside the
    # allow-list. This prevents an attacker who plants a directory on
    # PATH from having the walker resolve to a malicious install.
    bin_path = shutil.which("mmdc")
    if not bin_path:
        return None
    real = Path(bin_path).resolve()
    if not _is_trusted_mermaid_path(real):
        return None
    for candidate in real.parents:
        nm = candidate / "node_modules"
        if not (nm.is_dir() and (nm / "@mermaid-js" / "mermaid-cli").is_dir()):
            continue
        core = (
            nm
            / "@mermaid-js"
            / "mermaid-cli"
            / "node_modules"
            / "mermaid"
            / "dist"
            / "mermaid.core.mjs"
        )
        if core.is_file() and _is_trusted_mermaid_path(core):
            return core
    return None


def _locate_jsdom() -> Path | None:
    """Return the absolute path to the locally-installed jsdom package.

    Looks for the `node_modules/jsdom/` directory under the crackerjack
    repo root (where the wave-9 dev dep is installed). The result is
    the package's main entry point, `jsdom/lib/api.js`, which exposes
    the `JSDOM` class.

    Override via ``CRACKERJACK_JSDOM`` env var for CI where the
    crackerjack repo lives at a different path.
    """
    env_override = os.environ.get("CRACKERJACK_JSDOM")
    if env_override:
        path = Path(env_override).resolve()
        if path.is_file():
            return path
        raise RuntimeError(
            f"CRACKERJACK_JSDOM={env_override} does not exist or is not a file"
        )

    # Walk up from this file to find the crackerjack repo root.
    repo_root = Path(__file__).resolve()
    while repo_root != repo_root.parent:
        candidate = repo_root / "node_modules" / "jsdom" / "lib" / "api.js"
        if candidate.is_file():
            return candidate
        repo_root = repo_root.parent
    return None


def _is_trusted_mermaid_path(path: Path) -> bool:
    """Allow-list check: `path` must live under a known-good mermaid prefix."""
    resolved = str(path.resolve())
    return any(resolved.startswith(prefix) for prefix in DEFAULT_MERMAID_PREFIXES)


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

    runner = _resolve_runner_path()
    mermaid_core = _locate_mermaid_core()
    jsdom = _locate_jsdom()
    payload = json.dumps(
        [{"file": str(b.file), "line": b.line, "code": b.code} for b in blocks]
    )
    stdout = _run_validator_subprocess(
        runner, mermaid_core, jsdom, payload, len(blocks), timeout
    )
    results = _decode_validator_output(stdout)
    return _collect_errors(results)


def _resolve_runner_path() -> Path:
    """Locate the Node.js validator script or raise FileNotFoundError."""
    runner = Path(__file__).parent.parent / "bin" / "validate-mermaid.mjs"
    if not runner.exists():
        raise FileNotFoundError(f"validate-mermaid.mjs not found at {runner}")
    return runner


def _run_validator_subprocess(
    runner: Path,
    mermaid_core: Path | None,
    jsdom: Path | None,
    payload: str,
    block_count: int,
    timeout: float,
) -> str:
    """Execute the Node.js validator and return its stdout on success."""
    if not mermaid_core:
        raise RuntimeError(
            "could not find mermaid/dist/mermaid.core.mjs; install "
            "@mermaid-js/mermaid-cli (e.g. `brew install mermaid-cli`) "
            "or set a path that exposes mmdc on PATH"
        )
    if not jsdom:
        raise RuntimeError(
            "could not find jsdom at node_modules/jsdom/lib/api.js; "
            "run `npm install` in the crackerjack repo to install the "
            "wave-9 dev dep, or set CRACKERJACK_JSDOM to its absolute path"
        )
    try:
        completed = subprocess.run(
            ["node", str(runner), str(mermaid_core), str(jsdom)],
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
            f"validate-mermaid.mjs timed out after {timeout}s on {block_count} blocks"
        ) from e
    if completed.returncode != 0:
        raise RuntimeError(
            f"validate-mermaid.mjs exited {completed.returncode}: "
            f"{completed.stderr.strip()[:500]}"
        )
    return completed.stdout


def _decode_validator_output(stdout: str) -> list[dict[str, object]]:
    """Parse the validator's JSON output into a list of result dicts."""
    try:
        decoded = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"validate-mermaid.mjs returned invalid JSON: {e}; stdout={stdout[:200]!r}"
        ) from e
    return decoded if isinstance(decoded, list) else []


def _collect_errors(results: list[dict[str, object]]) -> list[MermaidValidationError]:
    """Filter the validator results to entries that failed to parse."""
    return [
        MermaidValidationError(
            file=Path(t.cast("str", entry["file"])),
            line=t.cast("int", entry["line"]),
            error=t.cast("str", entry.get("error", "<unknown error>")),
        )
        for entry in results
        if entry.get("status") == "error"
    ]


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
