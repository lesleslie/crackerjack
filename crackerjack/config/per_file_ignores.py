"""Universal per-file-ignores injected via ruff's --config=<file.toml> flag.

The starter pack silences ecosystem-wide patterns that fire too noisily
in admin/demo code to be worth enforcing repo-by-repo. Per-repo rules
(intentionally) stay OUT of this module — they're addressed per-repo.

The generated file is a ruff config file with [lint].extend-per-file-ignores
(ADDITIVE — extends the consumer's per-file-ignores rather than replacing).
Consumer repos with their own per-file-ignores (e.g., mahavishnu's
"scripts/**/*.py = [B007, B008, ...]") keep those rules; this file adds on top.

The file MUST end in .toml — ruff's --config flag rejects other extensions.
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

# Cached file path (deterministic — concurrent runs race-safely overwrite).
# MUST end in .toml — ruff's --config flag rejects other extensions.
_PER_FILE_IGNORES_FILENAME = ".crackerjack_cache/scripts_examples_per_file_ignores.toml"


def ensure_per_file_ignores_file(repo_root: Path) -> Path:
    """Write the starter pack TOML to .crackerjack_cache/ if not present.

    Returns the file path for use with `ruff --config=<path>`.
    Idempotent — re-running is a no-op if file exists.
    """
    target = repo_root / _PER_FILE_IGNORES_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        lines: list[str] = ["[lint.extend-per-file-ignores]"]
        for pattern, rules in UNIVERSAL_PER_FILE_IGNORES.items():
            rule_str = ", ".join(f'"{r}"' for r in rules)
            lines.append(f'"{pattern}" = [{rule_str}]')
        target.write_text("\n".join(lines) + "\n")
    return target
