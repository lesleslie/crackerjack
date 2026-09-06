"""Tests for ``crackerjack.services.quality.anti_ai_flavor``.

The module wraps a default list of anti-AI "tells" (the
``DEFAULT_PHRASES`` tuple) and runs a regex-based detection over arbitrary
text. The detector supports:

- Custom phrase lists (``phrases=...``)
- Whitelisting: a phrase can be whitelisted by exact match (str) or by a
  callable predicate ``(phrase, line_text) -> bool``
- Case-sensitive / case-insensitive detection
- YAML loading of phrases via ``AntiAIFlavorDetector.load_phrases_from_yaml``

The test fixtures use real ``tmp_path`` for YAML files; ``yaml`` is part
of the test deps (already installed).
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Callable

import pytest

from crackerjack.services.quality.anti_ai_flavor import (
    DEFAULT_PHRASES,
    AntiAIFlavorDetector,
    AntiAIFlavorMatch,
    detect_anti_ai_flavor,
)


# ---------------------------------------------------------------------------
# AntiAIFlavorMatch
# ---------------------------------------------------------------------------


def test_match_to_dict() -> None:
    match = AntiAIFlavorMatch(phrase="delve", line=3, column=5)
    assert match.to_dict() == {"phrase": "delve", "line": 3, "column": 5}


def test_match_is_frozen() -> None:
    match = AntiAIFlavorMatch(phrase="x", line=1, column=1)
    with pytest.raises((AttributeError, Exception)):
        match.phrase = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DEFAULT_PHRASES
# ---------------------------------------------------------------------------


def test_default_phrases_non_empty() -> None:
    assert isinstance(DEFAULT_PHRASES, tuple)
    assert len(DEFAULT_PHRASES) > 0
    # A few canonical entries.
    assert "delve into" in DEFAULT_PHRASES
    assert "leverage" in DEFAULT_PHRASES


# ---------------------------------------------------------------------------
# AntiAIFlavorDetector.__init__
# ---------------------------------------------------------------------------


def test_detector_default_phrases() -> None:
    detector = AntiAIFlavorDetector()
    assert detector.phrases == DEFAULT_PHRASES
    assert detector.whitelist == ()
    assert detector.case_sensitive is False


def test_detector_custom_phrases() -> None:
    detector = AntiAIFlavorDetector(phrases=["foo", "bar"])
    assert detector.phrases == ("foo", "bar")


def test_detector_whitelist_str_singleton() -> None:
    """A single string whitelist becomes a 1-tuple."""
    detector = AntiAIFlavorDetector(whitelist="delve into")
    assert detector.whitelist == ("delve into",)


def test_detector_whitelist_callable_singleton() -> None:
    """A single callable whitelist becomes a 1-tuple."""
    pred: Callable[[str, str], bool] = lambda p, line: False
    detector = AntiAIFlavorDetector(whitelist=pred)
    assert detector.whitelist == (pred,)


def test_detector_whitelist_list() -> None:
    detector = AntiAIFlavorDetector(
        whitelist=["foo", lambda p, line: False]
    )
    assert detector.whitelist == ("foo", detector.whitelist[1])


def test_detector_case_sensitive_compiles_without_ignorecase() -> None:
    """When case_sensitive=True, the patterns don't get the IGNORECASE flag.

    We can't introspect the flag directly, but we can verify that an
    uppercase phrase doesn't match when case_sensitive=True.
    """
    detector = AntiAIFlavorDetector(
        phrases=["delve into"], case_sensitive=True,
    )
    assert detector.detect("DELVE INTO this") == []


def test_detector_case_insensitive_matches_uppercase() -> None:
    detector = AntiAIFlavorDetector(
        phrases=["delve into"], case_sensitive=False,
    )
    matches = detector.detect("DELVE INTO this")
    assert len(matches) == 1
    assert matches[0].phrase == "delve into"


# ---------------------------------------------------------------------------
# detect
# ---------------------------------------------------------------------------


def test_detect_default_phrase() -> None:
    detector = AntiAIFlavorDetector()
    matches = detector.detect("Let's delve into this topic.")
    assert any(m.phrase == "delve into" for m in matches)
    # column is 1-indexed.
    assert matches[0].column >= 1


def test_detect_multiline_reports_correct_line() -> None:
    detector = AntiAIFlavorDetector(phrases=["delve"])
    text = "line one\nline two\nlet's delve here"
    matches = detector.detect(text)
    assert len(matches) == 1
    assert matches[0].line == 3


def test_detect_no_matches_returns_empty() -> None:
    detector = AntiAIFlavorDetector(phrases=["xyzzy"])
    assert detector.detect("nothing here") == []


def test_detect_multiple_matches_on_same_line() -> None:
    detector = AntiAIFlavorDetector(phrases=["foo"])
    text = "foo and foo and foo"
    matches = detector.detect(text)
    assert len(matches) == 3


def test_detect_word_boundary_respected() -> None:
    """``\\b`` ensures we don't match inside larger words."""
    detector = AntiAIFlavorDetector(phrases=["delve"])
    # ``delved`` should NOT match.
    assert detector.detect("He delved into it") == []


