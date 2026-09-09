"""Jinja template formatter — Tier 1 only.

Phase 4 ships the always-on Tier 1 canonicalization:
- Trailing newline at EOF.
- No trailing whitespace per line.
- Preserve `{%-` / `-%}` / `{{-` / `-}}` markers AND surrounding text.

Tier 2 normalization (`[tool.crackerjack.jinja] normalize = true`) is deferred
to a future phase. The Phase 4 design choice was to use raw-source string ops
instead of `lex()` token reconstruction — token values lose the very whitespace
control that Tier 1 rule 3 promises to preserve. `Environment.lex()` is still
called as a syntax-validation gate; on `TemplateSyntaxError`, the source is
returned unchanged.

Per-project delimiter config (`[tool.crackerjack.jinja]` in pyproject.toml) is
loaded by `_load_jinja_config` — see spec Jinja F2 / Data Flow step 3.
"""
from __future__ import annotations

import logging
import tomllib
from collections.abc import Mapping
from pathlib import Path

import jinja2

logger = logging.getLogger(__name__)

JINJA_SUFFIXES: frozenset[str] = frozenset({".html", ".j2", ".jinja"})

DEFAULT_DELIMITERS: Mapping[str, str] = {
    "block_start": "{%",
    "block_end": "%}",
    "variable_start": "{{",
    "variable_end": "}}",
    "comment_start": "{#",
    "comment_end": "#}",
}

_REQUIRED_DELIMITER_KEYS = frozenset(DEFAULT_DELIMITERS.keys())


def _env(delimiters: Mapping[str, str]) -> jinja2.Environment:
    """Construct a Jinja2 Environment with the 6 delimiter kwargs.

    `keep_trailing_newline=True` is set so the lexer's validation pass does
    not silently strip a trailing newline.
    """
    return jinja2.Environment(
        block_start_string=delimiters["block_start"],
        block_end_string=delimiters["block_end"],
        variable_start_string=delimiters["variable_start"],
        variable_end_string=delimiters["variable_end"],
        comment_start_string=delimiters["comment_start"],
        comment_end_string=delimiters["comment_end"],
        keep_trailing_newline=True,
    )


def _apply_tier1(source: str) -> str:
    """Apply Tier 1 canonicalization rules to the raw source string.

    Rules (per spec Jinja F3 Tier 1):
    1. Trailing newline at EOF.
    2. Strip trailing whitespace from each line.
    3. Preserve `{%-` / `-%}` / `{{-` / `-}}` markers (untouched by construction;
       we only operate on line-level trailing whitespace).
    """
    lines = source.splitlines()
    lines = [line.rstrip() for line in lines]
    out = "\n".join(lines)
    if source.endswith("\n"):
        out += "\n"
    elif out:
        out += "\n"
    return out


def format_template(
    source: str,
    delimiters: Mapping[str, str] | None = None,
) -> str:
    """Format `source` per Tier 1 rules. `lex()` validates; if it raises,
    `source` is returned unchanged.

    Phase 4 ships Tier 1 only. The `normalize` parameter is REMOVED from Rev 1;
    Tier 2 is deferred to a future phase.

    Mismatch detection: jinja2's `lex()` does NOT raise on delimiter
    mismatches — it tokenizes unmatched delimiters as plain text data. To
    satisfy the spec's "best-effort, return source unchanged on lex failure"
    contract for misconfigured delimiters, we pre-screen the source for the
    presence of any *standard* delimiter markers (`{%`, `%}`, `{{`, `}}`,
    `{#`, `#}`) when the env is configured with non-standard delimiters.
    """
    delims = delimiters or DEFAULT_DELIMITERS
    if not _delimiters_match_source(delims, source):
        logger.warning("Jinja delimiter mismatch; returning source unchanged")
        return source
    env = _env(delims)
    try:
        list(env.lex(source))
    except jinja2.TemplateSyntaxError:
        logger.warning("Jinja lex failed; returning source unchanged")
        return source
    return _apply_tier1(source)


def _delimiters_match_source(delims: Mapping[str, str], source: str) -> bool:
    """Return True iff `source` contains no standard delimiters when non-standard
    delimiters are configured (or vice versa).

    Standard delimiter markers: `{%`, `%}`, `{{`, `}}`, `{#`, `#}`.
    When the env is configured with non-standard delimiters, any appearance of
    a standard marker in the source indicates a delimiter mismatch that jinja2's
    `lex()` will silently swallow.
    """
    standard_markers = ("{%", "%}", "{{", "}}", "{#", "#}")
    is_standard_config = all(
        delims[key] == DEFAULT_DELIMITERS[key] for key in DEFAULT_DELIMITERS
    )
    if is_standard_config:
        # Standard delimiters: any marker in source is expected.
        return True
    # Non-standard delimiters: ensure source has no standard markers.
    return not any(marker in source for marker in standard_markers)


def _load_delimiters_from_pyproject(project_root: Path) -> Mapping[str, str] | None:
    """Read `[tool.crackerjack.jinja]` and return the 6 delimiter keys, or None if absent/malformed."""
    pyproject = project_root / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    section = data.get("tool", {}).get("crackerjack", {}).get("jinja", {})
    if not isinstance(section, dict):
        return None
    if not _REQUIRED_DELIMITER_KEYS.issubset(section):
        return None
    return {key: str(section[key]) for key in _REQUIRED_DELIMITER_KEYS}


def _load_jinja_config(project_root: Path) -> tuple[Mapping[str, str], bool]:
    """Return `(delimiters, normalize)` for `project_root`.

    `delimiters` is the 6-key mapping. `normalize` is always False in Phase 4
    (Tier 2 deferred). Defaults to standard delimiters when the config is absent.
    """
    delims = _load_delimiters_from_pyproject(project_root) or DEFAULT_DELIMITERS
    return delims, False


__all__ = [
    "DEFAULT_DELIMITERS",
    "JINJA_SUFFIXES",
    "_apply_tier1",
    "_env",
    "_load_jinja_config",
    "format_template",
]
