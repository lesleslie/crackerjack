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
    phrase: str
    line: int
    column: int

    def to_dict(self) -> dict[str, int | str]:
        return {"phrase": self.phrase, "line": self.line, "column": self.column}


WhitelistEntry = str | Callable[[str, str], bool]


class AntiAIFlavorDetector:
    def __init__(
        self,
        phrases: Sequence[str] | None = None,
        whitelist: Sequence[WhitelistEntry] | WhitelistEntry | None = None,
        case_sensitive: bool = False,
    ) -> None:

        if phrases is None:
            self.phrases: tuple[str, ...] = DEFAULT_PHRASES
        else:
            self.phrases = tuple(phrases)

        if whitelist is None:
            self.whitelist: tuple[WhitelistEntry, ...] = ()
        elif isinstance(whitelist, str) or callable(whitelist):
            self.whitelist = (t.cast("WhitelistEntry", whitelist),)
        else:
            self.whitelist = tuple(whitelist)
        self.case_sensitive = case_sensitive

        flags = 0 if case_sensitive else re.IGNORECASE

        self._patterns: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
            (phrase, re.compile(rf"\b{re.escape(phrase)}\b", flags))
            for phrase in self.phrases
        )

    def detect(self, text: str) -> list[AntiAIFlavorMatch]:
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
        if not path.exists():
            return ()

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
    return AntiAIFlavorDetector(
        phrases=phrases,
        whitelist=whitelist,
    ).detect(text)
