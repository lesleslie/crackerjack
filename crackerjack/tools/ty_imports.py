"""Mechanical auto-fix for ``ty`` ``unresolved-reference`` import errors.

``crackerjack ai-fix`` runs this alongside ``ty_cleanup``. Where
``ty_cleanup`` removes obsolete ``# type: ignore`` comments and
``cast()`` calls, this module **adds** missing imports.

Scope (deliberately narrow):

* The missing symbol IS the name of a stdlib module (``time``,
  ``os``, ``pathlib``, ...).
* The missing symbol is a public top-level attribute of a stdlib
  module (``Path`` -> ``pathlib``, ``Counter`` -> ``collections``).
* The missing symbol is the name of an installed third-party
  package (``typer``, ``pydantic``, ...).

Out of scope (handed to the LLM tier):

* Symbols defined inside optional-dep modules that aren't installed.
* Symbols whose only path is through a private (underscore-prefixed)
  module attribute.
* Symbols whose resolution requires understanding the project's own
  package layout beyond a flat import line.

The resolver never deletes or rewrites existing code; it only
prepends an import line into the import block. It is idempotent:
re-running on a file that already has the import is a no-op.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
import sys
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Only this ty code is unambiguously "missing import". Other unresolved
# variants (unresolved-attribute on a union, unresolved-import for a
# deleted module) need design decisions, not mechanical edits.
AUTO_FIX_CODES: frozenset[str] = frozenset({"unresolved-reference"})


# Compact regex matching the canonical ty concise output line:
#   path/to/file.py:LINE:COL: error[unresolved-reference] Name `X` used when not defined
_LINE_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+"
    r"error\[unresolved-reference\]\s+"
    r"Name `(?P<symbol>[^`]+)`\s+used when not defined\s*$"
)


@dataclass(frozen=True)
class FixSite:
    """A single unresolved-reference ty diagnostic."""

    file: Path
    line: int
    col: int
    symbol: str


@dataclass(frozen=True)
class ImportFix:
    """A resolved import to apply to a file.

    ``symbol`` is what ty said was missing (e.g. ``"Path"``).
    ``module`` is the source (e.g. ``"pathlib"``).
    ``import_line`` is the exact text to insert (e.g.
    ``"from pathlib import Path"``).
    """

    symbol: str
    module: str
    import_line: str


# ---------------------------------------------------------------------------
# Parsing ty output
# ---------------------------------------------------------------------------


def parse_ty_unresolved_reference(line: str) -> FixSite | None:
    """Parse one concise ty output line. Returns ``None`` for non-matches."""
    match = _LINE_RE.match(line.strip())
    if not match:
        return None
    return FixSite(
        file=Path(match["file"]),
        line=int(match["line"]),
        col=int(match["col"]),
        symbol=match["symbol"],
    )


# ---------------------------------------------------------------------------
# Symbol resolution
# ---------------------------------------------------------------------------

_STDLIB_NAMES: frozenset[str] | None = None


def _stdlib_names() -> frozenset[str]:
    """Names of all standard-library modules (cached)."""
    global _STDLIB_NAMES
    if _STDLIB_NAMES is None:
        names: set[str] = set()
        # Python 3.10+ ships an authoritative list.
        with suppress(AttributeError):
            names.update(getattr(sys, "stdlib_module_names", frozenset()))
        # Defensive fallback for older interpreters / odd environments.
        if not names:
            names.update(
                {
                    "os",
                    "sys",
                    "time",
                    "re",
                    "json",
                    "pathlib",
                    "typing",
                    "collections",
                    "itertools",
                    "functools",
                    "contextlib",
                    "dataclasses",
                    "subprocess",
                    "shutil",
                    "tempfile",
                    "logging",
                    "argparse",
                    "io",
                    "abc",
                    "ast",
                    "copy",
                    "csv",
                    "datetime",
                    "enum",
                    "errno",
                    "fnmatch",
                    "gc",
                    "glob",
                    "hashlib",
                    "heapq",
                    "importlib",
                    "inspect",
                    "ipaddress",
                    "math",
                    "mimetypes",
                    "numbers",
                    "operator",
                    "pickle",
                    "pkgutil",
                    "platform",
                    "pprint",
                    "queue",
                    "random",
                    "secrets",
                    "shelve",
                    "signal",
                    "socket",
                    "sqlite3",
                    "ssl",
                    "stat",
                    "statistics",
                    "string",
                    "struct",
                    "threading",
                    "token",
                    "tokenize",
                    "traceback",
                    "types",
                    "unicodedata",
                    "unittest",
                    "urllib",
                    "uuid",
                    "venv",
                    "warnings",
                    "weakref",
                    "xml",
                    "zipfile",
                    "zlib",
                }
            )
        _STDLIB_NAMES = frozenset(names)
    return _STDLIB_NAMES


# Avoid the import-system's lock state; cache subname lookups separately.
_SUBNAME_TO_MODULE: dict[str, str] = {}
_BAD_MODULES: set[str] = set()


def _resolve_subname(symbol: str) -> str | None:
    """Find a stdlib module that exposes ``symbol`` as a top-level attr.

    Returns the module name (e.g. ``"pathlib"``) or ``None``.
    """
    if symbol in _SUBNAME_TO_MODULE:
        return _SUBNAME_TO_MODULE[symbol]

    for module_name in sorted(_stdlib_names()):
        if module_name.startswith("_") or module_name in _BAD_MODULES:
            continue
        if module_name == "builtins":
            # Anything in `builtins` is already a global; no import needed.
            continue
        try:
            module = importlib.import_module(module_name)
        except Exception:
            # Module is broken on this interpreter; skip silently.
            _BAD_MODULES.add(module_name)
            continue

        if hasattr(module, symbol):
            attr = getattr(module, symbol)
            # Only accept *public* names defined in the module itself
            # (not inherited from somewhere obscure).
            if (
                not symbol.startswith("_")
                and getattr(attr, "__module__", None) == module_name
            ):
                _SUBNAME_TO_MODULE[symbol] = module_name
                return module_name
            if not symbol.startswith("_") and module_name in {
                "pathlib",
                "collections",
                "typing",
            }:
                # Common re-exports where __module__ may differ.
                _SUBNAME_TO_MODULE[symbol] = module_name
                return module_name

    return None


def resolve_symbol(symbol: str) -> ImportFix | None:
    """Return an ``ImportFix`` for ``symbol``, or ``None`` if unresolvable."""
    if not symbol or not symbol.replace("_", "").isalnum():
        return None
    if symbol.startswith("_"):
        return None

    stdlib = _stdlib_names()

    # Tier 1: symbol is a stdlib module itself.
    if symbol in stdlib:
        return ImportFix(symbol=symbol, module=symbol, import_line=f"import {symbol}")

    # Tier 2: symbol is a public stdlib sub-name (Path -> pathlib, etc.)
    if (module := _resolve_subname(symbol)) is not None:
        return ImportFix(
            symbol=symbol,
            module=module,
            import_line=f"from {module} import {symbol}",
        )

    # Tier 3: symbol is an installed third-party package (a top-level
    # importable name).
    if importlib.util.find_spec(symbol) is not None and "." not in symbol:
        # Cheap check: only treat as a candidate if it looks package-like
        # (no dots in the name, no underscore prefix).
        return ImportFix(symbol=symbol, module=symbol, import_line=f"import {symbol}")

    return None


# ---------------------------------------------------------------------------
# Applying the fix
# ---------------------------------------------------------------------------

# Lines we consider "import block" content.
_IMPORT_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<body>.*)$")


def _is_import_line(line: str) -> bool:
    stripped = line.lstrip()
    return (
        stripped.startswith("import ")
        or stripped.startswith("from ")
        or stripped.startswith("from __future__ import ")
    )


def _existing_import_match(import_line: str, body: str) -> bool:
    """True if ``body`` already covers what ``import_line`` would provide."""
    target = import_line.strip()
    return body.strip() == target


def apply_import_fix(file_path: Path, fix: ImportFix) -> bool:
    """Insert ``fix.import_line`` into the file's import block.

    Idempotent: returns ``False`` if the file already has an equivalent
    import line and ``True`` if it wrote a change.

    The insertion policy:
    * Find the contiguous import block at the top of the file
      (skipping blank lines and ``from __future__ import`` directives).
    * Insert the new line directly after the last import in that block.
    * If the file has no imports yet, insert at line 1.
    * Separate the import block from the next code with one blank line.
    """
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Walk the top-of-file import block. We treat any of:
    #   - blank line
    #   - comment (starts with #)
    #   - import statement
    #   - module-level docstring ("""...""" at module scope)
    # as still being in the "header" zone. Once we hit real code, the
    # import block is over.
    last_import_idx = -1
    in_docstring = False
    docstring_quote = ""

    for i, line in enumerate(lines):
        stripped = line.lstrip()

        if in_docstring:
            if docstring_quote in line:
                in_docstring = False
            continue

        if stripped.startswith('"""') or stripped.startswith("'''"):
            # Toggle docstring state. Naive (single-line only) but
            # sufficient for header detection.
            quote = '"""' if stripped.startswith('"""') else "'''"
            if stripped.count(quote) == 1:
                in_docstring = True
                docstring_quote = quote
            continue

        if not stripped:
            continue

        if stripped.startswith("#"):
            continue

        if _is_import_line(line):
            # Check idempotency: if the same import is already present,
            # bail out before we touch the file.
            body_match = _IMPORT_LINE_RE.match(line)
            if body_match and _existing_import_match(
                fix.import_line, body_match["body"]
            ):
                return False
            last_import_idx = i
            continue

        # Real code (def/class/assignment/expression) — stop scanning.
        break

    new_line = fix.import_line
    if last_import_idx == -1:
        # No imports yet — insert at the top, after any module docstring
        # or __future__ directive that exists at lines 0..N.
        insert_at = 0
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("from __future__"):
                insert_at = i + 1
                continue
            break
        # Add a blank line after the new import if the next line is
        # non-empty and not already blank.
        prefix = lines[:insert_at]
        suffix = lines[insert_at:]
        new_block = prefix + [new_line, ""]
        # If the original first line was already blank, don't double it.
        if suffix and not suffix[0].strip():
            new_block.extend(suffix[1:])
        else:
            new_block.extend(suffix)
        new_content = "\n".join(new_block)
    else:
        # Insert right after the last import line in the contiguous block.
        insert_at = last_import_idx + 1
        prefix = lines[:insert_at]
        suffix = lines[insert_at:]
        # Avoid double blank lines.
        if suffix and not suffix[0].strip():
            new_content = "\n".join(prefix + [new_line] + suffix)
        else:
            new_content = "\n".join(prefix + ["", new_line] + suffix)

    if new_content == content:
        return False

    file_path.write_text(new_content, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Top-level driver (analogous to ``ty_cleanup.run_ty``)
# ---------------------------------------------------------------------------


def fix_unresolved_references(
    file_path: Path,
    sites: list[FixSite],
) -> tuple[int, list[FixSite]]:
    """Apply ``apply_import_fix`` for every site whose symbol is resolvable.

    Returns ``(fixes_applied, unresolved_sites)`` — the latter is the
    subset we couldn't fix and that should be handed to the LLM tier.
    """
    fixes_applied = 0
    unresolved: list[FixSite] = []
    for site in sites:
        fix = resolve_symbol(site.symbol)
        if fix is None:
            unresolved.append(site)
            continue
        if apply_import_fix(file_path, fix):
            fixes_applied += 1
        else:
            # Already imported — not unresolved, not a "fix" per se.
            pass
    return fixes_applied, unresolved
