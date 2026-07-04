from __future__ import annotations

from pathlib import Path

from oneiric.core.logging import get_logger

logger = get_logger(__name__)

_STATIC_INVARIANTS = [
    "No new `Any` type annotations in production code",
    "Coverage must not decrease below current baseline",
    "No modifications to SELFPATCHER_DENY_PATHS files",
    "All async I/O must use httpx/aiofiles, not requests/sync file I/O",
    "Use oneiric logger, not stdlib logging or print()",
    "No assert statements in production code (use errors.py hierarchy)",
    "Line length must not exceed 88 characters",
    "Cyclomatic complexity must not exceed 15",
    "from __future__ import annotations must be the first non-comment line",
    "Imports must be sorted: stdlib → third-party → first-party",
]


def _extract_pyproject_rules() -> list[str]:
    pyproject = Path(__file__).parent.parent.parent / "pyproject.toml"
    rules: list[str] = []
    if not pyproject.exists():
        logger.warning(
            "pyproject.toml not found — constitution will use static rules only"
        )
        return rules
    try:
        content = pyproject.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("line-length"):
                rules.append(f"Ruff: {stripped}")
            elif stripped.startswith("max-complexity"):
                rules.append(f"Ruff: {stripped}")
    except OSError:
        logger.warning("Could not read pyproject.toml for constitution extraction")
    return rules


def load_constitution() -> str:
    pyproject_rules = _extract_pyproject_rules()
    all_rules = pyproject_rules + _STATIC_INVARIANTS
    return "=== Crackerjack Code Generation Constitution ===\n" + "\n".join(
        f"- {rule}" for rule in all_rules
    )
