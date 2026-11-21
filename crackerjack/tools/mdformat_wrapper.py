from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

from ._git_utils import get_git_tracked_files

# A byte-order mark is not whitespace -- ``"﻿".isspace()`` is False --
# so ``"﻿---".strip()`` keeps the mark and every ``---`` test in
# this module would miss it. Documents that open with one are handled
# explicitly.
_BOM = "﻿"

# A ``---`` line at column 0 whose next non-empty line is a YAML key
# opens a YAML block. Counting these blocks is what separates the two
# file shapes that both begin with ``---``:
#
#   * a markdown document with frontmatter -- ONE block, its own opener
#   * a stream of YAML documents -- MANY blocks, one per document
#
# Fenced code blocks are excluded. A ``---`` inside a ```yaml fence is
# sample content, not a document separator, and the fleet's templates
# show frontmatter inside such a fence. Tracking the fence state is
# what keeps those templates in scope.
_YAML_BLOCK_SEP = re.compile(r"^---[ \t]*$")
_YAML_BLOCK_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*:")
_CODE_FENCE = re.compile(r"^\s*(```|~~~)")


def _yaml_block_boundaries(text: str) -> int:
    """How many YAML blocks the text opens, ignoring fenced code.

    Each ``---`` separator at column 0 is tested against the next
    non-empty line: if that line is a YAML key at column 0 the
    separator opens a YAML block.
    """
    lines = text.splitlines()
    count = 0
    in_fence = False
    for index, line in enumerate(lines):
        if _CODE_FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or not _YAML_BLOCK_SEP.match(line):
            continue
        for following in lines[index + 1 :]:
            if not following.strip():
                continue
            if _YAML_BLOCK_KEY.match(following):
                count += 1
            break
    return count


