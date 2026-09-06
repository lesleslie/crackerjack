"""Universal per-file-ignores injected via ruff's --config='<inline TOML>' flag.

The starter pack silences ecosystem-wide patterns that fire too noisily in admin/demo code to be worth enforcing repo-by-repo. Per-repo rules (intentionally) stay OUT of this module — they're addressed per-repo.

The returned string is an inline TOML value (an inline-table expression)
used as the right-hand side of `lint.extend-per-file-ignores = <value>`.
This preserves consumer auto-discovery (pyproject.toml, ruff.toml) —
verified empirically 2026-09-05: --config=<file.toml> REPLACES auto-discovery,
which would lose consumer per-file-ignores; --config='KEY = VALUE' PRESERVES it.

A copy of the inline TOML is also written to
.crackerjack_cache/scripts_examples_per_file_ignores.toml for users to
inspect; the file is NOT used by the ruff invocation (only the inline string).
"""

from __future__ import annotations

from pathlib import Path

# Pattern-keyed dict; values are lists of ruff rule IDs.
# Use "ALL" to silence every rule for a pattern (e.g., stale .bak files).
UNIVERSAL_PER_FILE_IGNORES: dict[str, list[str]] = {
    "scripts/**/*.py": [
        "EXE001",  # shebang-not-executable (78 fires, 6 repos)
        "BLE001",  # blind-except (56 fires, 7 repos)
        "F541",  # f-string-missing-placeholders (32 fires, 6 repos)
        "C901",  # complex-structure (12 fires, 6 repos)
        "SIM102",  # collapsible-if (11 fires, 6 repos)
        "SIM103",  # needless-bool (7 fires, 6 repos)
        "SIM114",  # if-with-same-arms (8 fires, 7 repos)
        "S110",  # try-except-pass (10 fires, 2 repos)
        "PLW1510",  # subprocess-run-without-check (9 fires, 3 repos)
    ],
    "examples/**/*.py": [
        # Same as scripts/** + 3 examples-specific additions:
        "EXE001",
        "BLE001",
        "F541",
        "C901",
        "SIM102",
        "SIM103",
        "SIM114",
        "S110",
        "PLW1510",
        # Examples-only additions:
        "N999",  # invalid-module-name (underscored demo filenames)
        "RUF100",  # unused-noqa in example files
        "FURB162",  # fromisoformat-replace-z
    ],
    "scripts/_*.py": ["N999"],  # underscore-prefixed one-shot scripts
    "**/*.bak[0-9]": ["ALL"],  # stale backup files (crackerjack has 2)
}

# Optional debug artifact path (deterministic — concurrent runs race-safely
# overwrite with the same content).
_DEBUG_PER_FILE_IGNORES_FILENAME = (
    ".crackerjack_cache/scripts_examples_per_file_ignores.toml"
)


def build_inline_per_file_ignores(repo_root: Path | None = None) -> str:
    """Build the inline TOML value for use with `ruff --config='<value>'`.

    Returns an inline-table TOML expression:
        {"scripts/**/*.py" = [...], "examples/**/*.py" = [...], ...}

    Optionally writes a debug copy to .crackerjack_cache/ if repo_root given.
    Idempotent — re-running produces the same string and overwrites the debug file.
    """
    entries: list[str] = []
    for pattern, rules in UNIVERSAL_PER_FILE_IGNORES.items():
        rule_str = ", ".join(f'"{r}"' for r in rules)
        entries.append(f'"{pattern}" = [{rule_str}]')
    inline = "{" + ", ".join(entries) + "}"

    if repo_root is not None:
        target = repo_root / _DEBUG_PER_FILE_IGNORES_FILENAME
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("[lint]\nextend-per-file-ignores = " + inline + "\n")

    return inline
