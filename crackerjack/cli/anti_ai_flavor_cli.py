
from __future__ import annotations

import json
from pathlib import Path

from crackerjack.services.quality.anti_ai_flavor import (
    AntiAIFlavorDetector,
    detect_anti_ai_flavor,
)


def run_anti_ai_flavor(
    file_path: Path,
    yaml_config: Path | None = None,
    output_json: bool = False,
) -> int:
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return 2

    text = file_path.read_text()

    phrases = None
    if yaml_config is not None:
        phrases = AntiAIFlavorDetector.load_phrases_from_yaml(yaml_config)
        if not phrases:
            print(f"No phrases loaded from {yaml_config}; using built-in defaults.")
            phrases = None

    matches = detect_anti_ai_flavor(text, phrases=phrases)

    if output_json:
        print(
            json.dumps(
                {
                    "file": str(file_path),
                    "match_count": len(matches),
                    "matches": [m.to_dict() for m in matches],
                },
                indent=2,
            )
        )
    else:
        if not matches:
            print(f"[green]No anti-AI-flavor phrases detected in {file_path}[/green]")
        else:
            print(
                f"[yellow]Found {len(matches)} anti-AI-flavor phrase(s) in {file_path}:[/yellow]"
            )
            for m in matches:
                print(f" line {m.line}, col {m.column}: {m.phrase!r}")

    return 1 if matches else 0