# ---------------------------------------------------------------------------
# _is_whitelisted
# ---------------------------------------------------------------------------


def test_whitelist_str_skips_phrase() -> None:
    detector = AntiAIFlavorDetector(
        phrases=["delve into"], whitelist=["delve into"],
    )
    assert detector.detect("delve into this") == []


def test_whitelist_str_does_not_match_other_phrase() -> None:
    detector = AntiAIFlavorDetector(
        phrases=["delve into", "leverage"], whitelist=["leverage"],
    )
    matches = detector.detect("delve into leverage this")
    phrases_matched = {m.phrase for m in matches}
    assert "delve into" in phrases_matched
    assert "leverage" not in phrases_matched


def test_whitelist_callable_skips_phrase() -> None:
    def _skip_delve(phrase: str, _line: str) -> bool:
        return phrase == "delve into"

    detector = AntiAIFlavorDetector(
        phrases=["delve into", "leverage"], whitelist=[_skip_delve],
    )
    matches = detector.detect("delve into leverage")
    phrases_matched = {m.phrase for m in matches}
    assert "delve into" not in phrases_matched
    assert "leverage" in phrases_matched


def test_whitelist_callable_returns_false() -> None:
    def _no_skip(_phrase: str, _line: str) -> bool:
        return False

    detector = AntiAIFlavorDetector(
        phrases=["delve"], whitelist=[_no_skip],
    )
    assert len(detector.detect("delve here")) == 1


# ---------------------------------------------------------------------------
# load_phrases_from_yaml
# ---------------------------------------------------------------------------


def test_load_phrases_missing_file_returns_empty(tmp_path: Path) -> None:
    assert AntiAIFlavorDetector.load_phrases_from_yaml(tmp_path / "nope.yaml") == ()


def test_load_phrases_valid_yaml(tmp_path: Path) -> None:
    yaml = tmp_path / "phrases.yaml"
    yaml.write_text(
        textwrap.dedent(
            """\
            phrases:
              - "smorgasbord"
              - "panacea"
            """
        ),
        encoding="utf-8",
    )
    assert AntiAIFlavorDetector.load_phrases_from_yaml(yaml) == (
        "smorgasbord",
        "panacea",
    )


def test_load_phrases_non_dict_returns_empty(tmp_path: Path) -> None:
    yaml = tmp_path / "list.yaml"
    yaml.write_text("- just\n- a list\n", encoding="utf-8")
    assert AntiAIFlavorDetector.load_phrases_from_yaml(yaml) == ()


def test_load_phrases_missing_key_returns_empty(tmp_path: Path) -> None:
    yaml = tmp_path / "wrong_key.yaml"
    yaml.write_text("foo:\n  - bar\n", encoding="utf-8")
    assert AntiAIFlavorDetector.load_phrases_from_yaml(yaml) == ()


def test_load_phrases_phrases_not_list_returns_empty(tmp_path: Path) -> None:
    yaml = tmp_path / "scalar.yaml"
    yaml.write_text("phrases: not_a_list\n", encoding="utf-8")
    assert AntiAIFlavorDetector.load_phrases_from_yaml(yaml) == ()


def test_load_phrases_coerces_to_strings(tmp_path: Path) -> None:
    yaml = tmp_path / "mixed.yaml"
    yaml.write_text("phrases:\n  - 123\n  - true\n  - 'literal'\n", encoding="utf-8")
    result = AntiAIFlavorDetector.load_phrases_from_yaml(yaml)
    assert result == ("123", "True", "literal")


def test_load_phrases_invalid_yaml_returns_empty(tmp_path: Path) -> None:
    """A malformed YAML file returns ``()`` instead of raising."""
    yaml = tmp_path / "broken.yaml"
    yaml.write_text(": : : not valid yaml", encoding="utf-8")
    assert AntiAIFlavorDetector.load_phrases_from_yaml(yaml) == ()


# ---------------------------------------------------------------------------
# detect_anti_ai_flavor (module-level convenience)
# ---------------------------------------------------------------------------


def test_detect_anti_ai_flavor_uses_defaults() -> None:
    matches = detect_anti_ai_flavor("Let's delve into this.")
    assert any(m.phrase == "delve into" for m in matches)


def test_detect_anti_ai_flavor_with_phrases() -> None:
    matches = detect_anti_ai_flavor("smorgasbord here", phrases=["smorgasbord"])
    assert any(m.phrase == "smorgasbord" for m in matches)


def test_detect_anti_ai_flavor_with_whitelist() -> None:
    matches = detect_anti_ai_flavor(
        "delve here",
        phrases=["delve"],
        whitelist=["delve"],
    )
    assert matches == []
