"""End-to-end test for ``crackerjack_get_agent`` MCP tool.

Per plan §5 Phase 3 exit criteria and §11 B-1 / B-6:

- ``get_agent(name)`` returns ``{metadata, body}`` where ``body`` is
  the full markdown text Claude Code loads as the system prompt.
- The metadata's ``content_hash`` matches sha256 of ``body`` bytes.
- The metadata is signed by the server's ed25519 keypair; the
  signature can be verified by an independent client.
- The B-4 allowlist rejects forbidden ``name`` values BEFORE the
  metadata model re-validates them (defense-in-depth).
- Unknown agents return an error envelope rather than raising past
  the MCP boundary.

The test boots a stub FastMCP app via the production
``register_agent_registry`` function and invokes the registered
``crackerjack_get_agent`` coroutine directly — no subprocess, no
TCP. Signing keypair is ephemeral (per-test tempfile via the
``isolated_signer_key`` fixture).
"""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def isolated_signer_key(monkeypatch: pytest.MonkeyPatch) -> Generator[Path]:
    """Point ``CRACKERJACK_SKILLS_SIGNER_KEY_PATH`` at a path that does NOT exist yet.

    ``load_or_create_keypair`` reads the file as PEM when it exists, so
    we point at a fresh path inside an ephemeral directory and let the
    signer create the keypair itself.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="cj-signer-"))
    key_path = tmp_dir / "private_key.pem"
    assert not key_path.exists(), "fresh tmp dir must not contain the key file yet"

    monkeypatch.setenv("CRACKERJACK_SKILLS_SIGNER_KEY_PATH", str(key_path))
    yield key_path
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
    """Minimal shim implementing the FastMCP ``tool`` decorator API."""

    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Any]] = {}

    def tool(self, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[name] = fn
            return fn

        return decorator


@pytest.fixture
def registered_app(initialized_signer: Any) -> _StubApp:
    """Return a stub FastMCP app with both agent tools registered."""
    from crackerjack.mcp.tools.agent_registry import register_agent_registry

    app = _StubApp()
    register_agent_registry(app)  # type: ignore[arg-type]
    return app


@pytest.mark.asyncio
async def test_get_agent_round_trips_for_canonical_name(
    registered_app: _StubApp,
) -> None:
    """The crackerjack-specialist entry round-trips: body + signed metadata."""
    crackerjack_get_agent = registered_app.tools["crackerjack_get_agent"]
    result = await crackerjack_get_agent("crackerjack-specialist")

    assert result.get("success") is True, f"unexpected error envelope: {result}"
    assert "metadata" in result and "body" in result

    metadata = result["metadata"]
    body = result["body"]

    # B-6: body must be non-empty (the critical Phase 3 fix).
    assert body.strip(), "get_agent returned an empty body"

    # content_hash must equal sha256 of body bytes.
    expected_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    assert metadata["content_hash"] == expected_hash, (
        f"content_hash mismatch: metadata={metadata['content_hash']!r} "
        f"expected={expected_hash!r}"
    )

    # Signature must be populated after signing.
    assert metadata.get("signature"), "metadata is missing ed25519 signature"
    assert metadata.get("server_pubkey_id"), "metadata is missing server_pubkey_id"


@pytest.mark.asyncio
async def test_get_agent_signature_verifies_independently(
    registered_app: _StubApp,
    initialized_signer: Any,
) -> None:
    """The signature must verify against the canonicalized payload.

    Uses :func:`crackerjack.skills_signer.verify_signature` with the
    server's own pubkey manifest — the same code path Phase 3
    installers will use on the client side. If the signature does not
    verify, either the signer changed between signing and verification
    or the canonicalization was inconsistent.
    """
    from crackerjack.skills_signer import (
        canonical_payload_for_signing,
        verify_signature,
    )

    crackerjack_get_agent = registered_app.tools["crackerjack_get_agent"]
    result = await crackerjack_get_agent("quality-strategist")

    assert result.get("success") is True, f"unexpected error envelope: {result}"
    metadata = result["metadata"]

    # Re-canonicalize the same way the tool handler did and verify
    # against the server's own pubkey manifest (this is the wire
    # shape the Phase 3 installer will see).
    canonical = canonical_payload_for_signing(metadata)
    verify_signature(
        canonical,
        metadata["signature"],
        metadata["server_pubkey_id"],
        initialized_signer.manifest,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["bump-strategist", "crackerjack-specialist", "quality-strategist"])
async def test_get_agent_works_for_all_documented_agents(
    registered_app: _StubApp,
    name: str,
) -> None:
    """Every documented starter agent must round-trip cleanly."""
    crackerjack_get_agent = registered_app.tools["crackerjack_get_agent"]
    result = await crackerjack_get_agent(name)

    assert result.get("success") is True, (
        f"get_agent({name!r}) returned error envelope: {result}"
    )
    metadata = result["metadata"]
    body = result["body"]

    # Round-trip invariant: content_hash matches body bytes.
    assert metadata["content_hash"] == hashlib.sha256(body.encode("utf-8")).hexdigest()
    # Body is non-empty.
    assert body.strip()
    # Server key is the expected server.
    assert metadata["server_key"] == "crackerjack"


@pytest.mark.asyncio
async def test_get_agent_rejects_unknown_name(
    registered_app: _StubApp,
) -> None:
    """Unknown names return an error envelope rather than raising."""
    crackerjack_get_agent = registered_app.tools["crackerjack_get_agent"]
    result = await crackerjack_get_agent("does-not-exist")

    assert result.get("success") is False
    assert "not found" in result.get("error", "").lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "forbidden_name",
    [
        "../etc/passwd",  # path traversal (regex catches leading dot + slash)
        "FOO",  # uppercase (regex forbids)
        "a" * 64,  # length > 63 (regex caps at 62 trailing chars)
        "name..with..dots",  # ``..`` substring (defense-in-depth)
        "name/with/slash",  # ``/`` anywhere (regex forbids)
    ],
)
async def test_get_agent_rejects_b4_violations(
    registered_app: _StubApp,
    forbidden_name: str,
) -> None:
    """B-4: forbidden ``name`` values are rejected at the API boundary."""
    crackerjack_get_agent = registered_app.tools["crackerjack_get_agent"]
    result = await crackerjack_get_agent(forbidden_name)

    assert result.get("success") is False, (
        f"forbidden name {forbidden_name!r} unexpectedly succeeded: {result}"
    )
    error = result.get("error", "").lower()
    assert "allowlist" in error or "b-4" in error, (
        f"error message for {forbidden_name!r} does not reference allowlist: "
        f"{result.get('error')!r}"
    )


@pytest.mark.asyncio
async def test_get_agent_includes_scope_section_in_body(
    registered_app: _StubApp,
) -> None:
    """R-14 / Phase 3 task #4: every starter agent must have a Scope section."""
    crackerjack_get_agent = registered_app.tools["crackerjack_get_agent"]

    for name in ["crackerjack-specialist", "quality-strategist", "bump-strategist"]:
        result = await crackerjack_get_agent(name)
        assert result.get("success") is True, (
            f"get_agent({name!r}) failed: {result}"
        )
        body = result["body"]
        assert "## Scope" in body, (
            f"agent {name!r} body is missing the required ## Scope section"
        )