def _is_multi_document_yaml(file_path: Path) -> bool:
    """True when the file is a stream of YAML documents, not markdown.

    The fleet has files that wear a ``.md`` extension but hold YAML:
    Claude Code slash-command definitions are a run of ``---``-separated
    YAML documents. mdformat is a *markdown* formatter, and handed such
    a file it reads the prose line before each separator as a setext
    heading underline, so every document separator becomes an ATX
    heading::

        ---
        description: Show jot inbox vitals
        allowed-tools: []
        ---

    turns into ``## description: Show jot inbox vitals allowed-tools: []``.
    That is not a formatting difference, it is a destroyed file.

    Two parts to the test, and both are needed:

    * the file must OPEN with a ``---`` fence -- a YAML stream always
      does, and a markdown document that opens with a heading never
      does, so this keeps ordinary prose out of the scan;
    * it must contain at least TWO YAML blocks outside fenced code --
      one block is frontmatter, the shape every markdown document in
      the fleet has.
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return False
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    # Count over the WHOLE text. The opening fence is itself a
    # boundary -- it is what makes the first document a YAML block --
    # so counting only the lines after it would drop one from the total
    # and miss a two-document stream.
    return _yaml_block_boundaries(text) >= 2


def should_skip_file(file_path: Path) -> bool:
    skip_patterns = [
        # Per-area archives land under `<area>/.archive/` — match any
        # of them via a recursive glob (`**/.archive/**`) so the new
        # `docs/plans/.archive/`, `docs/specs/.archive/`, etc. are
        # excluded alongside the legacy `docs/archive/` location.
        "**/.archive/**",
        "**/archives/**",
        "*COMPLETE.md",
        "*ANALYSIS.md",
        "*PROGRESS.md",
        "*STATUS.md",
        "*PLAN.md",
        "*SUMMARY.md",
        "CHECKPOINT_*.md",
        "NOTES.md",
        "CLEANUP_*.md",
        "COMPREHENSIVE_*.md",
        "PYPROJECT_*.md",
        "TEST_*.md",
    ]
    file_str = str(file_path)
    if any(fnmatch.fnmatch(file_str, pattern) for pattern in skip_patterns):
        return True

    try:
        with file_path.open(encoding="utf-8") as fh:
            first_line = fh.readline()
    except OSError:
        return False
    stripped = first_line.strip()

    if stripped.startswith(_BOM):
        # Strip the mark and look at what follows it.
        had_bom = True
        stripped = stripped.lstrip(_BOM).strip()
    else:
        had_bom = False

    if had_bom and stripped == "---":
        # A BOM'd frontmatter document. The plugin's front-matter rule
        # is BOM-blind too, so handing this to mdformat would flatten
        # its frontmatter into a heading and drop the document out of
        # PLAN_INDEX.md -- the exact failure the guard exists to
        # prevent. Exclude it instead, and let main() report it, since
        # an excluded document is one nobody notices.
        return True

    # NOTE: a document whose first line is ``---`` is NOT skipped. That
    # exclusion existed because mdformat 1.0.0 core has no frontmatter
    # support -- it rewrites the fence into a horizontal rule and
    # flattens the YAML into body text, and a plan whose frontmatter
    # stops parsing drops out of PLAN_INDEX.md entirely. The
    # ``mdformat-frontmatter`` plugin re-serialises the block through a
    # ruamel round-trip that preserves quotes, comments and key order,
    # so the parsed values survive and the exclusion is no longer
    # needed. The fleet's 783 frontmatter'd documents can finally be
    # formatted.
    #
    # The underscore clause below is a different rule about a different
    # thing and stays.
    if stripped == "---" and _is_multi_document_yaml(file_path):
        # A ``.md`` file that is really a stream of YAML documents.
        # mdformat would turn each document separator into a heading,
        # which destroys the file rather than formatting it.
        return True

    return len(stripped) >= 3 and set(stripped) == {"_"}


def _resolve_mdformat_bin() -> str:
    """Locate the mdformat binary.

    Prefers the repo's own ``.venv`` binary and falls back to whatever
    ``mdformat`` is on ``PATH``.
    """
    mdformat_bin = Path.cwd() / ".venv" / "bin" / "mdformat"
    if mdformat_bin.exists():
        return str(mdformat_bin)
    return shutil.which("mdformat") or "mdformat"


def _build_mdformat_cmd(files: list[Path], argv: list[str] | None) -> list[str]:
    """Assemble the mdformat command line for ``files``.

    ``--number`` preserves the source numbering of ordered lists.
    mdformat's default renders every ordered-list item with the marker
    ``1.``, so a list written ``3. 4.`` becomes ``3. 1.``. In a decision
    record or a plan the number is often a reference rather than
    decoration -- an item numbered 4 becomes 1, and any prose pointing
    at "item 4" points at nothing.

    With ``--number`` mdformat applies consecutive numbering: it keeps
    the first marker of each list and numbers the rest from it. A
    well-formed list is unchanged, a list that continues a count from a
    sibling list is unchanged, and a list that an earlier default-mode
    format pass collapsed to ``1. 1. 1.`` is repaired to ``1. 2. 3.``.
    No marker is ever decreased, so a reference to "item N" still lands
    on the same item.

    The ``--extensions`` flag is deliberately NOT passed. mdformat's CLI
    enables every installed parser extension by default, and naming one
    explicitly *restricts* the enabled set to just that one -- passing
    ``--extensions frontmatter`` silently disables ``tables`` (which
    comes from mdformat-gfm) and any other extension that happens to be
    installed. No fleet venv installs mdformat-gfm today, so the fleet's
    mdformat is table-blind either way; the wrapper carries its own
    table-aware comparison for that reason. The frontmatter extension
    is verified separately, by
    :func:`_frontmatter_extension_available`.
    """
    cmd = [_resolve_mdformat_bin(), "--no-codeformatters", "--number"]

    if argv:
        cmd.extend(argv)

    cmd.extend([str(f) for f in files])
    return cmd


# Counts the mdformat parser extensions that define a renderer for the
# ``front_matter`` syntax. It runs in a subprocess because mdformat is
# executed as a separate binary: the extension must be present in THAT
# interpreter's site-packages, not in crackerjack's own imports.
#
# Counting rather than asking "is ``frontmatter`` registered?" matters.
# Two packages provide front-matter rendering and their entry-point
# names differ -- ``mdformat-frontmatter`` registers as ``frontmatter``,
# ``mdformat-front-matters`` (KyleKing) registers as ``front_matters``
# -- so pip installs both side by side without complaining. mdformat
# then logs a plugin conflict, keeps one renderer, and the two packages
# behave oppositely on the same input: one preserves quotes, the other
# strips them, which turns a quoted "yes" into a YAML 1.1 boolean.
_FRONTMATTER_PROBE = (
    "import importlib.metadata as m; "
    "print(sum(1 for e in m.entry_points(group='mdformat.parser_extension') "
    "if 'front_matter' in getattr(e.load(), 'RENDERERS', {})))"
)


def _frontmatter_extension_count(mdformat_bin: str) -> int | None:
    """How many front-matter extensions the mdformat environment has.

    ``None`` means the probe could not be run or could not be parsed,
    which the guard treats as "not safe to format".
    """
    python = Path(mdformat_bin).with_name("python")
    if not python.exists():
        # A mdformat on PATH may live outside a venv. The hook itself
        # runs under the repo's interpreter, so probe that one.
        python = Path(sys.executable)
    if not python.exists():
        return None

    try:
        result = subprocess.run(
            [str(python), "-c", _FRONTMATTER_PROBE],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except OSError, subprocess.SubprocessError:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def _frontmatter_extension_available(mdformat_bin: str) -> bool:
    """True when exactly one front-matter extension is registered.

    mdformat 1.0.0 core has no frontmatter support at all: given a
    document whose first line is ``---`` it rewrites the fence into a
    horizontal rule and flattens the YAML into body text. The
    ``mdformat-frontmatter`` plugin re-serialises the block through a
    ruamel round-trip that preserves quotes, comments and key order, so
    what the YAML parsers read is unchanged.

    Exactly one, not at least one: a second front-matter extension is
    a silent semantic hazard, and it is detectable.
    """
    return _frontmatter_extension_count(mdformat_bin) == 1


def _frontmatter_documents(files: list[Path]) -> list[Path]:
    """The files whose first line opens a YAML frontmatter block.

    Callers pass every tracked document, not only the ones about to be
    formatted: the guard asserts the safety property over the whole
    tracked tree, and a scope-limited check would miss a document that
    some other rule excludes from this run.

    A BOM'd frontmatter document is deliberately not in this list. It
    is excluded from formatting (the plugin's front-matter rule is
    BOM-blind), so it needs no plugin -- and it is reported separately,
    by :func:`_bom_frontmatter_documents`.
    """
    found: list[Path] = []
    for path in files:
        try:
            with path.open(encoding="utf-8") as fh:
                if fh.readline().strip() == "---":
                    found.append(path)
        except OSError:
            continue
    return found


def _multi_document_yaml_documents(files: list[Path]) -> list[Path]:
    """The files that are streams of YAML documents rather than markdown.

    These are excluded from formatting because mdformat would turn each
    document separator into a heading and destroy them. They are
    reported rather than skipped quietly: an excluded file is one
    nobody notices, and "why is this file never formatted?" is a
    question every operator eventually asks.
    """
    return [path for path in files if _is_multi_document_yaml(path)]


# --- GFM rendering comparison -------------------------------------------------
#
# mdformat's own safety net is ``mdformat._util.is_md_equal``: it renders
# both sides of a comparison with mdformat's parser and compares the
# HTML. That parser has NO table support -- a GFM table is just a
# paragraph to it.
#
# That is the blind spot. mdformat can merge a table's rows into one
# line, or re-indent a table out of the list item that contains it,
# and its check cannot see the damage because it cannot parse what
# changed. The check answers "did the parse tree change?" when the
# question is "does the document still read the same?".
#
# Rendering both sides with a table-aware parser answers the question
# that matters. If the rendering differs, the document was damaged, and
# the damage is rolled back.

_GFM_RENDERER: Any = None
_FRONTMATTER_BLOCK = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_WHITESPACE = re.compile(r"\s+")


def _gfm_renderer() -> Any:
    """A markdown-it renderer with GFM tables and strikethrough.

    Built lazily: importing markdown-it-py costs real time and the
    wrapper is imported by every hook.
    """
    global _GFM_RENDERER
    if _GFM_RENDERER is None:
        from markdown_it import MarkdownIt
        from markdown_it.renderer import RendererHTML

        _GFM_RENDERER = MarkdownIt(renderer_cls=RendererHTML).enable(
            ["table", "strikethrough"]
        )
    return _GFM_RENDERER


def _rendered_html(text: str) -> str:
    """Render a document the way a GFM reader would.

    The frontmatter block is stripped first. This renderer has no
    frontmatter plugin, so the block would be read as body text -- and
    the frontmatter plugin re-serialises YAML through a ruamel
    round-trip that changes that text without changing its meaning.
    The frontmatter has its own semantic check; this one is about the
    body.
    """
    html = _gfm_renderer().render(_FRONTMATTER_BLOCK.sub("", text, count=1))
    html = _WHITESPACE.sub(" ", html)
    html = html.replace("<p> ", "<p>").replace(" </p>", "</p>")
    return html.strip()


def _rendering_changes(before: str, after: str) -> bool:
    """True when the two documents do not read the same."""
    return _rendered_html(before) != _rendered_html(after)


# mdformat reports the file it refused with a message that names it:
#
#     Error: Could not format
#     "/path/to/doc.md".
#
# The path is on its own line, in quotes.
_COULD_NOT_FORMAT = re.compile(r'Could not format\s*\n"(?P<path>[^"]+)"')


def _bom_frontmatter_documents(files: list[Path]) -> list[Path]:
    """The files that open with a byte-order mark before a ``---`` fence.

    These are excluded from formatting because the plugin's front-matter
    rule is BOM-blind: handing one to mdformat flattens its frontmatter
    into a heading, and the document then drops out of PLAN_INDEX.md.
    Excluded documents are the ones nobody notices, so they are
    reported rather than skipped quietly.
    """
    found: list[Path] = []
    for path in files:
        try:
            with path.open(encoding="utf-8") as fh:
                first_line = fh.readline().strip()
        except OSError:
            continue
        if first_line.startswith(_BOM) and first_line.lstrip(_BOM).strip() == "---":
            found.append(path)
    return found


def _report_tool_output(text: str) -> None:
    """Surface a diagnostic without turning it into a hook failure.

    The ``✓`` prefix is load-bearing. Both
    ``crackerjack/parsers/regex_parsers.py`` (the regex parser) and
    ``crackerjack/utils/issue_detection.extract_issue_lines`` (the
    line-counting safety net) treat a ``✓``-prefixed line as passed
    output rather than as a reported issue, which is how
    :func:`_report_auto_formatted` keeps its own diagnostics out of the
    issue count.

    These are informational, not failures: mdformat exited 0, so the
    format succeeded. What matters is that the operator sees them --
    a front-matter block that could not be parsed, or a plugin conflict
    mdformat resolved silently -- rather than having them swallowed.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        print(f"✓ mdformat: {stripped}", file=sys.stderr)


