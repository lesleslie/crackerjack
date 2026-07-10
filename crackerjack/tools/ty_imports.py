from __future__ import annotations

import importlib
import importlib.util
import logging
import re
import sys
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


AUTO_FIX_CODES: frozenset[str] = frozenset({"unresolved-reference"})


_LINE_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+"
    r"error\[unresolved-reference\]\s+"
    r"Name `(?P<symbol>[^`]+)`\s+used when not defined\s*$"
)


@dataclass(frozen=True)
class FixSite:
    file: Path
    line: int
    col: int
    symbol: str


@dataclass(frozen=True)
class ImportFix:
    symbol: str
    module: str
    import_line: str


def parse_ty_unresolved_reference(line: str) -> FixSite | None:
    match = _LINE_RE.match(line.strip())
    if not match:
        return None
    return FixSite(
        file=Path(match["file"]),
        line=int(match["line"]),
        col=int(match["col"]),
        symbol=match["symbol"],
    )


_STDLIB_NAMES: frozenset[str] | None = None


def _stdlib_names() -> frozenset[str]:
    global _STDLIB_NAMES
    if _STDLIB_NAMES is None:
        names: set[str] = set()

        with suppress(AttributeError):
            names.update(getattr(sys, "stdlib_module_names", frozenset()))

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


_SUBNAME_TO_MODULE: dict[str, str] = {}
_BAD_MODULES: set[str] = set()


def _resolve_subname(symbol: str) -> str | None:
    if symbol in _SUBNAME_TO_MODULE:
        return _SUBNAME_TO_MODULE[symbol]

    for module_name in sorted(_stdlib_names()):
        if module_name.startswith("_") or module_name in _BAD_MODULES:
            continue
        if module_name == "builtins":
            continue
        try:
            module = importlib.import_module(module_name)
        except Exception:
            _BAD_MODULES.add(module_name)
            continue

        if hasattr(module, symbol):
            attr = getattr(module, symbol)

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
                _SUBNAME_TO_MODULE[symbol] = module_name
                return module_name

    return None


def resolve_symbol(symbol: str) -> ImportFix | None:
    if not symbol or not symbol.replace("_", "").isalnum():
        return None
    if symbol.startswith("_"):
        return None

    stdlib = _stdlib_names()

    if symbol in stdlib:
        return ImportFix(symbol=symbol, module=symbol, import_line=f"import {symbol}")

    if (module := _resolve_subname(symbol)) is not None:
        return ImportFix(
            symbol=symbol,
            module=module,
            import_line=f"from {module} import {symbol}",
        )

    if importlib.util.find_spec(symbol) is not None and "." not in symbol:
        return ImportFix(symbol=symbol, module=symbol, import_line=f"import {symbol}")

    return None


_IMPORT_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<body>.*)$")


def _is_import_line(line: str) -> bool:
    stripped = line.lstrip()
    return (
        stripped.startswith("import ")
        or stripped.startswith("from ")
        or stripped.startswith("from __future__ import ")
    )


def _existing_import_match(import_line: str, body: str) -> bool:
    target = import_line.strip()
    return body.strip() == target


def apply_import_fix(
    file_path: Path,
    fix: ImportFix,
    *,
    project_root: Path | None = None,
) -> bool:
    if project_root is not None:
        resolved = file_path.resolve(strict=False)
        root_resolved = project_root.resolve(strict=False)
        if not resolved.is_relative_to(root_resolved):
            logger.warning(
                "Refusing to write %s outside project root %s",
                resolved,
                root_resolved,
            )
            return False
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

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
            body_match = _IMPORT_LINE_RE.match(line)
            if body_match and _existing_import_match(
                fix.import_line, body_match["body"]
            ):
                return False
            last_import_idx = i
            continue

        break

    new_line = fix.import_line
    if last_import_idx == -1:
        insert_at = 0
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("from __future__"):
                insert_at = i + 1
                continue
            break

        prefix = lines[:insert_at]
        suffix = lines[insert_at:]
        new_block = prefix + [new_line, ""]

        if suffix and not suffix[0].strip():
            new_block.extend(suffix[1:])
        else:
            new_block.extend(suffix)
        new_content = "\n".join(new_block)
    else:
        insert_at = last_import_idx + 1
        prefix = lines[:insert_at]
        suffix = lines[insert_at:]

        if suffix and not suffix[0].strip():
            new_content = "\n".join(prefix + [new_line] + suffix)
        else:
            new_content = "\n".join(prefix + ["", new_line] + suffix)

    if new_content == content:
        return False

    file_path.write_text(new_content, encoding="utf-8")
    return True


def fix_unresolved_references(
    file_path: Path,
    sites: list[FixSite],
) -> tuple[int, list[FixSite]]:
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
            pass
    return fixes_applied, unresolved
