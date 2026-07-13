from __future__ import annotations

import ast
import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


MANIFEST_VERSION: int = 1


MANIFEST_FILENAME: str = "manifest.json"


@dataclass(frozen=True)
class ManifestEntry:
    signature: str
    sha256: str
    promoted_at: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class Manifest:
    version: int
    fixers: dict[str, ManifestEntry]

    def get(self, signature: str) -> ManifestEntry | None:
        return self.fixers.get(signature)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "fixers": {sig: entry.to_dict() for sig, entry in self.fixers.items()},
        }


def empty_manifest() -> Manifest:
    return Manifest(version=MANIFEST_VERSION, fixers={})


def load_manifest(manifest_path: Path) -> Manifest:
    if not manifest_path.exists():
        return empty_manifest()
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Could not read auto_fixers manifest at %s: %s — treating as empty",
            manifest_path,
            exc,
        )
        return empty_manifest()

    version = raw.get("version", MANIFEST_VERSION)
    if version != MANIFEST_VERSION:
        logger.warning(
            "auto_fixers manifest version %s does not match expected %s; "
            "treating as empty",
            version,
            MANIFEST_VERSION,
        )
        return empty_manifest()

    fixers_raw = raw.get("fixers", {})
    if not isinstance(fixers_raw, dict):
        return empty_manifest()

    fixers: dict[str, ManifestEntry] = {}
    for signature, entry_raw in fixers_raw.items():
        if not isinstance(entry_raw, dict):
            continue
        try:
            fixers[signature] = ManifestEntry(
                signature=str(entry_raw["signature"]),
                sha256=str(entry_raw["sha256"]),
                promoted_at=str(entry_raw.get("promoted_at", "")),
            )
        except KeyError:
            continue
    return Manifest(version=version, fixers=fixers)


def write_manifest(manifest: Manifest, path: Path, atomic: bool = True) -> None:
    payload = json.dumps(manifest.to_dict(), indent=2, sort_keys=True)
    if not atomic:
        path.write_text(payload, encoding="utf-8")
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_against_manifest(fixer_path: Path, manifest: Manifest) -> tuple[bool, str]:
    signature = fixer_path.stem
    entry = manifest.get(signature)
    if entry is None:
        return False, f"no manifest entry for signature {signature!r}"
    try:
        actual = sha256_of_file(fixer_path)
    except OSError as exc:
        return False, f"could not hash {fixer_path}: {exc}"
    if actual != entry.sha256:
        return (
            False,
            f"hash mismatch for {signature!r}: expected "
            f"{entry.sha256[:12]}..., got {actual[:12]}...",
        )
    return True, "ok"


BANNED_IMPORTS: frozenset[str] = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "shutil",
        "pathlib",
        "glob",
        "tempfile",
        "io",
        "socket",
        "ssl",
        "fcntl",
        "signal",
        "ctypes",
        "multiprocessing",
        "urllib",
        "urllib.request",
        "urllib.parse",
        "http",
        "http.client",
        "asyncio",
        "ftplib",
        "smtplib",
        "telnetlib",
        "popen2",
        "commands",
        "importlib",
        "code",
        "codeop",
        "pickle",
        "marshal",
        "shelve",
        "ctypes",
        "cffi",
    }
)


BANNED_METACLASS_PRIMITIVES: frozenset[str] = frozenset(
    {
        "type",
        "object",
        "super",
        "builtins",
    }
)


ALLOWED_DUNDER_ATTRS: frozenset[str] = frozenset(
    {
        "__name__",
        "__doc__",
        "__file__",
        "__all__",
    }
)


BANNED_BUILTIN_CALLS: frozenset[str] = frozenset(
    {
        "__import__",
        "eval",
        "exec",
        "compile",
        "globals",
        "locals",
        "vars",
        "breakpoint",
        "input",
    }
)


def _extract_import_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module.split(".")[0])
    return names


def _extract_dunder_attr_uses(tree: ast.AST) -> set[str]:
    seen: set[str] = set()
    dunder_access_builtins = {"getattr", "setattr", "delattr", "hasattr"}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr.startswith("__")
            and node.attr.endswith("__")
        ):
            seen.add(node.attr)
        elif isinstance(node, ast.Call):
            func = node.func

            builtin_name: str | None = None
            if isinstance(func, ast.Name) and func.id in dunder_access_builtins:
                builtin_name = func.id
            elif (
                isinstance(func, ast.Attribute) and func.attr in dunder_access_builtins
            ):
                builtin_name = func.attr
            if builtin_name is None:
                continue
            if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
                seen.add(f"<{builtin_name}:non_literal_arg>")
                continue
            value = node.args[1].value
            if (
                isinstance(value, str)
                and value.startswith("__")
                and value.endswith("__")
            ):
                seen.add(value)
    return seen


def _extract_banned_builtin_calls(tree: ast.AST) -> set[str]:
    seen: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in BANNED_BUILTIN_CALLS:
            seen.add(func.id)
        elif isinstance(func, ast.Attribute) and func.attr in BANNED_BUILTIN_CALLS:
            seen.add(func.attr)
        elif not isinstance(func, (ast.Name, ast.Attribute)):
            seen.add("<computed_callable>")
    return seen


def ast_validate_fixer_source(source: str) -> tuple[bool, str]:
    import ast

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return False, f"syntax error: {exc.msg}"

    banned_imports = _extract_import_names(tree) & BANNED_IMPORTS
    if banned_imports:
        return (
            False,
            "banned imports: " + ", ".join(sorted(banned_imports)),
        )

    metaclass_uses = _extract_import_names(tree) & BANNED_METACLASS_PRIMITIVES
    if metaclass_uses:
        return (
            False,
            "banned metaclass primitives: " + ", ".join(sorted(metaclass_uses)),
        )

    dunder_uses = _extract_dunder_attr_uses(tree) - ALLOWED_DUNDER_ATTRS
    if dunder_uses:
        return (
            False,
            "banned dunder attribute access: " + ", ".join(sorted(dunder_uses)),
        )

    banned_builtins = _extract_banned_builtin_calls(tree)
    if banned_builtins:
        return (
            False,
            "banned builtin calls: " + ", ".join(sorted(banned_builtins)),
        )

    return True, "ok"


__all__ = [
    "ALLOWED_DUNDER_ATTRS",
    "BANNED_IMPORTS",
    "BANNED_METACLASS_PRIMITIVES",
    "MANIFEST_FILENAME",
    "MANIFEST_VERSION",
    "Manifest",
    "ManifestEntry",
    "ast_validate_fixer_source",
    "empty_manifest",
    "load_manifest",
    "sha256_of_file",
    "verify_against_manifest",
    "write_manifest",
]