def _report_auto_formatted(files: list[Path]) -> None:
    """Report the files mdformat just rewrote.

    The list is the files THIS run changed. An earlier version ran
    ``git diff --name-only`` over them, which reports every file that
    differs from HEAD -- including files another session had edited
    and this run never touched. The report then named work that was
    not the formatter's.
    """
    # Silent auto-format path: surface what was changed so the
    # next "mdformat (failed)" message has substance.
    #
    # Two downstream parsers both see this output:
    #
    # 1. ``crackerjack/parsers/regex_parsers.py`` (regex parser).
    #    Returns 0 issues because the success marker ``✓`` and
    #    the substring ``passed`` short-circuit the
    #    ``success_indicators`` check at
    #    ``crackerjack/parsers/regex_parsers.py:326``.
    #
    # 2. ``crackerjack/utils/issue_detection.extract_issue_lines``
    #    (line-counting safety net). The ``✓`` prefix hits the
    #    ``_SUCCESS_PREFIXES`` filter at
    #    ``crackerjack/utils/issue_detection.py:11`` so each
    #    diagnostic line is excluded from the count.
    #
    # The literal ``files were modified by this hook`` substring
    # is also emitted because
    # ``crackerjack/executors/hook_executor.py:802`` requires
    # it for any hook marked ``is_formatting=True`` that exits 1:
    # without it the panel re-routes exit-1 to status="failed".
    print(
        f"✓ mdformat: PASSED hook after auto-formatted "
        f"{len(files)} file(s) (re-run to confirm clean "
        f"state): files were modified by this hook",
        file=sys.stderr,
    )
    for path in files:
        print(f"✓   {path}", file=sys.stderr)


