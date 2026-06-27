"""Tests for anti-AI-flavor CLI wrapper."""

from __future__ import annotations

import json
from pathlib import Path

from crackerjack.cli.anti_ai_flavor_cli import run_anti_ai_flavor


class TestRunAntiAIFlavor:
    def test_returns_1_when_phrases_detected(self, tmp_path: Path, capsys):
        target = tmp_path / "mr.md"
        target.write_text("Let's delve into the parser.\n")
        exit_code = run_anti_ai_flavor(target)
        assert exit_code == 1
        out = capsys.readouterr().out
        assert "delve into" in out

    def test_returns_0_when_clean(self, tmp_path: Path, capsys):
        target = tmp_path / "mr.md"
        target.write_text("This is a straightforward fix.\n")
        exit_code = run_anti_ai_flavor(target)
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "No anti-AI-flavor" in out

    def test_returns_2_when_file_missing(self, capsys):
        exit_code = run_anti_ai_flavor(Path("/does/not/exist.md"))
        assert exit_code == 2
        out = capsys.readouterr().out
        assert "File not found" in out

    def test_yaml_config_overrides_default_phrases(
        self, tmp_path: Path, capsys
    ):
        yaml_path = tmp_path / ".anti-ai-flavor.yaml"
        yaml_path.write_text("phrases:\n  - custom_flag\n")
        target = tmp_path / "mr.md"
        target.write_text("uses custom_flag here and also delve into something\n")
        exit_code = run_anti_ai_flavor(target, yaml_config=yaml_path)
        assert exit_code == 1
        out = capsys.readouterr().out
        assert "custom_flag" in out
        # Default 'delve into' should NOT be flagged when YAML is provided
        assert "delve into" not in out

    def test_json_output_format(self, tmp_path: Path, capsys):
        target = tmp_path / "mr.md"
        target.write_text("We leverage the API.\n")
        exit_code = run_anti_ai_flavor(target, output_json=True)
        assert exit_code == 1
        out = capsys.readouterr().out.strip()
        # Parse the JSON payload (it may be preceded by rich tags, so find the JSON block)
        start = out.find("{")
        assert start >= 0, f"No JSON object found in: {out!r}"
        payload = json.loads(out[start:])
        assert payload["file"] == str(target)
        assert payload["match_count"] >= 1
        assert any(m["phrase"] == "leverage" for m in payload["matches"])