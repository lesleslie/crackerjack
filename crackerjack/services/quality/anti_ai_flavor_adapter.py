
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from crackerjack.services.quality.anti_ai_flavor import (
    AntiAIFlavorDetector,
    AntiAIFlavorMatch,
    detect_anti_ai_flavor,
)


@dataclass
class AntiAIFlavorReport:

    file: str
    matches: list[AntiAIFlavorMatch] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.matches) == 0

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "is_clean": self.is_clean,
            "match_count": len(self.matches),
            "matches": [m.to_dict() for m in self.matches],
        }


def run_anti_ai_flavor_check(
    file_path: Path,
    yaml_config: Path | None = None,
) -> AntiAIFlavorReport:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    text = file_path.read_text()

    phrases = None
    if yaml_config is not None:
        phrases = AntiAIFlavorDetector.load_phrases_from_yaml(yaml_config)

        if not phrases:
            phrases = None

    matches = detect_anti_ai_flavor(text, phrases=phrases)
    return AntiAIFlavorReport(file=str(file_path), matches=matches)