def _frontmatter_environment_is_unsafe(all_files: list[Path]) -> bool:
    """True when the environment cannot format frontmatter safely.

    Fail loud rather than silently destroy frontmatter.

    mdformat 1.0.0 core rewrites a document's ``---`` YAML frontmatter
    fence into a horizontal rule and flattens the YAML into body text. A
    plan whose frontmatter is mangled can then fail extraction and
    disappear from PLAN_INDEX.md, making its lifecycle state invisible.

    The check scans every tracked document, not just the ones in scope,
    and it runs BEFORE the "nothing to do" short-circuit. The skip list
    still excludes documents by other rules (archive paths, ``*PLAN.md``),
    so a scope-limited check would miss a frontmatter'd document that
    this run would not have formatted anyway, and a later check would
    never fire at all when the scope is empty. Scoping it to
    ``all_files`` makes it a live assertion of the safety property over
    the whole tracked tree.

    The guard predates the lift of the frontmatter skip and is what
    makes the lift safe: if the plugin is ever missing from the
    environment that will run mdformat, the run stops instead of
    flattening 783 documents' frontmatter into body text. It also
    refuses to run when a SECOND front-matter extension is present,
    because mdformat resolves that conflict silently apart from a log
    line and the two packages disagree about quotes.
    """
    if not _frontmatter_documents(all_files):
        return False

    count = _frontmatter_extension_count(_resolve_mdformat_bin())
    if count == 0:
        print(
            "mdformat: the 'frontmatter' parser extension is not installed "
            "in the environment that will run mdformat. Without it "
            "mdformat rewrites YAML frontmatter into body text, which can "
            "drop a document out of the plan index. Run 'uv sync "
            "--all-groups' in the repo (crackerjack declares "
            "mdformat-frontmatter) and retry.",
            file=sys.stderr,
        )
        return True
    if count is None:
        print(
            "mdformat: could not determine whether the 'frontmatter' "
            "parser extension is installed in the environment that will "
            "run mdformat. Without it mdformat rewrites YAML frontmatter "
            "into body text, which can drop a document out of the plan "
            "index. Refusing to format.",
            file=sys.stderr,
        )
        return True
    if count > 1:
        print(
            f"mdformat: {count} front-matter parser extensions are "
            "installed in the environment that will run mdformat. They "
            "register under different entry-point names, so pip installs "
            "both without complaint, and mdformat resolves the conflict "
            "silently apart from a log line. One of them strips quotes, "
            'which turns a quoted "yes" into a YAML 1.1 boolean. Keep '
            "exactly one (crackerjack declares mdformat-frontmatter) and "
            "retry.",
            file=sys.stderr,
        )
        return True
    return False


