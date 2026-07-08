"""Dynamic registry of mechanical fixers — built-in plus auto-promoted.

PR 5 of the 2026-07-07 ai-fix design. Replaces the
``FixerCoordinator.fixers: dict[str, Agent]`` shape with two cooperating
namespaces:

- **built-in fixers** — registered at startup, keyed by issue type
  (``"TYPE_ERROR"``, ``"COMPLEXITY"`` …). Equivalent to today's static
  registration in :class:`FixerCoordinator.__init__`.
- **auto-promoted fixers** — registered at runtime after a successful
  skill has been replayed enough times, keyed by an opaque signature
  string. The signature is the same one PR 8 (``PromotionPipeline``)
  emits when it LLM-generates a mechanical fixer from a skill.

The :meth:`from_disk` classmethod is a stub in this PR — the real loader
that walks an ``auto_fixers/`` directory ships in PR 8. Returning an empty
registry here keeps the contract stable for PR 6 (FixRouter) and PR 7
(SkillStore wiring), neither of which needs the loaded contents to compile
or to exercise their own paths.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Fixer(Protocol):
    """Structural protocol for anything callable as a mechanical fixer.

    The existing agents expose either :meth:`analyze_and_fix` or
    :meth:`execute_fix_plan`; the future auto-promoted fixers expose
    :meth:`execute` (per :mod:`crackerjack.ai_fix.tightened_dispatcher`).
    Declaring a single attribute is impossible without a Union, so the
    type alias is intentionally permissive — callers should perform
    ``hasattr`` dispatch as :class:`FixerCoordinator` already does.
    """

    async def analyze_and_fix(self, issue: Any) -> Any:  # pragma: no cover - protocol
        ...

    async def execute_fix_plan(self, plan: Any) -> Any:  # pragma: no cover - protocol
        ...


class FixerRegistry:
    """Two-namespace registry for mechanical fixers.

    The two namespaces are deliberately separate:

    - :meth:`get` / :meth:`has_mechanical_fixer` answer "does this issue
      type have a built-in fixer?" — the question the existing
      ``FixerCoordinator._execute_single_plan`` asks.
    - :meth:`list_signatures` / :meth:`get_signature` expose the
      auto-promoted namespace, which the future :class:`FixRouter` will
      consult when a Tier-1 lookup misses (PR 6 / PR 7 wire this up).

    Keeping the namespaces disjoint means a future PR cannot accidentally
    promote a fixer into the built-in path or vice versa without explicit
    code; promotion is a deliberate decision, never an implicit side
    effect of a dict mutation.
    """

    def __init__(self) -> None:
        self._builtins: dict[str, Fixer] = {}
        self._auto_promoted: dict[str, Fixer] = {}

    # ------------------------------------------------------------------
    # Built-in registration — issue-type keyed.
    # ------------------------------------------------------------------

    def register_builtin(self, issue_type: str, fixer: Fixer) -> None:
        """Register ``fixer`` as the mechanical fixer for ``issue_type``.

        Last write wins. The registry does not validate that ``fixer``
        exposes any particular method — the executor (``FixerCoordinator``
        today, :class:`FixRouter` in PR 6) is responsible for dispatching
        on ``execute_fix_plan`` / ``analyze_and_fix`` / ``execute`` as
        appropriate.
        """
        self._builtins[issue_type] = fixer

    def has_mechanical_fixer(self, issue_type: str) -> bool:
        """Whether a built-in fixer is registered for ``issue_type``."""
        return issue_type in self._builtins

    def get(self, issue_type: str) -> Fixer | None:
        """Return the built-in fixer for ``issue_type`` or ``None``."""
        return self._builtins.get(issue_type)

    def iter_builtins(self) -> Iterator[tuple[str, Fixer]]:
        """Yield ``(issue_type, fixer)`` for every built-in entry.

        Mirrors ``dict.items()`` so call sites that previously did
        ``for issue_type, fixer in self.fixers.items()`` can swap to
        :meth:`iter_builtins` without restructuring.
        """
        return iter(self._builtins.items())

    # ------------------------------------------------------------------
    # Dict-like shim — lets the registry *be* a drop-in for the old
    # ``FixerCoordinator.fixers: dict[str, Agent]`` field. All dict
    # operations below address the built-in namespace only; auto-promoted
    # fixers remain reachable only via the explicit methods. This keeps
    # the two namespaces strictly disjoint from the caller's perspective.
    # ------------------------------------------------------------------

    def __getitem__(self, issue_type: str) -> Fixer:
        """Subscript lookup into the built-in namespace. Raises ``KeyError``
        when ``issue_type`` is not registered, matching ``dict.__getitem__``.
        """
        try:
            return self._builtins[issue_type]
        except KeyError:
            raise KeyError(issue_type) from None

    def __setitem__(self, issue_type: str, fixer: Fixer) -> None:
        """Subscript assignment maps to :meth:`register_builtin` so the
        existing ``self.fixers[issue_type] = agent`` call sites keep
        working unchanged.
        """
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

    # ------------------------------------------------------------------
    # Auto-promoted registration — signature keyed.
    # ------------------------------------------------------------------

    def register_auto_promoted(self, signature: str, fixer: Fixer) -> None:
        """Register ``fixer`` under the auto-promoted signature.

        Signatures are opaque — the only contract is that two fixers
        generated from the same skill share a signature, so
        re-registration overwrites cleanly. :class:`PromotionPipeline`
        (PR 8) is the canonical caller.
        """
        self._auto_promoted[signature] = fixer

    def get_signature(self, signature: str) -> Fixer | None:
        """Return the auto-promoted fixer for ``signature`` or ``None``."""
        return self._auto_promoted.get(signature)

    def list_signatures(self) -> list[str]:
        """Return all auto-promoted signatures, in insertion order."""
        return list(self._auto_promoted)

    # ------------------------------------------------------------------
    # Disk reconstruction — stub for PR 5.
    # ------------------------------------------------------------------

    @classmethod
    def from_disk(cls, auto_fixers_dir: Path) -> FixerRegistry:
        """Construct a registry pre-populated with auto-promoted fixers.

        PR 5 stub: returns an empty :class:`FixerRegistry` regardless of
        what is on disk. The real loader — which walks
        ``auto_fixers/{signature}.py``, validates the file, and calls
        :meth:`register_auto_promoted` — ships in PR 8 alongside
        :class:`PromotionPipeline`.

        Accepting (and silently ignoring) ``auto_fixers_dir`` here keeps
        the call sites identical across PRs and means test code does not
        have to special-case "registry built in PR 5" vs "registry built
        in PR 8".
        """
        return cls()


__all__ = [
    "Fixer",
    "FixerRegistry",
]
