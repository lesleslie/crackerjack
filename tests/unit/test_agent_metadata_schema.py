"""Unit tests for :class:`crackerjack.mcp.agent_schema.AgentMetadata`.

Per plan §5 task #4 and §11 B-4 / B-6, the AgentMetadata schema
enforces a strict path-traversal allowlist on ``name`` / ``server_key``
and requires a non-empty ``system_prompt``. These tests pin both
contracts so a server cannot accidentally weaken them.

The tests are scoped to the schema model only — they do NOT spin up a
FastMCP server or exercise the signing flow (those live in
``tests/integration/test_list_agents_e2e.py`` and
``tests/integration/test_get_agent_e2e.py``).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from crackerjack.mcp.agent_schema import AgentMetadata


def _base_kwargs(**overrides: object) -> dict[str, object]:
    """Build a kwargs dict that passes every required validator.

    Tests pass overrides to trigger specific failure modes.
    """
    base: dict[str, object] = {
        "id": "crackerjack:test-agent:1.0.0",
        "server_key": "crackerjack",
        "name": "test-agent",
        "description": "Test agent description",
        "version": "1.0.0",
        "model": "sonnet",
        "system_prompt": "This is a non-empty system prompt body.",
        "content_hash": (
            "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
        ),
        "timestamp": datetime.now(UTC).timestamp(),
    }
    base.update(overrides)
    return base


class TestNameAllowlist:
    """B-4 path-traversal allowlist on the ``name`` field."""

    def test_simple_lowercase_name_passes(self) -> None:
        """The canonical happy path: lowercase + dash."""
        m = AgentMetadata(**_base_kwargs(name="crackerjack-specialist"))
        assert m.name == "crackerjack-specialist"

    def test_name_with_underscore_and_digits_passes(self) -> None:
        """Underscore + digits are in the allowlist."""
        m = AgentMetadata(**_base_kwargs(name="bump_strategist_v2"))
        assert m.name == "bump_strategist_v2"

    def test_name_with_dot_passes(self) -> None:
        """Dot is in the allowlist (matches Phase 1 skill naming)."""
        m = AgentMetadata(**_base_kwargs(name="agent.v1"))
        assert m.name == "agent.v1"

    @pytest.mark.parametrize("forbidden", ["/", "..", ".", "A", "Z", "_", "-", ""])
    def test_forbidden_name_rejected(self, forbidden: str) -> None:
        """Every documented forbidden shape raises ``ValidationError``."""
        if forbidden == "_" or forbidden == "-":
            # Underscore / dash alone: regex requires ``[a-z0-9]`` first
            # char. Both are invalid because the first char is not in the
            # allowlist (which is ``[a-z0-9]``).
            with pytest.raises(ValidationError, match="allowlist regex"):
                AgentMetadata(**_base_kwargs(name=forbidden))
        elif forbidden == "":
            # Empty fails the regex (requires ≥1 char).
            with pytest.raises(ValidationError, match="allowlist regex"):
                AgentMetadata(**_base_kwargs(name=forbidden))
        elif forbidden == ".":
            # Leading dot: fails the regex AND the substring check
            # (``"."`` contains ``".."`` is False; but the regex catches
            # it first). Accept either failure mode.
            with pytest.raises(ValidationError):
                AgentMetadata(**_base_kwargs(name=forbidden))
        elif forbidden == "..":
            # ``..`` substring check fires (defense-in-depth).
            with pytest.raises(ValidationError, match=r"\.\."):
                AgentMetadata(**_base_kwargs(name=forbidden))
        else:
            # ``/`` / uppercase / etc. fail the regex.
            with pytest.raises(ValidationError, match="allowlist regex"):
                AgentMetadata(**_base_kwargs(name=forbidden))

    def test_64_char_name_rejected(self) -> None:
        """Total length > 63 is rejected (regex ``{0,62}`` after first char)."""
        # 64 chars total: first char lowercase + 63 more (regex caps at 62).
        too_long = "a" + "b" * 63
        assert len(too_long) == 64
        with pytest.raises(ValidationError, match="allowlist regex"):
            AgentMetadata(**_base_kwargs(name=too_long))

    def test_63_char_name_accepted(self) -> None:
        """Total length 63 is the boundary; must still pass."""
        just_right = "a" + "b" * 62
        assert len(just_right) == 63
        m = AgentMetadata(**_base_kwargs(name=just_right))
        assert m.name == just_right

    def test_path_traversal_payload_rejected(self) -> None:
        """A literal path-traversal payload like ``../../etc/passwd``
        must be rejected. The regex catches ``/``; the substring check
        catches the leading ``.``.
        """
        with pytest.raises(ValidationError):
            AgentMetadata(**_base_kwargs(name="../../etc/passwd"))


class TestServerKeyAllowlist:
    """B-4 path-traversal allowlist on the ``server_key`` field.

    The plan requires the same regex on ``server_key`` so a server
    cannot advertise itself as ``../akosha`` to spoof a different
    registry's catalog.
    """

    def test_simple_server_key_passes(self) -> None:
        m = AgentMetadata(**_base_kwargs(server_key="crackerjack"))
        assert m.server_key == "crackerjack"

    def test_server_key_with_uppercase_rejected(self) -> None:
        with pytest.raises(ValidationError, match="allowlist regex"):
            AgentMetadata(**_base_kwargs(server_key="Crackerjack"))

    def test_server_key_with_slash_rejected(self) -> None:
        with pytest.raises(ValidationError, match="allowlist regex"):
            AgentMetadata(**_base_kwargs(server_key="akosha/spoof"))


class TestSystemPromptRequired:
    """B-6 / plan §5 task #2: ``system_prompt`` must be non-empty.

    The Phase 3 plan's critical fix — without a body, the installed
    agent is non-functional. The schema enforces this so a server
    cannot accidentally advertise a body-less agent.
    """

    def test_non_empty_system_prompt_passes(self) -> None:
        m = AgentMetadata(**_base_kwargs(system_prompt="real body"))
        assert m.system_prompt == "real body"

    def test_empty_system_prompt_rejected(self) -> None:
        with pytest.raises(ValidationError, match="system_prompt"):
            AgentMetadata(**_base_kwargs(system_prompt=""))

    def test_whitespace_only_system_prompt_rejected(self) -> None:
        """Whitespace-only is non-functional — reject it."""
        with pytest.raises(ValidationError, match="system_prompt"):
            AgentMetadata(**_base_kwargs(system_prompt="   \n\t  "))


class TestDescriptionRequired:
    """The ``description`` validator mirrors the Phase 1 contract."""

    def test_empty_description_rejected(self) -> None:
        with pytest.raises(ValidationError, match="description"):
            AgentMetadata(**_base_kwargs(description=""))

    def test_whitespace_description_rejected(self) -> None:
        with pytest.raises(ValidationError, match="description"):
            AgentMetadata(**_base_kwargs(description="   "))


class TestIdShape:
    """``id`` must be ``{server_key}:{name}:{version}``."""

    def test_canonical_id_passes(self) -> None:
        m = AgentMetadata(**_base_kwargs(
            id="crackerjack:bump-strategist:1.0.0",
            server_key="crackerjack",
            name="bump-strategist",
            version="1.0.0",
        ))
        assert m.id == "crackerjack:bump-strategist:1.0.0"

    def test_id_with_extra_colons_rejected(self) -> None:
        """Extra colons break the documented ``server_key:name:version`` format."""
        with pytest.raises(ValidationError, match="exactly 3 colon-separated"):
            AgentMetadata(**_base_kwargs(
                id="crackerjack:bump:strategist:1.0.0",
            ))

    def test_id_with_invalid_server_segment_rejected(self) -> None:
        with pytest.raises(ValidationError, match="server_key segment"):
            AgentMetadata(**_base_kwargs(
                id="BadServer:bump-strategist:1.0.0",
            ))

    def test_id_with_invalid_name_segment_rejected(self) -> None:
        with pytest.raises(ValidationError, match="name segment"):
            AgentMetadata(**_base_kwargs(
                id="crackerjack:BAD-NAME:1.0.0",
            ))

    def test_id_with_invalid_version_segment_rejected(self) -> None:
        with pytest.raises(ValidationError, match="version segment"):
            AgentMetadata(**_base_kwargs(
                id="crackerjack:bump-strategist:1.0.0/evil",
            ))

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(ValidationError, match="id"):
            AgentMetadata(**_base_kwargs(id=""))


class TestScopeLiteral:
    """R-14: ``scope`` must be one of the documented literals."""

    def test_user_global_scope_passes(self) -> None:
        m = AgentMetadata(**_base_kwargs(scope="user-global"))
        assert m.scope == "user-global"

    def test_project_local_scope_passes(self) -> None:
        m = AgentMetadata(**_base_kwargs(scope="project-local"))
        assert m.scope == "project-local"

    def test_invalid_scope_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentMetadata(**_base_kwargs(scope="server-shared"))


class TestLastReviewedFormat:
    """``last_reviewed`` must be YYYY-MM-DD when set."""

    def test_iso_date_passes(self) -> None:
        m = AgentMetadata(**_base_kwargs(last_reviewed="2026-09-10"))
        assert m.last_reviewed == "2026-09-10"

    def test_none_passes(self) -> None:
        m = AgentMetadata(**_base_kwargs(last_reviewed=None))
        assert m.last_reviewed is None

    @pytest.mark.parametrize("bad", ["2026-9-10", "26-09-10", "2026/09/10", "today"])
    def test_malformed_dates_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError, match="last_reviewed"):
            AgentMetadata(**_base_kwargs(last_reviewed=bad))


class TestStatusLiteral:
    """``status`` must be one of the documented literals when set."""

    def test_active_status_passes(self) -> None:
        m = AgentMetadata(**_base_kwargs(status="active"))
        assert m.status == "active"

    def test_archived_status_passes(self) -> None:
        m = AgentMetadata(**_base_kwargs(status="archived"))
        assert m.status == "archived"

    def test_draft_status_passes(self) -> None:
        m = AgentMetadata(**_base_kwargs(status="draft"))
        assert m.status == "draft"

    def test_none_status_passes(self) -> None:
        m = AgentMetadata(**_base_kwargs(status=None))
        assert m.status is None

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentMetadata(**_base_kwargs(status="deprecated"))


class TestExtraFieldsForbidden:
    """``extra='forbid'`` config — unknown fields raise."""

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            AgentMetadata(**_base_kwargs(unknown_field="evil"))


class TestValidateAssignment:
    """``validate_assignment=True`` — re-validation on attribute set."""

    def test_assignment_with_invalid_name_rejected(self) -> None:
        m = AgentMetadata(**_base_kwargs())
        with pytest.raises(ValidationError):
            m.name = "../bad"
