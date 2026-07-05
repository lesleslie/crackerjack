"""Anti-AI-flavor phrase detector.

Spec: docs/superpowers/specs/2026-06-22-anti-ai-flavor-style-sop-design.md
Spec #6 from Phase 2 spec batch.

Detects LLM-tic phrases like "delve into", "tapestry", "leverage", "robust"
in text content. Supports configurable phrase lists, YAML loading, and
context-aware whitelisting.
"""

from __future__ import annotations

import importlib
import re
import typing as t
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# Default LLM-tic phrases from the spec.
DEFAULT_PHRASES: tuple[str, ...] = (
    "delve into",
    "tapestry",
    "leverage",
    "robust",
    "in conclusion",
    "it's important to note",
    "navigate the complexities",
    "in the realm of",
    "dive deep",
    "embark on a journey",
    "game-changer",
    "cutting-edge",
    "state-of-the-art",
    "seamlessly",
    "harness the power of",
    "unleash the potential",
    "unlock the potential",
    "revolutionize",
    "transformative",
    "synergy",
    "holistic",
    "paradigm shift",
    "in today's",
    "in the ever-evolving",
)


@dataclass(frozen=True)
class AntiAIFlavorMatch:
    """A single detected anti-AI-flavor phrase occurrence."""

    phrase: str
    line: int
    column: int

    def to_dict(self) -> dict[str, int | str]:
        return {"phrase": self.phrase, "line": self.line, "column": self.column}


WhitelistEntry = str | Callable[[str, str], bool]


class AntiAIFlavorDetector:
    """Detect LLM-tic phrases in text.

    Args:
        phrases: Sequence of phrases to detect. Defaults to DEFAULT_PHRASES.
        whitelist: Phrases (or callables) to skip. A callable receives
            (phrase, line_text) and returns True to allow the occurrence.
        case_sensitive: If False (default), match case-insensitively.
    """

    def __init__(
        self,
        phrases: Sequence[str] | None = None,
        whitelist: Sequence[WhitelistEntry] | WhitelistEntry | None = None,
        case_sensitive: bool = False,
    ) -> None:
        # `None` means use defaults. An empty sequence means empty (no phrases).
        if phrases is None:
            self.phrases: tuple[str, ...] = DEFAULT_PHRASES
        else:
            self.phrases = tuple(phrases)
        # Whitelist accepts a single entry (string or callable) or a sequence.
        if whitelist is None:
            self.whitelist: tuple[WhitelistEntry, ...] = ()
        elif isinstance(whitelist, str) or callable(whitelist):
            # ty can't narrow ``whitelist`` to ``WhitelistEntry`` through
            # the ``callable(...)`` predicate alone (Sequence and Callable
            # overlap statically), so use ``t.cast`` at the boundary.
            self.whitelist = (t.cast("WhitelistEntry", whitelist),)
        else:
            self.whitelist = tuple(whitelist)
        self.case_sensitive = case_sensitive
        # Pre-compile patterns once.
        flags = 0 if case_sensitive else re.IGNORECASE
        # \b boundaries keep us from matching "robustly" against "robust".
        self._patterns: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
            (phrase, re.compile(rf"\b{re.escape(phrase)}\b", flags))
            for phrase in self.phrases
        )

    def detect(self, text: str) -> list[AntiAIFlavorMatch]:
        """Scan text and return all matches."""
        matches: list[AntiAIFlavorMatch] = []
        for line_num, line_text in enumerate(text.splitlines(), start=1):
            for phrase, pattern in self._patterns:
                for m in pattern.finditer(line_text):
                    if self._is_whitelisted(phrase, line_text):
                        continue
                    matches.append(
                        AntiAIFlavorMatch(
                            phrase=phrase,
                            line=line_num,
                            column=m.start() + 1,
                        )
                    )
        return matches

    def _is_whitelisted(self, phrase: str, line_text: str) -> bool:
        for entry in self.whitelist:
            if isinstance(entry, str):
                if entry == phrase:
                    return True
            elif callable(entry):
                if entry(phrase, line_text):
                    return True
        return False

    @staticmethod
    def load_phrases_from_yaml(path: Path) -> tuple[str, ...]:
        """Load phrase list from .anti-ai-flavor.yaml. Returns () on failure."""
        if not path.exists():
            return ()
        # Defer yaml import to this single consumer; the module is optional
        # at runtime in some crackerjack distribution channels.
        try:
            yaml_mod = importlib.import_module("yaml")
        except ImportError:
            return ()
        try:
            data = yaml_mod.safe_load(path.read_text())
        except yaml_mod.YAMLError:
            return ()
        if not isinstance(data, dict):
            return ()
        phrases = data.get("phrases", [])
        if not isinstance(phrases, list):
            return ()
        return tuple(str(p) for p in phrases)


def detect_anti_ai_flavor(
    text: str,
    phrases: Sequence[str] | None = None,
    whitelist: Sequence[WhitelistEntry] | WhitelistEntry | None = None,
) -> list[AntiAIFlavorMatch]:
    """Module-level convenience wrapper around AntiAIFlavorDetector."""
    return AntiAIFlavorDetector(
        phrases=phrases,
        whitelist=whitelist,
    ).detect(text)
