"""Unit tests for the archive lifecycle gate in ``DocumentationCategorizer``.

The gate is the tool-side enforcement of the archive policy that the
Bodai repos encode in their decisions stores: a lifecycle-governed
document may only be auto-archived once it declares ``status: shipped``.
A mechanical sweep must not be the thing that decides a governed
document's fate.

See ``docs/plans/2026-11-15-archive-lifecycle-gate.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.services.doc_categorizer import DocumentationCategorizer

pytestmark = pytest.mark.unit


# A filename that the categorizer's ``implementation_reports`` category
# matches (``.*-implementation\.md``). Every fixture uses it so that the
# only thing under test is the lifecycle gate, not the name heuristic.
IMPLEMENTATION_NAME = "2026-10-19-example-implementation.md"


def _write(root: Path, name: str, body: str) -> Path:
    """Write ``body`` to ``root/name`` and return the path."""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


@pytest.fixture
def docs_root(tmp_path: Path) -> Path:
    """A throwaway repository root."""
    return tmp_path


class TestLifecyclePredicate:
    """``lifecycle_permits_archival`` is the gate."""

    def test_complete_status_is_not_archived(self, docs_root: Path) -> None:
        """A ``complete`` document is still live — the sweep must skip it.

        This is the exact shape that lost the two OTel substrate plans in
        mahavishnu three times.
        """
        _write(
            docs_root,
            IMPLEMENTATION_NAME,
            "---\nstatus: complete\nrole: implementation\n---\n\n# Plan\n",
        )

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is False

    @pytest.mark.parametrize("status", ["draft", "active", "partial", "complete"])
    def test_non_archivable_statuses_are_not_archived(
        self, docs_root: Path, status: str
    ) -> None:
        """Every lifecycle value other than ``shipped`` blocks archival."""
        _write(
            docs_root,
            IMPLEMENTATION_NAME,
            f"---\nstatus: {status}\nrole: implementation\n---\n\n# Doc\n",
        )

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is False

    def test_shipped_status_is_archived(self, docs_root: Path) -> None:
        """``shipped`` means closed — the document may be archived."""
        _write(
            docs_root,
            IMPLEMENTATION_NAME,
            "---\nstatus: shipped\nrole: implementation\n---\n\n# Doc\n",
        )

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is True

    def test_file_without_frontmatter_is_still_archived(self, docs_root: Path) -> None:
        """Scratch artifacts carry no lifecycle — cleanup keeps working."""
        _write(docs_root, IMPLEMENTATION_NAME, "# Progress notes\n")

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is True

    def test_unparsable_frontmatter_is_not_archived(self, docs_root: Path) -> None:
        """A broken ``---`` block means unknown lifecycle — fail closed."""
        _write(
            docs_root,
            IMPLEMENTATION_NAME,
            "---\nstatus: `unquoted backtick\nrole: implementation\n---\n\n# Doc\n",
        )

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is False

    def test_frontmatter_without_status_is_not_archived(self, docs_root: Path) -> None:
        """Frontmatter that declares no lifecycle — fail closed."""
        _write(
            docs_root,
            IMPLEMENTATION_NAME,
            "---\ntitle: A report\n---\n\n# Report\n",
        )

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is False

    def test_empty_frontmatter_is_not_archived(self, docs_root: Path) -> None:
        """An empty ``---`` block declares no lifecycle — fail closed."""
        _write(docs_root, IMPLEMENTATION_NAME, "---\n---\n\n# Doc\n")

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is False

    def test_leading_fence_without_readable_status_is_not_archived(
        self, docs_root: Path
    ) -> None:
        """A file opening with ``---`` declares frontmatter — fail closed.

        The extractor only reports a block when its regex matches, so an
        empty or otherwise unreadable block reads as "no frontmatter".
        A leading fence is treated as a declaration, matching the
        convention ``crackerjack.tools.mdformat_wrapper`` already uses.
        """
        _write(docs_root, IMPLEMENTATION_NAME, "---\nProse, not frontmatter.\n")

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is False

    @pytest.mark.parametrize("status", ["", "null", "123", "[]"])
    def test_a_status_that_is_not_a_usable_string_is_not_archived(
        self, docs_root: Path, status: str
    ) -> None:
        """An empty, null, numeric, or list ``status:`` blocks archival.

        Only a string can name a lifecycle, and only a non-empty one can
        match the archivable set — so anything else is an unknown
        lifecycle and fails closed.
        """
        _write(
            docs_root,
            IMPLEMENTATION_NAME,
            f"---\nstatus: {status}\nrole: implementation\n---\n\n# Doc\n",
        )

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is False

    def test_unreadable_file_is_not_archived(self, docs_root: Path) -> None:
        """A file that cannot be decoded is left alone, not swept."""
        path = docs_root / IMPLEMENTATION_NAME
        path.write_bytes(b"---\nstatus: \xff\xfe shipped\n---\n")

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is False

    def test_bom_prefixed_frontmatter_is_not_archived(self, docs_root: Path) -> None:
        """A UTF-8 BOM must not make a governed document look ungoverned.

        The BOM is an encoding artifact. Left in place it makes the
        anchored frontmatter regex miss the block, and a missed
        frontmatter reads as "not governed" — the one direction that must
        never happen.
        """
        _write(
            docs_root,
            IMPLEMENTATION_NAME,
            "\ufeff---\nstatus: draft\nrole: implementation\n---\n\n# Doc\n",
        )

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is False

    def test_bom_prefixed_shipped_document_is_archived(self, docs_root: Path) -> None:
        """A BOM must not over-block either — ``shipped`` still archives.

        The counterpart to the fail-closed case above: a BOM regression
        that blocked every document would look exactly like a working
        gate, so the permissive direction needs its own pin.
        """
        _write(
            docs_root,
            IMPLEMENTATION_NAME,
            "\ufeff---\nstatus: shipped\nrole: implementation\n---\n\n# Doc\n",
        )

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is True

    def test_whitespace_before_bom_is_not_archived(self, docs_root: Path) -> None:
        """Whitespace before the BOM must not hide the frontmatter either.

        The two artefacts combine: the extractor's regex is anchored, so
        a leading space makes it miss the block, and a BOM stripped
        before the whitespace would expose the BOM rather than remove
        it. Either way the document must still be recognised as
        governed.
        """
        _write(
            docs_root,
            IMPLEMENTATION_NAME,
            " \ufeff---\nstatus: draft\nrole: implementation\n---\n\n# Doc\n",
        )

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is False

    def test_leading_blank_line_before_frontmatter_is_not_archived(
        self, docs_root: Path
    ) -> None:
        """Leading blank lines must not make a governed document look ungoverned."""
        _write(
            docs_root,
            IMPLEMENTATION_NAME,
            "\n---\nstatus: draft\nrole: implementation\n---\n\n# Doc\n",
        )

        categorizer = DocumentationCategorizer(docs_root)
        path = docs_root / IMPLEMENTATION_NAME

        assert categorizer.lifecycle_permits_archival(path) is False


class TestArchivalCandidates:
    """Candidate detection is separate from the lifecycle gate.

    ``get_archival_candidates`` answers "does this name look
    archivable?"; the gate answers "may this document actually be
    archived?". The gate is applied by
    ``DocumentationCleanup._detect_archivable_files`` — the single place
    it is applied — so no detection path can bypass it.
    """

    def test_candidate_detection_ignores_the_lifecycle(self, docs_root: Path) -> None:
        """A governed document is still a *candidate*; the gate rejects it."""
        _write(
            docs_root,
            IMPLEMENTATION_NAME,
            "---\nstatus: complete\nrole: implementation\n---\n\n# Plan\n",
        )

        candidates = DocumentationCategorizer(docs_root).get_archival_candidates()

        assert IMPLEMENTATION_NAME in {p.name for p in candidates}

    def test_keep_categories_are_not_candidates(self, docs_root: Path) -> None:
        """``keep_in_root`` and ``keep_in_docs`` are excluded by name."""
        _write(docs_root, "README.md", "# Readme\n")
        _write(docs_root, "CLAUDE_GUIDE.md", "# Guide\n")

        candidates = DocumentationCategorizer(docs_root).get_archival_candidates()

        assert not {p.name for p in candidates} & {"README.md", "CLAUDE_GUIDE.md"}


class TestConfigurableArchivableStatuses:
    """A repo with a different vocabulary widens the list in settings."""

    def test_custom_status_set_is_honoured(self, docs_root: Path) -> None:
        path = _write(docs_root, "a.md", "---\nstatus: archived\n---\n\n# Doc\n")
        categorizer = DocumentationCategorizer(
            docs_root, archivable_statuses={"archived"}
        )

        assert categorizer.lifecycle_permits_archival(path) is True

    def test_shipped_is_not_archivable_when_overridden(self, docs_root: Path) -> None:
        path = _write(docs_root, "a.md", "---\nstatus: shipped\n---\n\n# Doc\n")
        categorizer = DocumentationCategorizer(
            docs_root, archivable_statuses={"archived"}
        )

        assert categorizer.lifecycle_permits_archival(path) is False

    def test_a_bare_string_is_one_status_not_characters(self, docs_root: Path) -> None:
        """``archivable_statuses="shipped"`` must not iterate characters."""
        path = _write(docs_root, "a.md", "---\nstatus: shipped\n---\n\n# Doc\n")
        categorizer = DocumentationCategorizer(
            docs_root,
            archivable_statuses="shipped",
        )

        assert categorizer.archivable_statuses == frozenset({"shipped"})
        assert categorizer.lifecycle_permits_archival(path) is True

    def test_default_status_set_is_shipped_only(self, docs_root: Path) -> None:
        categorizer = DocumentationCategorizer(docs_root)

        assert categorizer.archivable_statuses == frozenset({"shipped"})

    def test_default_status_set_comes_from_the_shared_source(
        self, docs_root: Path
    ) -> None:
        """The tool default and the settings default must not drift."""
        from crackerjack.config.settings import DocumentationSettings
        from crackerjack.core.lifecycle import ARCHIVABLE_STATUSES

        categorizer = DocumentationCategorizer(docs_root)

        assert categorizer.archivable_statuses == ARCHIVABLE_STATUSES
        assert DocumentationSettings().archivable_statuses == sorted(
            ARCHIVABLE_STATUSES
        )

    @pytest.mark.parametrize("configured", ["Shipped", " shipped ", "SHIPPED"])
    def test_configured_statuses_are_normalized(
        self, docs_root: Path, configured: str
    ) -> None:
        """A configuration written in any case still matches.

        The document's status is lower-cased before the comparison, so the
        configured set has to be normalised the same way — otherwise
        ``archivable_statuses: ["Shipped"]`` silently archives nothing.
        """
        path = _write(docs_root, "a.md", "---\nstatus: shipped\n---\n\n# Doc\n")
        categorizer = DocumentationCategorizer(
            docs_root, archivable_statuses={configured}
        )

        assert categorizer.archivable_statuses == frozenset({"shipped"})
        assert categorizer.lifecycle_permits_archival(path) is True


class TestArchiveTargetPath:
    """``archive_target_path`` composes the destination and resolves clashes."""

    def test_a_collision_gets_a_numeric_suffix(self, docs_root: Path) -> None:
        """An existing destination is not overwritten.

        The suffix keeps both copies, so a second sweep of the same
        name cannot silently replace the first archive entry.
        """
        categorizer = DocumentationCategorizer(docs_root)
        source = docs_root / "docs" / "plans" / IMPLEMENTATION_NAME
        _write(docs_root, source.relative_to(docs_root).as_posix(), "x\n")

        first = categorizer.archive_target_path(source, "implementation-reports")
        first.parent.mkdir(parents=True, exist_ok=True)
        first.write_text("first\n", encoding="utf-8")

        second = categorizer.archive_target_path(source, "implementation-reports")

        assert second != first
        assert second.name == f"{IMPLEMENTATION_NAME[:-3]}__001.md"
        assert first.read_text(encoding="utf-8") == "first\n"


class TestFrontmatterContract:
    """The gate relies on the extractor's contract; pin it."""

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param("---\njust a string\n---\n\nbody\n", id="scalar"),
            pytest.param("---\n- one\n- two\n---\n\nbody\n", id="list"),
        ],
    )
    def test_frontmatter_that_is_not_a_mapping_fails_closed(
        self,
        docs_root: Path,
        body: str,
    ) -> None:
        """A frontmatter block that is not a mapping is an unknown lifecycle.

        ``extract_frontmatter`` rejects it before returning, so the gate
        sees a parse error rather than a value it would have to call
        ``.get()`` on. The document stays put.
        """
        categorizer = DocumentationCategorizer(docs_root)
        path = _write(docs_root, IMPLEMENTATION_NAME, body)

        assert categorizer.lifecycle_permits_archival(path) is False

    def test_a_non_mapping_from_the_extractor_fails_closed(
        self,
        docs_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The gate checks the extractor's contract rather than trusting it.

        ``extract_frontmatter`` rejects a non-mapping before it returns,
        so this cannot happen today. The gate reads arbitrary files, and
        one malformed document must not abort the whole cleanup with an
        ``AttributeError`` -- so the gate checks for itself.
        """
        import crackerjack.services.doc_categorizer as module

        monkeypatch.setattr(
            module,
            "extract_frontmatter",
            lambda text: ("not a mapping", None, 0),
        )

        categorizer = DocumentationCategorizer(docs_root)
        path = _write(
            docs_root,
            IMPLEMENTATION_NAME,
            "---\nstatus: shipped\n---\n\nbody\n",
        )

        assert categorizer.lifecycle_permits_archival(path) is False
