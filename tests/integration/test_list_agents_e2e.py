"""End-to-end test for ``crackerjack_list_agents`` MCP tool.

Per plan §5 Phase 3 exit criteria and §11 B-6:

- ``mcp__<server>__list_agents()`` returns ≥1 entry with a
  non-empty ``system_prompt`` field.
- The four mandatory feed signals (``feed_entities_count``,
  ``feed_last_updated_timestamp``, ``cycles_total``,
  ``errors_total``) stay accurate across calls (B-7).

Crackerjack has no async lifespan — the SkillsSigner is built at
``init_signer_feed_state()`` time and read via
``get_signer_feed_state()``. The test bootstraps that singleton
explicitly with a fresh ephemeral keypair so it never reads /
mutates the real persisted ``~/.crackerjack/state/...`` key.

The test exercises the tool handler in-process via a stub FastMCP
app: we register the tool via the production ``register_agent_registry``
function, capture the registered coroutine, and invoke it directly.
That keeps the test fast (no subprocess, no TCP) while still
exercising the production code path.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest

# Marker so the test is opted into ``crackerjack`` runs but skipped
# automatically on environments without the in-process FastMCP shim.
pytestmark = pytest.mark.integration


@pytest.fixture
def isolated_signer_key(monkeypatch: pytest.MonkeyPatch) -> Generator[Path]:
    """Point ``CRACKERJACK_SKILLS_SIGNER_KEY_PATH`` at a path that does NOT exist yet.

    ``load_or_create_keypair`` reads the file as PEM when it exists, so we
    point at a fresh path inside an ephemeral directory and let
    ``load_or_create_keypair`` generate + persist the new keypair
    itself. This avoids a MalformedFraming error from an empty file.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="cj-signer-"))
    key_path = tmp_dir / "private_key.pem"
    assert not key_path.exists(), "fresh tmp dir must not contain the key file yet"

    monkeypatch.setenv("CRACKERJACK_SKILLS_SIGNER_KEY_PATH", str(key_path))
    yield key_path
    # Best-effort cleanup.
    try:
        key_path.unlink()
    except FileNotFoundError:
        pass
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


@pytest.fixture
def initialized_signer(isolated_signer_key: Path) -> Generator[Any]:
    """Initialize + return the SignerFeedState singleton, resetting on teardown."""
    from crackerjack.mcp import signer_feed
    from crackerjack.mcp.signer_feed import (
        init_signer_feed_state,
        reset_signer_feed_state,
    )

    reset_signer_feed_state()
    state = init_signer_feed_state()
    try:
        yield state
    finally:
        reset_signer_feed_state()
        signer_feed._signer_feed_state = None


class _StubApp:
    """Minimal shim implementing the FastMCP ``tool`` decorator API.

    The production ``register_agent_registry`` registers two tools via
    ``@app.tool(name=...)``. We capture both callables and surface them
    as attributes so the test can invoke them as plain async functions.
    """

    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Any]] = {}

    def tool(self, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Mirror the FastMCP ``tool`` decorator signature."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[name] = fn
            return fn

        return decorator


@pytest.mark.asyncio
async def test_list_agents_returns_three_entries(
    initialized_signer: Any,
) -> None:
    """Phase 3 exit criterion: ≥3 entries, non-empty ``system_prompt`` per entry."""
    from crackerjack.mcp.tools.agent_registry import register_agent_registry

    app = _StubApp()
    register_agent_registry(app)  # type: ignore[arg-type]

    assert "crackerjack_list_agents" in app.tools, (
        "register_agent_registry must register 'crackerjack_list_agents'"
    )

    crackerjack_list_agents = app.tools["crackerjack_list_agents"]
    entries = await crackerjack_list_agents()

    # The plan's minimum bar is ≥1 entry with non-empty system_prompt;
    # Crackerjack ships 3 starter agents per Phase 3 task #4.
    assert len(entries) >= 3, (
        f"crackerjack_list_agents must return ≥3 entries, got {len(entries)}"
    )

    # Every entry must carry a non-empty system_prompt (B-6).
    for entry in entries:
        assert entry.get("system_prompt", "").strip(), (
            f"entry {entry.get('name')!r} has empty system_prompt"
        )

    # Each entry must have a content_hash (sha256 of system_prompt bytes).
    for entry in entries:
        assert entry.get("content_hash"), (
            f"entry {entry.get('name')!r} is missing content_hash"
        )
        assert len(entry["content_hash"]) == 64, (
            f"entry {entry.get('name')!r} content_hash is not a sha256 hex digest"
        )

    # No signature on list responses (per Phase 1 mirror — signing
    # happens in get_agent).
    for entry in entries:
        assert entry.get("signature") is None
        assert entry.get("server_pubkey_id") is None


@pytest.mark.asyncio
async def test_list_agents_bumps_feed_cycles(
    initialized_signer: Any,
) -> None:
    """B-7: ``cycles_total`` must increment per call."""
    from crackerjack.mcp.signer_feed import get_signer_feed_state
    from crackerjack.mcp.tools.agent_registry import register_agent_registry

    app = _StubApp()
    register_agent_registry(app)  # type: ignore[arg-type]

    crackerjack_list_agents = app.tools["crackerjack_list_agents"]

    before = get_signer_feed_state().cycles_total
    await crackerjack_list_agents()
    after_one = get_signer_feed_state().cycles_total
    await crackerjack_list_agents()
    after_two = get_signer_feed_state().cycles_total

    assert after_one == before + 1, (
        f"first call did not bump cycles_total: before={before} after={after_one}"
    )
    assert after_two == after_one + 1, (
        f"second call did not bump cycles_total: "
        f"after_one={after_one} after_two={after_two}"
    )


@pytest.mark.asyncio
async def test_list_agents_returns_expected_agent_names(
    initialized_signer: Any,
) -> None:
    """The 3 documented starter agents must be present, with the documented names."""
    from crackerjack.mcp.tools.agent_registry import register_agent_registry

    app = _StubApp()
    register_agent_registry(app)  # type: ignore[arg-type]

    entries = await app.tools["crackerjack_list_agents"]()
    names = {entry["name"] for entry in entries}

    expected = {
        "crackerjack-specialist",
        "quality-strategist",
        "bump-strategist",
    }
    assert expected.issubset(names), (
        f"missing agents: {expected - names}; got {names}"
    )


@pytest.mark.asyncio
async def test_list_agents_each_entry_has_valid_id_shape(
    initialized_signer: Any,
) -> None:
    """Every entry's ``id`` must be ``crackerjack:<name>:<version>``."""
    from crackerjack.mcp.tools.agent_registry import register_agent_registry

    app = _StubApp()
    register_agent_registry(app)  # type: ignore[arg-type]

    entries = await app.tools["crackerjack_list_agents"]()
    for entry in entries:
        parts = entry["id"].split(":")
        assert len(parts) == 3, f"id {entry['id']!r} is not 3 colon-separated parts"
        server_key, name, version = parts
        assert server_key == "crackerjack", (
            f"entry {entry['name']!r} has wrong server_key {server_key!r}"
        )
        assert name == entry["name"], (
            f"entry id {entry['id']!r} disagrees with name {entry['name']!r}"
        )
        assert version == entry["version"], (
            f"entry id {entry['id']!r} disagrees with version {entry['version']!r}"
        )