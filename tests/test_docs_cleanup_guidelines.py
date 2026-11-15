"""Pin the cleanup guidelines' examples to the categorizer's real routing.

The guidelines are the operator-facing contract for the documentation
cleanup. Their examples are hand-written prose, and hand-written prose
drifts: a category is renamed, a pattern is widened, and the examples
quietly start describing destinations the code cannot produce.

This module parses the examples out of the guidelines and checks each one
against ``DocumentationCategorizer.categorize_file()`` — the same function
the cleanup calls. It fails loudly, which is the point: a reader who trusts
an example should be able to trust it.

"Loudly" is the whole design constraint. A parser that silently skips a
claim it does not recognise is worse than no parser at all: it reports an
agreement it never checked. So three things are pinned here:

- every list item in the Examples section must parse, and must carry a
  backtick span (a list item with no span is an error, not a skip);
- every filename mentioned in a backtick span anywhere in the section — in
  a bullet, a table row, or a prose sentence — must be one the parser
  actually checked;
- every checked filename must agree with the categorizer's verdict.

The scope is backticked spans, and the scope is stated here because it is
the limit of what this module reads: a filename or a category written in
plain prose, without backticks, is not a claim this checker can see.
That is a deliberate line — the guidelines write paths and names as code
spans, and a module that guessed at prose would produce false failures
as readily as it would find real ones.

The set of extensions that count as "a filename" is read from the
categorizer's own candidate globs rather than kept as a second copy here:
a list the sweep does not honour would make the completeness guard
circular.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from crackerjack.config.settings import CrackerjackSettings
from crackerjack.services.doc_categorizer import DocumentationCategorizer
from crackerjack.services.documentation_cleanup import DocumentationCleanup

GUIDELINES = (
    Path(__file__).resolve().parent.parent / "docs" / "DOCS_CLEANUP_GUIDELINES.md"
)

_EXAMPLES_HEADING = "## Examples"
_HEADING = re.compile(r"^#+\s*(.*)$", re.MULTILINE)

#: A list item in any of the shapes markdown allows: ``-``, ``*``, ``+``,
#: ``1.``, ``1)``, at any indentation. The detection is deliberately
#: generous — a list item written in a shape this module does not
#: recognise must be *counted* (and so fail the completeness guard)
#: rather than skipped.
_BULLET_LINE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
_BACKTICK_SPAN = re.compile(r"`([^`]+)`")

#: The archive areas the categorizer can compose a destination under. A
#: claim may also use the ``<area>`` placeholder, since a bare filename
#: example does not pin the area it came from.
_ARCHIVE_AREAS = frozenset(
    {"<area>", "docs", "docs/plans", "docs/specs", "docs/decisions"}
)

#: The two plans the archive sweep lost three times. They are named here
#: so that a future pattern change which re-arms the incident trips a test
#: rather than the next publish.
INCIDENT_PLANS = (
    "2026-10-19-bodai-substrate-otel-v7-implementation.md",
    "2026-10-20-bodai-otel-substrate-read-path-implementation.md",
)

#: A name that carries ``.md`` without ending in it. ``re.match`` anchors
#: at the start of the name, so the ``analysis`` category's ``TEST_.*\.md``
#: pattern classifies this as an analysis document — which makes the
#: gate's name-based test a live path rather than a hypothetical one.
MARKDOWN_COPY = "TEST_foo.md.backup"


def _examples_section(text: str) -> str:
    """Return the Examples section of the guidelines."""
    start = text.index(_EXAMPLES_HEADING)
    end = text.index("\n## ", start + 1)
    return text[start:end]


def _claimed_bullets(section: str) -> list[tuple[str, list[str]]]:
    """Return ``(heading, spans)`` for every list item in a section.

    A list item that carries no backtick span is an error rather than
    something to skip — an unparsed claim means an unchecked claim.
    """
    bullets: list[tuple[str, list[str]]] = []
    heading = ""
    for line in section.splitlines():
        heading_match = _HEADING.match(line)
        if heading_match:
            heading = heading_match.group(1).strip()
            continue
        bullet = _BULLET_LINE.match(line)
        if not bullet:
            continue
        spans = _BACKTICK_SPAN.findall(bullet.group(1))
        if not spans:
            raise AssertionError(
                f"list item under {heading!r} carries no backtick span, so it "
                f"cannot be checked: {line!r}"
            )
        bullets.append((heading, spans))
    return bullets


def _destination_claims(section: str) -> list[str]:
    """Return every destination claim in the section, wherever it appears.

    A destination is a ``<area>/.archive/<category>/<name>`` span. It is
    collected from the whole section rather than from list items alone,
    so a destination written in a table row or a prose sentence is
    checked too.
    """
    return [span for span in _BACKTICK_SPAN.findall(section) if ".archive/" in span]


def _basename_of(span: str) -> str:
    """Return the filename a span refers to.

    A span may be a bare filename, a path to one, or an archive
    destination that ends in one. All three name a file, so all three are
    reduced to the basename.
    """
    return span.rsplit("/", 1)[-1]


def _looks_like_a_file(name: str) -> bool:
    """Return whether a name could be a filename at all.

    The *routing* checks use this rather than "the categorizer routes
    it": a claim about a file the categorizer no longer routes is
    itself the drift worth reporting, so those checks must not skip it.
    """
    return "." in name and " " not in name


def _is_routing_claim(categorizer: DocumentationCategorizer, name: str) -> bool:
    """Return whether the cleanup routes a file with this name.

    The question is asked of the categorizer rather than answered from
    a list of extensions kept here: the checker covers exactly the
    files the sweep can touch, and a mention of something the cleanup
    never routes — a ``.yaml``, a name matching no category — is not a
    routing claim at all.
    """
    return categorizer.categorize_file(Path(name)).category is not None


def _mentioned_filenames(
    section: str,
    categorizer: DocumentationCategorizer,
) -> set[str]:
    """Return every routable filename mentioned anywhere in the section."""
    mentioned: set[str] = set()
    for span in _BACKTICK_SPAN.findall(section):
        name = _basename_of(span)
        if name and _is_routing_claim(categorizer, name):
            mentioned.add(name)
    return mentioned


def test_the_examples_section_exists() -> None:
    assert GUIDELINES.is_file(), f"missing {GUIDELINES}"
    text = GUIDELINES.read_text(encoding="utf-8")
    assert _EXAMPLES_HEADING in text, "the guidelines lost their Examples section"


def test_every_mentioned_filename_is_actually_checked() -> None:
    """No claim may slip past the checker, whatever shape it is written in.

    A filename mentioned in a table row or a prose sentence counts, as
    long as it is in a backtick span — which is how the guidelines write
    every path and name. If the parser does not check it, the test fails —
    so a new shape of example cannot be added without the checker learning
    to read it.
    """
    section = _examples_section(GUIDELINES.read_text(encoding="utf-8"))
    bullets = _claimed_bullets(section)
    categorizer = DocumentationCategorizer(Path("/tmp"))

    checked: set[str] = set()
    for _heading, spans in bullets:
        for span in spans:
            name = _basename_of(span)
            if name:
                checked.add(name)
    for destination in _destination_claims(section):
        name = _basename_of(destination)
        if name:
            checked.add(name)

    mentioned = _mentioned_filenames(section, categorizer)
    unchecked = mentioned - checked
    assert not unchecked, (
        "these filenames are mentioned in the Examples section but never "
        f"checked: {sorted(unchecked)}"
    )


def test_every_destination_claim_matches_the_categorizer() -> None:
    """Every destination claim is checked against its own category.

    Each claim is compared on its own, so two destinations in one bullet
    cannot let the second stand in for the first — and a destination
    written outside a list item is checked too.
    """
    section = _examples_section(GUIDELINES.read_text(encoding="utf-8"))
    categorizer = DocumentationCategorizer(Path("/tmp"))
    mismatches: list[str] = []

    for destination in _destination_claims(section):
        area, _, remainder = destination.partition(".archive/")
        area = area.rstrip("/")
        category, _, name = remainder.partition("/")
        result = categorizer.categorize_file(Path(name))
        if result.destination != category:
            mismatches.append(
                f"{name}: the guidelines say .archive/{category}/ "
                f"but the code routes it to {result.destination!r}"
            )
        if area not in _ARCHIVE_AREAS:
            mismatches.append(
                f"{destination}: the guidelines claim the archive area "
                f"{area!r}, which the categorizer never produces"
            )

    assert not mismatches, "guidelines contradict the code:\n" + "\n".join(mismatches)


def test_every_prose_category_claim_matches_the_categorizer() -> None:
    """A category claimed in prose is checked against the code.

    A destination written as a path is checked wherever it appears. A
    category named in words — "`X.md` goes to summaries" — is a claim
    too, and it is checked on the line it is made: the file it names
    must actually route to that category.
    """
    section = _examples_section(GUIDELINES.read_text(encoding="utf-8"))
    categorizer = DocumentationCategorizer(Path("/tmp"))

    # A category can be named by the destination it routes to
    # ("summaries") or by its internal key ("completion_reports"); both
    # mean the same place, and a claim in either form is a claim.
    category_names: dict[str, str] = {}
    for key, config in categorizer.CATEGORIES.items():
        destination = config["destination"]
        if destination:
            category_names[destination] = destination
            category_names[key] = destination

    mismatches: list[str] = []

    for line in section.splitlines():
        spans = _BACKTICK_SPAN.findall(line)
        claimed = {category_names[span] for span in spans if span in category_names}
        if not claimed:
            continue
        for span in spans:
            name = _basename_of(span)
            if not name or not _looks_like_a_file(name):
                continue
            result = categorizer.categorize_file(Path(name))
            if result.category in {"keep_in_root", "keep_in_docs"}:
                # A file that stays put, named beside a category: the
                # category is the archive half of the claim, this is the
                # keep half. Nothing to compare.
                continue
            actual = result.destination
            # A line may name more than one category; the file has to
            # route to one of them, not to all of them.
            if actual not in claimed:
                mismatches.append(
                    f"{name}: the guidelines say it goes to {sorted(claimed)} "
                    f"but the code routes it to {actual!r}"
                )

    assert not mismatches, "guidelines contradict the code:\n" + "\n".join(mismatches)


def test_every_example_matches_the_categorizers_verdict() -> None:
    """Each example must describe the destination the code actually produces.

    The destination claims are checked by
    :func:`test_every_destination_claim_matches_the_categorizer`. What
    remains here is the context a destination cannot carry: whether the
    files a list item names are files that *stay put*.
    """
    text = GUIDELINES.read_text(encoding="utf-8")
    bullets = _claimed_bullets(_examples_section(text))
    assert bullets, "the Examples section parsed to zero list items"

    categorizer = DocumentationCategorizer(Path("/tmp"))
    mismatches: list[str] = []

    for heading, spans in bullets:
        categories = {
            category
            for span in spans
            if ".archive/" in span
            for category in (span.partition(".archive/")[2].partition("/")[0],)
        }

        for span in spans:
            if ".archive/" in span:
                # Its category claim is checked above.
                continue
            name = _basename_of(span)
            if not name or not _looks_like_a_file(name):
                continue
            result = categorizer.categorize_file(Path(name))
            actual = result.destination

            if result.category in {"keep_in_root", "keep_in_docs"}:
                # A file that stays put, named in the same bullet as a
                # destination: the destination is the archive half of the
                # claim, this is the keep half. Nothing to compare.
                continue

            if categories:
                # A bare name alongside one or more destinations must
                # match one of the categories the bullet claims.
                if actual not in categories:
                    mismatches.append(
                        f"{name}: the guidelines claim a destination of "
                        f"{sorted(categories)} but the code routes it to "
                        f"{actual!r}"
                    )
            elif result.category not in {"keep_in_root", "keep_in_docs"}:
                mismatches.append(
                    f"{name}: the guidelines list it under {heading!r} "
                    f"but the code classifies it as {result.category!r}"
                )

    assert not mismatches, "guidelines contradict the code:\n" + "\n".join(mismatches)


@pytest.mark.parametrize("plan_name", INCIDENT_PLANS)
def test_the_incident_plans_are_categorised_as_implementation_reports(
    plan_name: str,
) -> None:
    """The names that triggered the incident must keep their category.

    The gate protects these documents regardless of category, but the
    category is what made them candidates in the first place. If a
    pattern change moves them out of ``implementation_reports``, the sweep
    would stop proposing them — worth knowing, loudly.
    """
    categorizer = DocumentationCategorizer(Path("/tmp"))
    result = categorizer.categorize_file(Path(plan_name))
    assert result.category == "implementation_reports"
    assert result.destination == "implementation-reports"


def test_a_markdown_copy_is_still_classified() -> None:
    """The gate's name-based test is a live path, not a hypothetical one.

    ``re.match`` anchors at the *start* of the name, so a pattern that is
    not end-anchored matches a prefix. The ``analysis`` category's
    ``TEST_.*\\.md`` pattern therefore classifies ``TEST_foo.md.backup``
    as an analysis document even though the name does not end in ``.md``
    — and the ``*.backup`` glob proposes it as a candidate.
    """
    categorizer = DocumentationCategorizer(Path("/tmp"))
    result = categorizer.categorize_file(Path(MARKDOWN_COPY))
    assert result.category == "analysis"
    assert result.destination == "analysis"


def test_a_markdown_copy_is_gated_by_the_name_test(tmp_path: Path) -> None:
    """A copy whose name carries ``.md`` is gated like the document it copies.

    A suffix test would have swept this copy of a governed document
    ungated. The name test is what stops that.
    """
    copy = tmp_path / MARKDOWN_COPY
    copy.write_text("---\nstatus: draft\n---\n\nstill open\n", encoding="utf-8")

    settings = CrackerjackSettings()
    cleanup = DocumentationCleanup(pkg_path=tmp_path, settings=settings)

    assert cleanup._passes_lifecycle_gate(copy) is False
