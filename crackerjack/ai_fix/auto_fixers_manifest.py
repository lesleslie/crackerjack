"""Manifest for the ``auto_fixers/`` trust boundary.

A directory of ``{signature}.py`` files written by
:class:`~crackerjack.ai_fix.auto_fixer_pr_creator.GhPRCreator` is a
trust boundary: every file there is a candidate for execution by
:class:`~crackerjack.ai_fix.fixer_registry.FixerRegistry.from_disk`
on the next ``crackerjack run``. A malicious PR that lands a
``.py`` in that directory would run on every subsequent invocation.

The manifest is a single source of truth for "this file is
trusted." The contract:

* :class:`ManifestEntry` records the SHA256 of a fixer file at the
  moment it was written. ``GhPRCreator`` updates the manifest
  atomically with the file write.
* :func:`load_manifest` reads it back, with a missing-file path
  (the legacy / first-run state) returning an *empty* manifest —
  not an error, not "trust everything." The safe default is to
  trust nothing that isn't in the manifest.
* :func:`verify_against_manifest` is the gate :meth:`from_disk`
  uses. A file's hash must equal the recorded hash; otherwise the
  file is treated as untrusted and refused.

The manifest is a plain JSON file in the same directory. Its
security model assumes the directory is writable only by
``GhPRCreator`` in our codebase — anyone who can write to the
manifest can also write to the directory, so the manifest is not
a *cryptographic* trust boundary, just a *workflow* one. The
defense-in-depth value is: an attacker who manages to write a
``.py`` file but not the manifest can't get it executed by the
loader.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# Manifest schema version. Bumped if the format changes incompatibly.
MANIFEST_VERSION: int = 1

# Default filename inside the auto_fixers directory.
MANIFEST_FILENAME: str = "manifest.json"


@dataclass(frozen=True)
class ManifestEntry:
    """One row in the auto_fixers manifest."""

    signature: str
    sha256: str
    promoted_at: str  # ISO 8601 timestamp; informational

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class Manifest:
    """The full manifest. A dict-of-entries keyed by signature."""

    version: int
    fixers: dict[str, ManifestEntry]

    def get(self, signature: str) -> ManifestEntry | None:
        return self.fixers.get(signature)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "fixers": {sig: entry.to_dict() for sig, entry in self.fixers.items()},
        }


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def empty_manifest() -> Manifest:
    """The safe default: trust nothing."""
    return Manifest(version=MANIFEST_VERSION, fixers={})


def load_manifest(manifest_path: Path) -> Manifest:
    """Read the manifest from disk.

    A missing file is *not* an error — the caller decides what to
    do (the default policy: refuse to load any fixer). A corrupt
    file is logged and treated as empty (the alternative is to
    hard-fail the whole crackerjack run, which seems worse than
    a noisy warning).
    """
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
    """Write ``manifest`` to ``path``.

    Atomic by default: writes to ``manifest.json.tmp`` and
    renames. Avoids leaving a half-written manifest if the
    process is killed mid-write.
    """
    payload = json.dumps(manifest.to_dict(), indent=2, sort_keys=True)
    if not atomic:
        path.write_text(payload, encoding="utf-8")
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def sha256_of_file(path: Path) -> str:
    """SHA256 hex digest of ``path``. Read in 64 KiB chunks for big fixers."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_against_manifest(fixer_path: Path, manifest: Manifest) -> tuple[bool, str]:
    """Return ``(ok, reason)`` for ``fixer_path`` against the manifest.

    ``ok`` is True iff the file's SHA256 matches the manifest's
    recorded hash for the same signature. A missing manifest entry
    is a *deny* (the file is not in the trust list) — it is *not*
    a "treat as trusted" path.

    The :class:`Manifest` is read-only here; updating the manifest
    is the :class:`GhPRCreator`'s responsibility (the only writer).
    """
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


# ---------------------------------------------------------------------------
# AST-based import blocklist
# ---------------------------------------------------------------------------