def _report_excluded_documents(all_files: list[Path]) -> None:
    """Report the documents that are excluded from formatting.

    An excluded document is one nobody notices: the operator sees a
    file that is never formatted and has no idea why. Both exclusions
    below are reported by name.
    """
    bom_docs = _bom_frontmatter_documents(all_files)
    if bom_docs:
        _report_tool_output(
            f"{len(bom_docs)} document(s) open with a byte-order mark before "
            "their frontmatter fence and are excluded from formatting: the "
            "front-matter plugin is BOM-blind, so formatting them would "
            "flatten their frontmatter into a heading and drop them out of "
            "the plan index. Remove the byte-order mark to have them "
            "formatted."
        )
        for path in bom_docs:
            _report_tool_output(f"excluded (byte-order mark): {path}")

    yaml_docs = _multi_document_yaml_documents(all_files)
    if yaml_docs:
        _report_tool_output(
            f"{len(yaml_docs)} document(s) are streams of YAML documents "
            "rather than markdown, and are excluded from formatting: "
            "mdformat reads the prose line before each '---' separator as "
            "a settext heading underline and turns every separator into an "
            "ATX heading, which destroys the file rather than formatting "
            "it. Rename them to a .yaml extension to have them covered."
        )
        for path in yaml_docs:
            _report_tool_output(f"excluded (multi-document YAML): {path}")


