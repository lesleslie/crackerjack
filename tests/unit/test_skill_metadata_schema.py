"""B-4 path-traversal rejection tests for SkillMetadata.

Per plan §5 task #4 and §11 B-4, ``name`` and ``server`` fields are
constrained to a strict allowlist that prevents path-traversal attacks
via server-supplied metadata. The unit test asserts the validator
rejects every forbidden shape AND accepts the happy-path shape.

This test does NOT spin up the MCP server — it exercises the Pydantic
model directly so it can run without the full lifespan state.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from crackerjack.mcp.skill_schema import SkillMetadata


def _valid_kwargs(**overrides: object) -> dict[str, object]:
    """Return valid kwargs with sensible defaults; pass ``overrides`` to mutate."""
    defaults: dict[str, object] = {
        "schema_version": 1,
        "id": "akosha:search-insights:1.0.0",
        "server": "akosha",
        "name": "search-insights",
        "description": "Test description",
        "version": "1.0.0",
        "tool_refs": ["mcp__akosha__akosha_search_all_systems"],
        "dependencies": [],
        "content_type": "skill",
        "content_hash": "0" * 64,
        "body_size": 1024,
        "body_format": "yaml-frontmatter+markdown",
        "allowed_tools": ["mcp__akosha__akosha_search_all_systems"],
        "signature": None,
        "server_pubkey_id": None,
        "timestamp": datetime.now(UTC).timestamp(),
    }
    defaults.update(overrides)
    return defaults


class TestAllowlistHappyPath:
    """Valid identifiers parse without raising."""

    def test_lowercase_with_dash(self) -> None:
        m = SkillMetadata(**_valid_kwargs(name="search-insights"))
        assert m.name == "search-insights"

    def test_lowercase_with_dot(self) -> None:
        m = SkillMetadata(**_valid_kwargs(name="v1.2.3"))
        assert m.name == "v1.2.3"

    def test_lowercase_with_underscore(self) -> None:
        m = SkillMetadata(**_valid_kwargs(name="foo_bar"))
        assert m.name == "foo_bar"

    def test_single_char(self) -> None:
        """Length 1 is the minimum the regex allows."""
        m = SkillMetadata(**_valid_kwargs(name="a"))
        assert m.name == "a"

    def test_max_length_63(self) -> None:
        """Length 63 is the maximum the regex allows."""
        m = SkillMetadata(**_valid_kwargs(name="a" + "b" * 62))
        assert len(m.name) == 63


class TestNameAllowlistRejection:
    """B-4: forbidden name shapes must raise ValidationError."""

    def test_empty_string(self) -> None:
        with pytest.raises(ValidationError, match="allowlist"):
            SkillMetadata(**_valid_kwargs(name=""))

    def test_max_length_64(self) -> None:
        """64 chars exceeds the {0,62} limit."""
        with pytest.raises(ValidationError, match="allowlist"):
            SkillMetadata(**_valid_kwargs(name="a" * 64))

    @pytest.mark.parametrize(
        "bad_name",
        [
            "../../foo",  # path traversal: parent dirs
            "foo/bar",  # slash anywhere
            ".hidden",  # leading dot
            "FOO",  # uppercase
            "Foo",  # mixed case
            "foo bar",  # whitespace
            "foo!",  # punctuation
            "foo$bar",  # shell metacharacter
            "foo|bar",  # pipe
            "foo;bar",  # semicolon
            "foo&bar",  # ampersand
            "foo`bar`",  # backtick
            "foo\nbar",  # newline
            "foo\rbar",  # carriage return
            "foo\tbar",  # tab
        ],
    )
    def test_forbidden_characters(self, bad_name: str) -> None:
        """B-4 negative cases: every forbidden character class rejected."""
        with pytest.raises(ValidationError, match="allowlist"):
            SkillMetadata(**_valid_kwargs(name=bad_name))

    def test_double_dot_substring_rejected(self) -> None:
        """Defense-in-depth: ``..`` is forbidden even mid-string.

        The regex ``^[a-z0-9][a-z0-9._-]{0,62}$`` does not forbid ``..``
        in the middle of a string (e.g. ``a..b``). The brief requires
        forbidding ``..`` explicitly as defense-in-depth.
        """
        with pytest.raises(ValidationError, match=r"\.\."):
            SkillMetadata(**_valid_kwargs(name="a..b"))


class TestServerAllowlistRejection:
    """B-4 applies to BOTH ``name`` and ``server`` (a forged ``server``
    value could trick a client into path-traversal too)."""

    def test_server_with_slash_rejected(self) -> None:
        with pytest.raises(ValidationError, match="allowlist"):
            SkillMetadata(**_valid_kwargs(server="akosha/../etc"))

    def test_server_uppercase_rejected(self) -> None:
        with pytest.raises(ValidationError, match="allowlist"):
            SkillMetadata(**_valid_kwargs(server="AkoSHA"))

    def test_server_double_dot_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"\.\."):
            SkillMetadata(**_valid_kwargs(server="ak..osha"))


class TestIdShapeValidation:
    """``id`` must be ``{server}:{name}:{version}`` with three parts."""

    def test_id_with_two_parts_rejected(self) -> None:
        with pytest.raises(ValidationError, match="server:name:version"):
            SkillMetadata(**_valid_kwargs(id="akosha:search-insights"))

    def test_id_with_four_parts_rejected(self) -> None:
        with pytest.raises(ValidationError, match="server:name:version"):
            SkillMetadata(
                **_valid_kwargs(id="akosha:search-insights:1.0.0:extra"),
            )

    def test_id_with_invalid_server_segment_rejected(self) -> None:
        with pytest.raises(ValidationError, match="invalid server segment"):
            SkillMetadata(
                **_valid_kwargs(id="AKOSHA:search-insights:1.0.0"),
            )

    def test_id_with_invalid_name_segment_rejected(self) -> None:
        with pytest.raises(ValidationError, match="invalid name segment"):
            SkillMetadata(
                **_valid_kwargs(id="akosha:bad/name:1.0.0"),
            )

    def test_id_with_invalid_version_segment_rejected(self) -> None:
        with pytest.raises(ValidationError, match="invalid version segment"):
            SkillMetadata(
                **_valid_kwargs(id="akosha:search-insights:1.0.0/../../etc"),
            )


class TestSchemaInvariants:
    """Default values and field constraints beyond the allowlist."""

    def test_default_dependencies_empty(self) -> None:
        """Omitting ``dependencies`` yields ``[]`` via default_factory."""
        kwargs = _valid_kwargs()
        del kwargs["dependencies"]
        m = SkillMetadata(**kwargs)
        assert m.dependencies == []

    def test_default_content_type_skill(self) -> None:
        m = SkillMetadata(**_valid_kwargs(content_type="skill"))
        assert m.content_type == "skill"

    def test_default_body_format(self) -> None:
        m = SkillMetadata(**_valid_kwargs(body_format="yaml-frontmatter+markdown"))
        assert m.body_format == "yaml-frontmatter+markdown"

    def test_extras_forbidden(self) -> None:
        """Unknown fields raise ValidationError (model_config extra='forbid')."""
        with pytest.raises(ValidationError, match="Extra inputs"):
            SkillMetadata(**_valid_kwargs(unknown_field="x"))

    def test_signature_default_none(self) -> None:
        """``signature`` and ``server_pubkey_id`` default to None (unsigned)."""
        m = SkillMetadata(**_valid_kwargs())
        assert m.signature is None
        assert m.server_pubkey_id is None

    def test_description_max_length_1024(self) -> None:
        """Description is bounded at 1024 chars per plan §5 task #1."""
        long_desc = "x" * 1025
        with pytest.raises(ValidationError, match="description"):
            SkillMetadata(**_valid_kwargs(description=long_desc))

    def test_description_empty_after_strip_rejected(self) -> None:
        """Description must be non-empty after stripping whitespace."""
        with pytest.raises(ValidationError, match="description must be non-empty"):
            SkillMetadata(**_valid_kwargs(description="   "))
