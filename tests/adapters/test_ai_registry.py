"""Tests for AI adapter registry and provider info.

Covers: crackerjack/adapters/ai/registry.py
"""

from __future__ import annotations

import pytest

from crackerjack.adapters.ai.registry import (
    PROVIDER_INFO,
    ProviderID,
    ProviderInfo,
    get_code_fixer,
    get_provider_info,
    list_providers,
)


class TestProviderID:
    """Tests for ProviderID enum."""

    def test_provider_id_values(self):
        assert ProviderID.MINIMAX == "minimax"
        assert ProviderID.LLAMA_SERVER == "llama_server"


class TestProviderInfo:
    """Tests for ProviderInfo dataclass."""

    def test_provider_info_str(self):
        info = PROVIDER_INFO[ProviderID.MINIMAX]
        assert "MiniMax" in str(info)
        assert "minimax" in str(info)

    def test_provider_info_fields(self):
        info = PROVIDER_INFO[ProviderID.MINIMAX]
        assert info.id == ProviderID.MINIMAX
        assert info.name == "MiniMax"
        assert info.requires_api_key is True
        assert info.default_model == "MiniMax-M2.7"
        assert info.cost_tier == "medium"

    def test_llama_server_info(self):
        info = PROVIDER_INFO[ProviderID.LLAMA_SERVER]
        assert info.requires_api_key is False
        assert info.default_model == "qwen3.5"
        assert info.cost_tier == "free"


class TestListProviders:
    """Tests for list_providers function."""

    def test_returns_all_providers(self):
        providers = list_providers()
        assert len(providers) == 2

    def test_returns_provider_info_objects(self):
        providers = list_providers()
        assert all(isinstance(p, ProviderInfo) for p in providers)

    def test_contains_minimax(self):
        providers = list_providers()
        ids = [p.id for p in providers]
        assert ProviderID.MINIMAX in ids


class TestGetProviderInfo:
    """Tests for get_provider_info function."""

    def test_get_by_provider_id(self):
        info = get_provider_info(ProviderID.MINIMAX)
        assert info.id == ProviderID.MINIMAX

    def test_get_by_string_lowercase(self):
        info = get_provider_info("llama_server")
        assert info.id == ProviderID.LLAMA_SERVER

    def test_get_by_string_uppercase(self):
        info = get_provider_info("LLAMA_SERVER")
        assert info.id == ProviderID.LLAMA_SERVER

    def test_get_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider_info("unknown_provider")

    def test_unknown_provider_error_message(self):
        with pytest.raises(ValueError) as exc_info:
            get_provider_info("claude")
        assert "claude" in str(exc_info.value)
        assert "Available" in str(exc_info.value)


class TestGetCodeFixer:
    """Tests for get_code_fixer function."""

    def test_returns_code_fixer_instance(self):
        fixer = get_code_fixer()
        from crackerjack.adapters.ai.unified import FallbackChainCodeFixer

        assert isinstance(fixer, FallbackChainCodeFixer)

    def test_returns_same_instance_type(self):
        fixer1 = get_code_fixer()
        fixer2 = get_code_fixer()
        # Both should be the same type
        assert type(fixer1) == type(fixer2)


class TestProviderInfoShape:
    """Structural tests for the ``ProviderInfo`` shape.

    Phase 5 (bifrost plan §5, generalist H-3) pinned the absence
    of a ``uses_bifrost: bool`` decision field from
    ``PROVIDER_INFO``. The field was already absent on main at
    the time of the migration; the structural tests below are
    regression guards so a future refactor that re-adds the
    field (or any structurally-similar per-provider decision
    key that duplicates the router's "is this provider routed
    through the gateway?" query) trips a test failure.

    Note: legitimate per-provider capability flags
    (``uses_streaming``, ``uses_tool_calling``, ``uses_vision``,
    etc.) are NOT pinned by these tests — only the specific
    set of fields that would re-introduce the
    structural-coupling bug is locked.
    """

    # The set of field names that would re-introduce the
    # ``route_qwen_code: True while enabled: False`` bug shape:
    # any per-provider boolean that duplicates the router's
    # "is this provider routed through the gateway?" decision.
    # Naming is intentional — a maintainer adding a field
    # here must rename to ``supports_*`` / ``has_*`` / etc.
    # to avoid the test trip, which surfaces the decision in
    # code review.
    _FORBIDDEN_BIFROST_DECISION_KEYS: frozenset[str] = frozenset(
        {
            "uses_bifrost",
            "uses_claude_route",
            "uses_qwen_route",
            "uses_anthropic_route",
            "uses_gateway",
        }
    )

    def test_uses_bifrost_field_removed(self) -> None:
        """REQ-BIFROST-010 evidence (bifrost plan line 573): the
        ``uses_bifrost`` field is gone from every ``ProviderInfo``.
        Operators no longer need to set it; the URL source lives
        in the oneiric ``BifrostLLMRouter`` singleton.
        """
        import dataclasses

        for provider_id, info in PROVIDER_INFO.items():
            field_names = {f.name for f in dataclasses.fields(info)}
            assert "uses_bifrost" not in field_names, (
                f"ProviderInfo for {provider_id.value!r} unexpectedly has "
                "a 'uses_bifrost' field; the bifrost plan (generalist "
                "H-3) pinned its absence so the URL source stays in "
                "the oneiric router, not per-provider flags."
            )

    def test_no_bifrost_decision_keys(self) -> None:
        """Pin the absence of any per-provider decision field
        that would re-introduce the structural coupling to the
        bifrost gateway configuration. The URL source is the
        oneiric router, not per-provider boolean flags.

        Note: the deny-list is a *name set*, not a ``uses_*``
        prefix ban — legitimate per-provider capability flags
        (``uses_streaming``, ``uses_tool_calling``, etc.) are
        not pinned by this test. The test guards specifically
        against fields that would duplicate the router's
        "is this provider routed through the gateway?" decision.
        """
        import dataclasses

        for provider_id, info in PROVIDER_INFO.items():
            for f in dataclasses.fields(info):
                assert (
                    f.name not in self._FORBIDDEN_BIFROST_DECISION_KEYS
                ), (
                    f"ProviderInfo for {provider_id.value!r} has a "
                    f"forbidden decision key ({f.name!r}); the bifrost "
                    "plan removed 'uses_bifrost' and the URL source "
                    "moved to the oneiric router. Add a per-provider "
                    "decision key only with a clear consumer (and a "
                    "name outside the _FORBIDDEN_BIFROST_DECISION_KEYS "
                    "set, so future maintainers can grep for it)."
                )
