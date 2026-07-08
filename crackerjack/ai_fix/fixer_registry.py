
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Fixer(Protocol):

    async def analyze_and_fix(self, issue: Any) -> Any: # pragma: no cover - protocol
        ...

    async def execute_fix_plan(self, plan: Any) -> Any: # pragma: no cover - protocol
        ...


class FixerRegistry:

    def __init__(self) -> None:
        self._builtins: dict[str, Fixer] = {}
        self._auto_promoted: dict[str, Fixer] = {}


    def register_builtin(self, issue_type: str, fixer: Fixer) -> None:
        self._builtins[issue_type] = fixer

    def has_mechanical_fixer(self, issue_type: str) -> bool:
        return issue_type in self._builtins

    def get(self, issue_type: str) -> Fixer | None:
        return self._builtins.get(issue_type)

    def iter_builtins(self) -> Iterator[tuple[str, Fixer]]:
        return iter(self._builtins.items())


    def __getitem__(self, issue_type: str) -> Fixer:
        try:
            return self._builtins[issue_type]
        except KeyError:
            raise KeyError(issue_type) from None

    def __setitem__(self, issue_type: str, fixer: Fixer) -> None:
        self.register_builtin(issue_type, fixer)

    def __len__(self) -> int:
        return len(self._builtins)

    def __contains__(self, issue_type: object) -> bool:
        return isinstance(issue_type, str) and self.has_mechanical_fixer(issue_type)

    def __iter__(self) -> Iterator[str]:
        return iter(self._builtins)

    def keys(self) -> Iterator[str]:
        return self._builtins.keys()

    def values(self) -> Iterator[Fixer]:
        return self._builtins.values()

    def items(self) -> Iterator[tuple[str, Fixer]]:
        return self._builtins.items()


    def register_auto_promoted(self, signature: str, fixer: Fixer) -> None:
        self._auto_promoted[signature] = fixer

    def get_signature(self, signature: str) -> Fixer | None:
        return self._auto_promoted.get(signature)

    def list_signatures(self) -> list[str]:
        return list(self._auto_promoted)


    @classmethod
    def from_disk(cls, auto_fixers_dir: Path) -> FixerRegistry:
        import importlib.util
        import logging
        import sys

        from crackerjack.ai_fix.auto_fixers_manifest import (
            ast_validate_fixer_source,
            load_manifest,
            verify_against_manifest,
        )

        log = logging.getLogger(__name__)
        registry = cls()
        if not auto_fixers_dir.exists() or not auto_fixers_dir.is_dir():
            log.debug(
                "auto_fixers_dir %s does not exist; empty registry", auto_fixers_dir
            )
            return registry

        manifest = load_manifest(auto_fixers_dir / "manifest.json")

        for fixer_path in sorted(auto_fixers_dir.glob("*.py")):
            signature = fixer_path.stem


            ok, reason = verify_against_manifest(fixer_path, manifest)
            if not ok:
                log.warning(
                    "Refusing to load auto-promoted fixer %s: %s",
                    fixer_path,
                    reason,
                )
                continue


            try:
                source = fixer_path.read_text(encoding="utf-8")
            except OSError as exc:
                log.warning("Could not read %s: %s", fixer_path, exc)
                continue
            ok, reason = ast_validate_fixer_source(source)
            if not ok:
                log.warning(
                    "Refusing to load auto-promoted fixer %s: %s",
                    fixer_path,
                    reason,
                )
                continue


            module_name = f"_crackerjack_auto_fixer_{signature}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, fixer_path)
                if spec is None or spec.loader is None:
                    log.warning("Could not load spec for %s", fixer_path)
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            except Exception as exc: # noqa: BLE001
                log.warning(
                    "Failed to import auto-promoted fixer %s: %s",
                    fixer_path,
                    exc,
                )
                continue
            registry.register_auto_promoted(signature, module)
            log.debug(
                "Loaded auto-promoted fixer for %s from %s", signature, fixer_path
            )
        return registry


__all__ = [
    "Fixer",
    "FixerRegistry",
]
