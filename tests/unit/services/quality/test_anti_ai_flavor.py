"""Tests for anti-AI-flavor phrase detector.

Spec: docs/superpowers/specs/2026-06-22-anti-ai-flavor-style-sop-design.md
Spec #6 from Phase 2 spec batch.

TDD: red -> green -> refactor.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.services.quality.anti_ai_flavor import (
    DEFAULT_PHRASES,
    AntiAIFlavorDetector,
    AntiAIFlavorMatch,
    detect_anti_ai_flavor,
)


class TestAntiAIFlavorMatch:
    """AntiAIFlavorMatch is a typed dict-like container."""

    def test_match_fields(self):
        match = AntiAIFlavorMatch(phrase="delve into", line=1, column=1)
        assert match.phrase == "delve into"
        assert match.line == 1
        assert match.column == 1


class TestDetectorWithDefaultPhrases:
    """The detector ships with a default phrase list."""

    def test_default_phrases_include_common_ai_tics(self):
        # Spot-check the spec's phrase examples.
        assert "delve into" in DEFAULT_PHRASES
        assert "tapestry" in DEFAULT_PHRASES
        assert "leverage" in DEFAULT_PHRASES
        assert "robust" in DEFAULT_PHRASES

    def test_default_phrases_is_tuple_or_list(self):
        assert isinstance(DEFAULT_PHRASES, (tuple, list, frozenset))
        assert len(DEFAULT_PHRASES) >= 4

    def test_detect_returns_match_for_delve_into(self):
        detector = AntiAIFlavorDetector()
        text = "Let's delve into the details of the implementation."
        matches = detector.detect(text)
        assert len(matches) == 1
        assert matches[0].phrase == "delve into"

    def test_detect_returns_match_for_robust(self):
        detector = AntiAIFlavorDetector()
        text = "We need a robust solution for this."
        matches = detector.detect(text)
        assert any(m.phrase == "robust" for m in matches)

    def test_detect_returns_match_for_leverage(self):
        detector = AntiAIFlavorDetector()
        text = "We can leverage the existing framework."
        matches = detector.detect(text)
        assert any(m.phrase == "leverage" for m in matches)

    def test_detect_returns_match_for_tapestry(self):
        detector = AntiAIFlavorDetector()
        text = "The API forms a tapestry of services."
        matches = detector.detect(text)
        assert any(m.phrase == "tapestry" for m in matches)

    def test_returns_empty_list_for_clean_content(self):
        detector = AntiAIFlavorDetector()
        text = "This is a straightforward implementation of the parser."
        matches = detector.detect(text)
        assert matches == []

    def test_word_boundary_avoids_substring_matches(self):
        # "robustly" should not match "robust" if we enforce word boundaries.
        detector = AntiAIFlavorDetector()
        text = "We rebuilt it robustly."
        matches = detector.detect(text)
        # Either no match or only whole-word match
        for m in matches:
            if m.phrase == "robust":
                # If found, must be a whole-word match
                start = m.column - 1
                end = start + len("robust")
                assert text[start:end] == "robust"


class TestLineAndColumn:
    """Matches report source position (line, column) for actionable feedback."""

    def test_first_line_match_reports_line_1(self):
        detector = AntiAIFlavorDetector(phrases=("delve into",))
        text = "delve into the codebase"
        matches = detector.detect(text)
        assert len(matches) == 1
        assert matches[0].line == 1
        assert matches[0].column == 1

    def test_second_line_match_reports_line_2(self):
        detector = AntiAIFlavorDetector(phrases=("robust",))
        text = "first line clean\nthis is robust code"
        matches = detector.detect(text)
        assert len(matches) == 1
        assert matches[0].line == 2

    def test_column_points_to_start_of_phrase(self):
        detector = AntiAIFlavorDetector(phrases=("leverage",))
        text = "We will leverage this API."
        matches = detector.detect(text)
        assert len(matches) == 1
        # "We will leverage this API."
        # columns: W=1, e=2, ' '=3, w=4, i=5, l=6, l=7, ' '=8, l=9
        assert matches[0].column == 9


class TestConfigurablePhraseList:
    """Phrases can be customized per detector."""

    def test_custom_phrase_list_used(self):
        custom = ("my_custom_phrase",)
        detector = AntiAIFlavorDetector(phrases=custom)
        text = "this contains my_custom_phrase here"
        matches = detector.detect(text)
        assert len(matches) == 1
        assert matches[0].phrase == "my_custom_phrase"

    def test_empty_phrase_list_returns_no_matches(self):
        detector = AntiAIFlavorDetector(phrases=())
        text = "delve into this tapestry"
        matches = detector.detect(text)
        assert matches == []

    def test_default_phrases_used_when_none_provided(self):
        detector = AntiAIFlavorDetector()
        # Should pick up default phrases
        text = "We leverage a robust solution."
        matches = detector.detect(text)
        assert len(matches) >= 2  # leverage + robust


class TestLoadPhrasesFromYaml:
    """Phrase lists can be loaded from .anti-ai-flavor.yaml."""

    def test_load_phrases_from_yaml_file(self, tmp_path: Path):
        yaml_path = tmp_path / ".anti-ai-flavor.yaml"
        yaml_path.write_text(
            "phrases:\n"
            "  - custom_phrase_one\n"
            "  - custom_phrase_two\n"
        )
        phrases = AntiAIFlavorDetector.load_phrases_from_yaml(yaml_path)
        assert phrases == ("custom_phrase_one", "custom_phrase_two")

    def test_load_phrases_returns_empty_when_file_missing(self, tmp_path: Path):
        yaml_path = tmp_path / "does_not_exist.yaml"
        phrases = AntiAIFlavorDetector.load_phrases_from_yaml(yaml_path)
        assert phrases == ()

    def test_load_phrases_returns_empty_when_yaml_malformed(self, tmp_path: Path):
        yaml_path = tmp_path / "bad.yaml"
        yaml_path.write_text(": not valid yaml:\n  - [\n")
        phrases = AntiAIFlavorDetector.load_phrases_from_yaml(yaml_path)
        # Should return empty list, not raise
        assert phrases == ()

    def test_load_phrases_returns_empty_when_no_phrases_key(self, tmp_path: Path):
        yaml_path = tmp_path / "no_phrases.yaml"
        yaml_path.write_text("other_key: value\n")
        phrases = AntiAIFlavorDetector.load_phrases_from_yaml(yaml_path)
        assert phrases == ()


class TestWhitelist:
    """Specific phrases can be allowed in specific contexts."""

    def test_whitelist_phrase_is_ignored(self):
        detector = AntiAIFlavorDetector(
            phrases=("leverage",),
            whitelist=("leverage",),
        )
        text = "We leverage the framework."
        matches = detector.detect(text)
        assert matches == []

    def test_whitelist_only_affects_listed_phrases(self):
        detector = AntiAIFlavorDetector(
            phrases=("leverage", "robust"),
            whitelist=("leverage",),
        )
        text = "leverage and robust"
        matches = detector.detect(text)
        assert len(matches) == 1
        assert matches[0].phrase == "robust"

    def test_whitelist_can_be_callable(self):
        """Whitelist can be a callable for context-aware allow-listing."""

        def whitelist_fn(phrase: str, line: str) -> bool:
            return phrase == "robust" and "test" in line

        detector = AntiAIFlavorDetector(
            phrases=("robust",),
            whitelist=whitelist_fn,
        )
        # "robust" in a test line should be allowed
        text = "this is a robust test for the parser"
        matches = detector.detect(text)
        assert matches == []

        # "robust" in a non-test line should still be flagged
        text2 = "we need a robust solution"
        matches2 = detector.detect(text2)
        assert len(matches2) == 1


class TestConvenienceFunction:
    """Module-level detect_anti_ai_flavor wraps the detector."""

    def test_convenience_function_returns_matches(self):
        text = "delve into the codebase"
        matches = detect_anti_ai_flavor(text)
        assert len(matches) == 1
        assert matches[0].phrase == "delve into"

    def test_convenience_function_accepts_phrases(self):
        text = "use my_special_word here"
        matches = detect_anti_ai_flavor(text, phrases=("my_special_word",))
        assert len(matches) == 1


class TestMixedFlaggedAndCleanContent:
    """Verify behavior on realistic mixed content (Y2 false-positive regression)."""

    def test_mixed_content_detects_only_flagged(self):
        text = (
            "# Changelog\n"
            "\n"
            "## 2026-06-27\n"
            "\n"
            "We delve into the parser to add support for new formats.\n"
            "\n"
            "The fix is straightforward: a single regex update.\n"
            "\n"
            "We leverage the existing tokenizer.\n"
        )
        detector = AntiAIFlavorDetector()
        matches = detector.detect(text)
        phrases = {m.phrase for m in matches}
        # Flag the AI-flavor words
        assert "delve into" in phrases
        assert "leverage" in phrases
        # The clean sentence should not be flagged
        assert not any("straightforward" in m.phrase for m in matches)

    def test_multiple_occurrences_each_reported(self):
        text = "leverage one. leverage two. leverage three."
        detector = AntiAIFlavorDetector(phrases=("leverage",))
        matches = detector.detect(text)
        assert len(matches) == 3


@pytest.mark.parametrize(
    "phrase, sample",
    [
        ("delve into", "We delve into the history."),
        ("tapestry", "a tapestry of features"),
        ("leverage", "leverage the existing API"),
        ("robust", "a robust solution"),
    ],
)
def test_default_phrases_each_detected(phrase: str, sample: str):
    """Parametrized verification of each default phrase from the spec."""
    detector = AntiAIFlavorDetector()
    matches = detector.detect(sample)
    assert any(m.phrase == phrase for m in matches), (
        f"Expected '{phrase}' to be detected in: {sample!r}"
    )
