"""Strip comments from ``.json`` files so the JSON hooks can retry them.

The ``format-json`` and ``check-json`` hooks parse strictly with
``json.loads``, so a file carrying comments fails the hook. This module
removes those comments so the phase can strip and retry.

Behaviour is unchanged from the implementation this was moved out of
(``crackerjack/core/autofix_coordinator.py``), which was deleted when the
AI-fix module cluster was removed — see
``docs/plans/2026-11-13-remove-dead-ai-fix-module-cluster.md``.

Known limitation, carried over verbatim: only ``#``-style comments are
recognised. The JSON-with-Comments spec uses ``//`` and ``/* */``, so a
file using those is not actually cleaned. No tracked ``.json`` file in
this repo carries comments, so the path is rarely exercised.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from crackerjack.tools._git_utils import get_files_by_extension
from crackerjack.utils.path_redaction import redact_path

logger = logging.getLogger(__name__)

__all__ = [
    "strip_jsonc_comments",
    "strip_jsonc_comments_from_failed_json_files",
]


def strip_jsonc_comments_from_failed_json_files(root: Path) -> bool:
    """Strip comments from every tracked ``.json`` file under ``root``.

    Returns ``True`` when every file that was rewritten still parsed as
    JSON, ``False`` when a file could not be found or a stripped file
    failed to parse.
    """
    jsonc_files: list[Path] = []
    try:
        jsonc_files = get_files_by_extension([".json"], use_git=True, root=root)
    except Exception:
        logger.exception("Failed to find JSON files for JSONC stripping")
        return False

    if not jsonc_files:
        logger.info("No JSON files found to check for JSONC comments")
        return True

    logger.info(f"Checking {len(jsonc_files)} JSON files for JSONC comments")

    all_successful = True
    for json_file in jsonc_files:
        stripped, had_comments = strip_jsonc_comments(json_file)
        logger.debug(f"{redact_path(json_file)}: had_comments={had_comments}")
        if had_comments:
            try:
                json.loads(stripped)
                json_file.write_text(stripped, encoding="utf-8")
                logger.info(f"Stripped JSONC comments from {redact_path(json_file)}")
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Stripped content from {redact_path(json_file)} is not valid JSON: {e}"
                )
                all_successful = False

    return all_successful


def strip_jsonc_comments(file_path: Path) -> tuple[str, bool]:
    """Return ``(stripped_content, had_comments)`` for one file.

    A ``#`` that is not inside a JSON string starts a comment. The rest of
    that line is dropped.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return "", False

    lines = content.split("\n")
    new_lines = []
    had_comments = False
    for line in lines:
        comment_start = -1
        in_string = False
        i = 0
        while i < len(line):
            c = line[i]
            if c == '"' and (i == 0 or line[i - 1] != "\\"):
                in_string = not in_string
            elif not in_string and c == "#":
                comment_start = i
                break
            i += 1

        if comment_start >= 0:
            had_comments = True
            new_lines.append(line[:comment_start].rstrip())
        else:
            new_lines.append(line)

    return "\n".join(new_lines), had_comments
