from __future__ import annotations

import ast
from dataclasses import dataclass

from oneiric.core.logging import get_logger

logger = get_logger(__name__)

# First-party repos that indicate code should stay local (cannot be extracted)
_LOCAL_REPO_PREFIXES = ("crackerjack",)

# Imports from oneiric or stdlib-only → code is foundational → Oneiric
_ONEIRIC_PREFIXES = ("oneiric",)

_STDLIB_MODULES: frozenset[str] = frozenset(
    {
        "abc",
        "ast",
        "asyncio",
        "builtins",
        "collections",
        "contextlib",
        "copy",
        "dataclasses",
        "datetime",
        "enum",
        "functools",
        "hashlib",
        "importlib",
        "inspect",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "operator",
        "os",
        "pathlib",
        "re",
        "shutil",
        "signal",
        "socket",
        "subprocess",
        "sys",
        "tempfile",
        "time",
        "traceback",
        "types",
        "typing",
        "uuid",
        "warnings",
        "__future__",
    }
)


@dataclass
class ExtractionProposal:
    target_repo: str  # "oneiric" | "new_package" | "local"
    target_module: str
    proposed_name: str
    rationale: str


class ExtractionTargetClassifier:
    """Classifies clone groups to determine extraction target.

    Rules (in priority order):
    1. Code importing current repo (crackerjack.*) → local (cannot extract)
    2. Code importing only stdlib + oneiric → Oneiric (foundational)
    3. Code importing third-party domain packages → new shared package
    """

    def classify(self, code: str, pattern_description: str) -> ExtractionProposal:
        imports = self._extract_imports(code)
        logger.debug("ExtractionTargetClassifier: imports=%s", imports)

        if self._has_local_repo_imports(imports):
            return ExtractionProposal(
                target_repo="local",
                target_module="",
                proposed_name=self._propose_name(pattern_description),
                rationale="Code imports from the same repo — cannot extract without circular dependency",
            )

        if self._is_foundational(imports):
            return ExtractionProposal(
                target_repo="oneiric",
                target_module="oneiric.utils",
                proposed_name=self._propose_name(pattern_description),
                rationale="Code uses only stdlib and oneiric — foundational, belongs in Oneiric",
            )

        return ExtractionProposal(
            target_repo="new_package",
            target_module="shared",
            proposed_name=self._propose_name(pattern_description),
            rationale=f"Code uses domain packages ({', '.join(imports - _STDLIB_MODULES)}) — extract to a new shared package",
        )

    def _extract_imports(self, code: str) -> set[str]:
        """Return set of top-level module names imported in code."""
        imports: set[str] = set()
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return imports

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

        return imports

    def _has_local_repo_imports(self, imports: set[str]) -> bool:
        return any(imp in _LOCAL_REPO_PREFIXES for imp in imports)

    def _is_foundational(self, imports: set[str]) -> bool:
        non_stdlib = imports - _STDLIB_MODULES
        return all(imp in _ONEIRIC_PREFIXES for imp in non_stdlib)

    @staticmethod
    def _propose_name(pattern_description: str) -> str:
        words = pattern_description.strip().lower().split()
        clean = [w for w in words if w.isalpha()][:4]
        return "_".join(clean) if clean else "extracted_helper"
