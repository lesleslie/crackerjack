"""Crackerjack adapter for anti-AI-flavor check.

Spec: docs/superpowers/specs/2026-06-22-anti-ai-flavor-style-sop-design.md
Spec #6 from Phase 2 spec batch.

Provides run_anti_ai_flavor_check() for integration with the existing
crackerjack quality flow. The adapter is intentionally lightweight —
it reads the file, runs the detector, and returns a structured report
that other Crackerjack components can consume.

The adapter is advisory in v1.0 (matches the spec's "Advisory in v1.1,
gate in v2.0" policy).
"""

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
    """Result of running the anti-AI-flavor check on a single file."""

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
    """Run the anti-AI-flavor check on a file.

    Args:
        file_path: The file to scan. Must exist.
        yaml_config: Optional .anti-ai-flavor.yaml path. If provided and
            phrases are loaded, those replace the built-in defaults.

    Raises:
        FileNotFoundError: If file_path does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    text = file_path.read_text()

    phrases = None
    if yaml_config is not None:
        phrases = AntiAIFlavorDetector.load_phrases_from_yaml(yaml_config)
        # Empty result -> fall back to defaults (consistent with CLI behavior)
        if not phrases:
            phrases = None

    matches = detect_anti_ai_flavor(text, phrases=phrases)
    return AntiAIFlavorReport(file=str(file_path), matches=matches)