def _report_format_outcome(
    changed: list[Path],
    refused: list[Path],
    damaged: list[Path],
) -> int:
    """Report what the format run did, and return the hook's exit code.

    A run that changed a file exits 1. The hook is marked as a
    formatter, and the executor reads an exit-1 formatter as "it
    rewrote something" rather than as a failure.
    """
    if refused:
        _report_tool_output(
            f"{len(refused)} document(s) could not be formatted by mdformat "
            "and are left as they are: mdformat refuses a document whose "
            "formatted output renders to different HTML than the input, "
            "and it aborts the whole batch at the first refusal. These "
            "documents are reported so they are not mistaken for "
            "formatted."
        )
        for path in refused:
            _report_tool_output(f"not formatted (mdformat refused): {path}")

    if damaged:
        _report_tool_output(
            f"{len(damaged)} document(s) were changed by mdformat in a way "
            "that alters how they read, and have been restored: mdformat "
            "has no GFM table support, so it can merge a table's rows or "
            "re-indent a table out of its list item without noticing. "
            "They are left as they were."
        )
        for path in damaged:
            _report_tool_output(f"restored (rendering changed): {path}")

    if changed:
        _report_auto_formatted(changed)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    md_files = get_git_tracked_files("*.md")
    markdown_files = get_git_tracked_files("*.markdown")
    all_files = md_files + markdown_files

    if _frontmatter_environment_is_unsafe(all_files):
        return 1

    _report_excluded_documents(all_files)

    files = [f for f in all_files if not should_skip_file(f)]

    if not files:
        print("No git-tracked markdown files found", file=sys.stderr)
        return 0

    cmd = _build_mdformat_cmd(files, argv)

    try:
        check_cmd = [*cmd, "--check"]
        check_result = subprocess.run(
            check_cmd,
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )

        if check_result.returncode == 0:
            # mdformat writes its own diagnostics to stderr -- a
            # front-matter block it could not parse, a plugin conflict
            # -- and the clean path used to discard them, so those
            # warnings were invisible. Surface them now. They are
            # informational: mdformat exited 0, so the format succeeded.
            _report_tool_output(check_result.stderr)
            return 0

        changed, refused, damaged = _format_with_rollback(files, argv)
        return _report_format_outcome(changed, refused, damaged)
    except FileNotFoundError:
        return 127
    except Exception as e:
        print(f"Error running mdformat: {e}", file=sys.stderr)
        return 1


def _format_with_rollback(
    files: list[Path],
    argv: list[str] | None,
) -> tuple[list[Path], list[Path], list[Path]]:
    """Format the files, rolling back anything mdformat damages.

    mdformat has two behaviours that make a plain format run unsafe on
    a fleet-wide tree:

    **It aborts the whole batch at the first file it cannot format.**
    A document whose formatted output renders to different HTML than
    the input is refused, and the refusal stops every file after it in
    the same invocation. The tree is left half-formatted and the
    formatter reports the same failure on every subsequent run, so the
    gate never converges. The batch is therefore run iteratively: the
    refused file is named in mdformat's own error message, dropped from
    the set, and the batch re-run.

    **Its safety check cannot see table damage.** The check compares
    the rendering produced by mdformat's parser, which has no GFM table
    support. So mdformat can merge a table's rows, or re-indent a table
    out of its list item, and pass its own check. Each file's GFM
    rendering is compared before and after; a file that reads
    differently is restored to its original bytes and reported.

    Returns the files that were changed, the files mdformat refused,
    and the files whose damage was rolled back.
    """
    snapshot: dict[Path, str] = {}
    for path in files:
        try:
            snapshot[path] = path.read_text(encoding="utf-8")
        except OSError, UnicodeDecodeError:
            snapshot[path] = ""

    pending = files.copy()
    refused: list[Path] = []
    while pending:
        result = subprocess.run(
            _build_mdformat_cmd(pending, argv),
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            if result.stderr:
                _report_tool_output(result.stderr)
            break

        culprit = _refused_file(result.stderr, pending)
        if culprit is None:
            # Not a file-level refusal -- a real failure. Surface it
            # and stop rather than looping on it.
            print(result.stderr, file=sys.stderr)
            return [], refused, []
        refused.append(culprit)
        pending.remove(culprit)

    changed: list[Path] = []
    damaged: list[Path] = []
    for path in pending:
        try:
            after = path.read_text(encoding="utf-8")
        except OSError, UnicodeDecodeError:
            continue
        before = snapshot.get(path, "")
        if after == before:
            continue
        if _rendering_changes(before, after):
            # mdformat changed what the document says. Put it back.
            with suppress(OSError):
                path.write_text(before, encoding="utf-8")
            damaged.append(path)
            continue
        changed.append(path)

    return changed, refused, damaged


def _refused_file(stderr: str, candidates: list[Path]) -> Path | None:
    """The file mdformat refused, named in its error message.

    mdformat reports::

        Error: Could not format
        "/path/to/doc.md".

    The path is matched against the candidates by resolved path, so a
    relative path on the command line and an absolute path in the
    message both resolve to the same file.
    """
    match = _COULD_NOT_FORMAT.search(stderr)
    if match is None:
        return None
    reported = Path(match.group("path"))
    try:
        resolved = reported.resolve()
    except OSError:
        resolved = reported
    for candidate in candidates:
        try:
            if candidate.resolve() == resolved:
                return candidate
        except OSError:
            if candidate == reported:
                return candidate
    return None


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