# Banned top-level imports in an auto-promoted fixer. These are
# capabilities a fixer should not have: filesystem writes outside
# the project, network access, subprocess spawning, dynamic
# execution, or import-by-name. A fixer is supposed to be a pure
# transformation of source bytes; if it needs any of these, the
# fix is wrong and should be re-derived by the LLM.
BANNED_IMPORTS: frozenset[str] = frozenset(
    {
        # filesystem / process control
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
        # network
        "urllib",
        "urllib.request",
        "urllib.parse",
        "http",
        "http.client",
        "asyncio",
        "ftplib",
        "smtplib",
        "telnetlib",
        # shelling out
        "popen2",
        "commands",
        # dynamic execution
        "importlib",
        "code",
        "codeop",
        "pickle",
        "marshal",
        "shelve",
        # introspection that can be weaponised
        "ctypes",
        "cffi",
    }
)


# Banned attribute access via getattr / setattr on dunder paths.
# We do a coarse static check: any ``getattr(x, "__something__")`` or
# ``x.__something__`` reference is denied unless the attribute is in
# this allowlist. The allowlist is intentionally small.
ALLOWED_DUNDER_ATTRS: frozenset[str] = frozenset(
    {
        "__name__",
        "__doc__",
        "__file__",
        "__all__",
    }
)


# Banned builtin function calls. A fixer is a pure source-byte
# transformation; it has no business calling any of these. Most
# dangerous: ``__import__`` (works around the import blocklist),
# ``eval`` / ``exec`` / ``compile`` (dynamic execution), and the
# introspection builtins that can be weaponised to escape the
# sandbox (``globals`` / ``locals`` / ``vars`` / ``breakpoint``).
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


def _extract_import_names(tree: object) -> set[str]:
    """Collect every imported module name from an AST module.

    Walks ``ast.Import`` (``import os``) and ``ast.ImportFrom``
    (``from os import path``). Returns the set of top-level names.
    """
    import ast

    names: set[str] = set()
    for node in ast.walk(tree):  # type: ignore[arg-type]
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module.split(".")[0])
    return names


def _extract_dunder_attr_uses(tree: object) -> set[str]:
    """Collect every dunder attribute name referenced in the AST.

    Two patterns: ``obj.__foo__`` (an :class:`ast.Attribute` whose
    ``attr`` starts and ends with ``__``) and ``getattr(obj, "__foo__")``
    (a :class:`ast.Call` whose second positional arg is a string
    constant of that shape).
    """
    import ast

    seen: set[str] = set()
    for node in ast.walk(tree):  # type: ignore[arg-type]
        if (
            isinstance(node, ast.Attribute)
            and node.attr.startswith("__")
            and node.attr.endswith("__")
        ):
            seen.add(node.attr)
        elif isinstance(node, ast.Call):
            func = node.func
            is_getattr = (isinstance(func, ast.Name) and func.id == "getattr") or (
                isinstance(func, ast.Attribute) and func.attr == "getattr"
            )
            if (
                is_getattr
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
            ):
                value = node.args[1].value
                if (
                    isinstance(value, str)
                    and value.startswith("__")
                    and value.endswith("__")
                ):
                    seen.add(value)
    return seen


def _extract_banned_builtin_calls(tree: object) -> set[str]:
    """Collect the names of banned builtin function calls in the AST.

    Two patterns: ``__import__(...)`` (an :class:`ast.Call` whose
    ``func`` is an :class:`ast.Name` with a banned id) and
    ``module.__import__(...)`` (an :class:`ast.Call` whose
    ``func`` is an :class:`ast.Attribute` with a banned attr).
    """
    import ast

    seen: set[str] = set()
    for node in ast.walk(tree):  # type: ignore[arg-type]
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in BANNED_BUILTIN_CALLS:
            seen.add(func.id)
        elif isinstance(func, ast.Attribute) and func.attr in BANNED_BUILTIN_CALLS:
            seen.add(func.attr)
    return seen


def ast_validate_fixer_source(source: str) -> tuple[bool, str]:
    """Static-validate an auto-promoted fixer's source.

    Returns ``(ok, reason)``. The validator runs *before* any
    execution; it's a defense-in-depth check against the manifest
    hash.

    Checks (in order, first failure short-circuits):

    1. The source parses.
    2. No banned top-level imports.
    3. No out-of-allowlist dunder attribute access.
    4. No banned builtin function calls (``__import__``, ``eval``,
       ``exec``, etc.) — closes the work-around where a fixer
       uses ``__import__('os')`` instead of ``import os``.
    """
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
