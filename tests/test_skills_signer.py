"""Unit tests for the ``skills_signer`` package (Phase 1.5 of
``docs/plans/2026-09-09-bodai-skill-agent-distribution.md``).

These tests cover the cryptographic core: keypair generation,
canonicalization, signing, verification, tampering rejection, and
the pubkey manifest round-trip. They MUST run with no network and
no external services — the signing layer is local-only.

After the 3-agent review (Phase 1.5 quality-control round, 2026-09-09),
this file was extended to cover:

- :func:`canonical_payload_for_signing` (strips signature fields)
- :class:`UnknownKeyIdError` (replaces ``KeyError`` from verify path)
- :class:`MalformedManifestError` / :class:`InvalidManifestAlgorithmError`
- Multi-entry manifests and :func:`merge_manifests` (rotation)
- :func:`load_or_create_keypair` (key persistence)
"""

from __future__ import annotations

import base64
from pathlib import Path  # noqa: TC003  # used in pytest tmp_path parameter
from typing import Any

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

# SignerFeedState lives in crackerjack.mcp (not in the skills_signer package
# itself), so import it directly. Tests for the package itself import
# only from the package; tests for the MCP integration import both.
from crackerjack.mcp.signer_feed import SignerFeedState

from crackerjack.skills_signer import (
    InvalidManifestAlgorithmError,
    Keypair,
    MalformedManifestError,
    PubkeyManifest,
    SkillsSigner,
    UnknownKeyIdError,
    build_pubkey_manifest,
    canonical_payload_for_signing,
    canonicalize_payload,
    generate_keypair,
    load_or_create_keypair,
    manifest_entry_from_dict,
    manifest_from_dict,
    merge_manifests,
    public_key_from_bytes,
    verify_signature,
)

# ---------------------------------------------------------------------------
# Canonicalization
# ---------------------------------------------------------------------------


class TestCanonicalizePayload:
    def test_dict_sorted_keys_deterministic(self) -> None:
        """Same logical dict produces byte-identical output regardless of key order."""
        a = canonicalize_payload({"b": 2, "a": 1, "c": 3})
        b = canonicalize_payload({"c": 3, "a": 1, "b": 2})
        assert a == b
        assert a == b'{"a":1,"b":2,"c":3}'

    def test_no_whitespace(self) -> None:
        payload = canonicalize_payload({"key": "value", "list": [1, 2, 3]})
        assert b" " not in payload
        assert b"\n" not in payload
        assert b"\t" not in payload

    def test_unicode_preserved(self) -> None:
        """``ensure_ascii=False`` keeps non-ASCII characters intact."""
        payload = canonicalize_payload({"name": "café", "city": "東京"})
        assert "café".encode() in payload
        assert "東京".encode() in payload

    def test_pydantic_model_dump(self) -> None:
        """Pydantic v2 models are converted via ``model_dump(mode="json")``."""

        class Sample:
            def model_dump(self, *, mode: str = "python") -> dict[str, Any]:  # noqa: ARG002
                return {"x": 1, "y": "z"}

        payload = canonicalize_payload(Sample())
        assert payload == b'{"x":1,"y":"z"}'

    def test_pydantic_mode_json_forces_json_native_types(self) -> None:
        """``model_dump(mode="json")`` coerces datetime/Decimal to JSON-safe forms.

        Without mode="json", datetime objects crash ``json.dumps`` with
        ``TypeError``. The canonicalizer pins mode="json" so adding a
        datetime field to a schema does not break signing.
        """
        from datetime import datetime

        class WithDatetime:
            def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
                if mode == "json":
                    return {"created_at": "2026-09-09T00:00:00Z"}
                return {"created_at": datetime(2026, 9, 9)}  # would crash json.dumps

        payload = canonicalize_payload(WithDatetime())
        assert b'"created_at":"2026-09-09T00:00:00Z"' in payload

    def test_canonicalize_empty_dict(self) -> None:
        assert canonicalize_payload({}) == b"{}"

    def test_canonicalize_none(self) -> None:
        assert canonicalize_payload(None) == b"null"

    def test_canonicalize_numeric_primitive(self) -> None:
        assert canonicalize_payload(42) == b"42"


# ---------------------------------------------------------------------------
# canonical_payload_for_signing (B1 — strips post-signing fields)
# ---------------------------------------------------------------------------


class TestCanonicalPayloadForSigning:
    def test_strips_signature_field_from_dict(self) -> None:
        """A dict with ``signature`` and ``server_pubkey_id`` strips both."""
        payload = {
            "name": "crackerjack-search",
            "version": "1.0.0",
            "signature": "should_be_stripped",
            "server_pubkey_id": "should_be_stripped",
        }
        canonical = canonical_payload_for_signing(payload)
        assert b"signature" not in canonical
        assert b"server_pubkey_id" not in canonical
        assert canonical == canonicalize_payload({"name": "crackerjack-search", "version": "1.0.0"})

    def test_strips_signature_field_from_pydantic_model(self) -> None:
        """A Pydantic model with ``signature`` field strips it via model_dump."""

        class WithSignature:
            def model_dump(self, *, mode: str = "python") -> dict[str, Any]:  # noqa: ARG002
                return {
                    "name": "crackerjack-search",
                    "signature": "fake_sig",
                    "server_pubkey_id": "fake_key",
                }

        canonical = canonical_payload_for_signing(WithSignature())
        assert b"signature" not in canonical
        assert b"server_pubkey_id" not in canonical
        assert canonical == b'{"name":"crackerjack-search"}'

    def test_extra_exclude_keys(self) -> None:
        """Caller can add additional keys to strip beyond the defaults."""
        payload = {
            "name": "x",
            "signature": "s",
            "server_pubkey_id": "k",
            "internal_secret": "should_be_gone",
        }
        canonical = canonical_payload_for_signing(
            payload, extra_exclude_keys=frozenset({"internal_secret"})
        )
        assert b"internal_secret" not in canonical
        assert b"signature" not in canonical

    def test_signing_without_stripping_produces_different_bytes(self) -> None:
        """Sanity: canonical_payload_for_signing ≠ canonicalize_payload when
        the dict contains signature fields. This is the bug the helper
        prevents in Phase 2 — without stripping, the client re-canonicalizes
        the *populated* metadata and gets different bytes than the server signed.
        """
        populated = {
            "name": "x",
            "signature": "real_sig",
            "server_pubkey_id": "real_key",
        }
        assert canonical_payload_for_signing(populated) != canonicalize_payload(populated)


# ---------------------------------------------------------------------------
# Keypair generation
# ---------------------------------------------------------------------------


class TestGenerateKeypair:
    def test_unique_keypairs_have_different_key_ids(self) -> None:
        a = generate_keypair()
        b = generate_keypair()
        assert a.key_id != b.key_id

    def test_key_id_is_16_hex_chars(self) -> None:
        kp = generate_keypair()
        assert len(kp.key_id) == 16
        int(kp.key_id, 16)  # parses as hex

    def test_key_id_matches_sha256_of_public_key(self) -> None:
        """key_id must equal the first KEY_ID_BYTES of SHA256(public_key_raw)."""
        import hashlib

        kp = generate_keypair()
        raw = kp.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        expected = hashlib.sha256(raw).digest()[:8].hex()
        assert kp.key_id == expected

    def test_public_key_from_bytes_roundtrip(self) -> None:
        kp = generate_keypair()
        raw = kp.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        assert len(raw) == 32
        reloaded = public_key_from_bytes(raw)
        assert reloaded.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ) == raw

    def test_public_key_from_bytes_wrong_length(self) -> None:
        with pytest.raises(ValueError, match="exactly 32 bytes"):
            public_key_from_bytes(b"too short")

    def test_key_id_uniqueness_across_many_keypairs(self) -> None:
        """Statistical guarantee: 1000 generated keypairs all have distinct key_ids.

        Truncating SHA-256 to 64 bits gives 2^-64 collision probability per pair;
        across 1000 keys the expected collisions are <10^-15. If this fails,
        something has gone wrong with the key_id derivation, not bad luck.
        """
        ids = {generate_keypair().key_id for _ in range(1000)}
        assert len(ids) == 1000


# ---------------------------------------------------------------------------
# Keypair persistence (A4)
# ---------------------------------------------------------------------------


class TestLoadOrCreateKeypair:
    def test_creates_new_keypair_when_file_absent(self, tmp_path: Path) -> None:
        path = tmp_path / "skills_signer" / "private_key.pem"
        kp = load_or_create_keypair(path)
        assert path.exists()
        assert isinstance(kp, Keypair)

    def test_persisted_file_has_restricted_permissions(self, tmp_path: Path) -> None:
        """Parent dir 0o700, key file 0o600."""
        path = tmp_path / "skills_signer" / "private_key.pem"
        load_or_create_keypair(path)
        # POSIX permission check via stat
        file_mode = path.stat().st_mode & 0o777
        assert file_mode == 0o600, f"got {oct(file_mode)}"
        parent_mode = path.parent.stat().st_mode & 0o777
        assert parent_mode == 0o700, f"got {oct(parent_mode)}"

    def test_loads_existing_keypair_with_same_key_id(self, tmp_path: Path) -> None:
        """Second call returns the same keypair (key_id stable across calls)."""
        path = tmp_path / "private_key.pem"
        first = load_or_create_keypair(path)
        second = load_or_create_keypair(path)
        assert first.key_id == second.key_id

    def test_loaded_keypair_can_sign_and_verify(self, tmp_path: Path) -> None:
        """Round-trip: load → sign → verify against manifest built from same key."""
        path = tmp_path / "private_key.pem"
        kp = load_or_create_keypair(path)
        signer = SkillsSigner.from_keypair(kp)
        manifest = signer.pubkey_manifest()

        metadata = {"name": "test", "version": "1.0.0"}
        canonical = canonicalize_payload(metadata)
        signed = signer.sign(canonical)

        entry = verify_signature(
            canonical_payload=canonical,
            signature_b64=signed.signature_b64,
            key_id=signed.key_id,
            manifest=manifest,
        )
        assert entry.key_id == kp.key_id


# ---------------------------------------------------------------------------
# Signing and verification round-trip
# ---------------------------------------------------------------------------


class TestSigningRoundtrip:
    def test_sign_then_verify_succeeds(self) -> None:
        kp = generate_keypair()
        signer = SkillsSigner.from_keypair(kp)
        manifest = signer.pubkey_manifest()

        metadata = {"name": "crackerjack-search", "version": "1.0.0", "tool_refs": []}
        canonical = canonicalize_payload(metadata)
        signed = signer.sign(canonical)

        entry = verify_signature(
            canonical_payload=canonical,
            signature_b64=signed.signature_b64,
            key_id=signed.key_id,
            manifest=manifest,
        )
        assert entry.key_id == kp.key_id

    def test_signature_b64_is_ascii_safe(self) -> None:
        """Wire format must be ASCII (base64) for JSON transport."""
        kp = generate_keypair()
        signer = SkillsSigner.from_keypair(kp)
        signed = signer.sign(canonicalize_payload({"x": 1}))
        signed.signature_b64.encode("ascii")  # must not raise
        base64.b64decode(signed.signature_b64, validate=True)

    def test_tampered_payload_fails_verify(self) -> None:
        """A 1-byte change in the payload must cause verification to fail."""
        kp = generate_keypair()
        signer = SkillsSigner.from_keypair(kp)
        manifest = signer.pubkey_manifest()

        canonical = canonicalize_payload({"name": "crackerjack-search", "version": "1.0.0"})
        signed = signer.sign(canonical)

        tampered = canonical.replace(b"1.0.0", b"2.0.0")
        with pytest.raises(InvalidSignature):
            verify_signature(
                canonical_payload=tampered,
                signature_b64=signed.signature_b64,
                key_id=signed.key_id,
                manifest=manifest,
            )

    def test_tampered_signature_fails_verify(self) -> None:
        """A 1-byte change in the signature must cause verification to fail."""
        kp = generate_keypair()
        signer = SkillsSigner.from_keypair(kp)
        manifest = signer.pubkey_manifest()

        canonical = canonicalize_payload({"x": 1})
        signed = signer.sign(canonical)

        sig_bytes = bytearray(base64.b64decode(signed.signature_b64))
        sig_bytes[0] ^= 0x01
        tampered_sig = base64.b64encode(bytes(sig_bytes)).decode("ascii")

        with pytest.raises(InvalidSignature):
            verify_signature(
                canonical_payload=canonical,
                signature_b64=tampered_sig,
                key_id=signed.key_id,
                manifest=manifest,
            )

    def test_wrong_key_id_raises_unknown_key_id_error(self) -> None:
        """A signature from server A verified against server B's manifest must fail."""
        server_a = generate_keypair()
        server_b = generate_keypair()
        signer_a = SkillsSigner.from_keypair(server_a)
        manifest_b = SkillsSigner.from_keypair(server_b).pubkey_manifest()

        canonical = canonicalize_payload({"x": 1})
        signed_a = signer_a.sign(canonical)

        with pytest.raises(UnknownKeyIdError, match="not present in pubkey manifest"):
            verify_signature(
                canonical_payload=canonical,
                signature_b64=signed_a.signature_b64,
                key_id=signed_a.key_id,
                manifest=manifest_b,
            )

    def test_unknown_key_id_raises_unknown_key_id_error(self) -> None:
        """A forged key_id raises ``UnknownKeyIdError``, NOT ``KeyError``.

        Verifies review B4: the verify path raises its own type so callers
        cannot accidentally catch a ``KeyError`` raised by an inner
        ``dict`` lookup and treat it as a manifest error.
        """
        kp = generate_keypair()
        signer = SkillsSigner.from_keypair(kp)
        manifest = signer.pubkey_manifest()

        canonical = canonicalize_payload({"x": 1})
        signed = signer.sign(canonical)

        with pytest.raises(UnknownKeyIdError):
            verify_signature(
                canonical_payload=canonical,
                signature_b64=signed.signature_b64,
                key_id="0000000000000000",
                manifest=manifest,
            )

    def test_unknown_key_id_error_is_not_key_error(self) -> None:
        """``UnknownKeyIdError`` must NOT subclass ``KeyError`` — the review
        explicitly required this so installers cannot catch a stray
        ``KeyError`` and treat it as a verify failure.
        """
        assert not issubclass(UnknownKeyIdError, KeyError)

    def test_signature_b64_rejects_bytes(self) -> None:
        """``signature_b64`` must be ``str``; passing ``bytes`` raises ``TypeError``."""
        kp = generate_keypair()
        manifest = SkillsSigner.from_keypair(kp).pubkey_manifest()
        with pytest.raises(TypeError, match="must be str"):
            verify_signature(
                canonical_payload=b'{"x":1}',
                signature_b64=b"not-a-string",
                key_id=kp.key_id,
                manifest=manifest,
            )

    def test_malformed_signature_b64_raises_valueerror(self) -> None:
        kp = generate_keypair()
        manifest = SkillsSigner.from_keypair(kp).pubkey_manifest()

        with pytest.raises(ValueError, match="not valid base64"):
            verify_signature(
                canonical_payload=b'{"x":1}',
                signature_b64="not!base64!at!all",
                key_id=kp.key_id,
                manifest=manifest,
            )


# ---------------------------------------------------------------------------
# Pubkey manifest serialization round-trip + algorithm validation (R2-M3)
# ---------------------------------------------------------------------------


class TestPubkeyManifestRoundtrip:
    def test_build_manifest_single_entry(self) -> None:
        kp = generate_keypair()
        manifest = build_pubkey_manifest(kp)
        assert len(manifest) == 1
        assert kp.key_id in manifest

    def test_as_dict_is_pure_data_no_lifecycle_signals(self) -> None:
        """``PubkeyManifest.as_dict()`` does NOT include ``ok`` or feed signals.

        The lifecycle signals (``ok``, ``feed_entities_count``, etc.) are
        added by ``SignerFeedState``, not the manifest itself. This keeps
        the package pure data and replicates byte-for-byte across servers.
        """
        kp = generate_keypair()
        manifest = build_pubkey_manifest(kp)
        payload = manifest.as_dict()
        assert "ok" not in payload
        assert "feed_entities_count" not in payload
        assert "cycles_total" not in payload
        assert "errors_total" not in payload
        assert "last_updated_timestamp" not in payload
        assert payload["key_count"] == 1
        assert len(payload["pubkeys"]) == 1

    def test_as_dict_then_from_dict_roundtrip(self) -> None:
        kp = generate_keypair()
        manifest = build_pubkey_manifest(kp)
        payload = manifest.as_dict()

        reloaded = manifest_from_dict(payload)
        reloaded_entry = reloaded.get(kp.key_id)
        assert reloaded_entry is not None

        original_raw = kp.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        reloaded_raw = reloaded_entry.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        assert original_raw == reloaded_raw

    def test_manifest_entry_from_dict_missing_fields(self) -> None:
        """Missing required fields raises ``MalformedManifestError``, not ``KeyError``."""
        with pytest.raises(MalformedManifestError, match="missing fields"):
            manifest_entry_from_dict({"key_id": "abc"})

    def test_manifest_entry_from_dict_unsupported_algorithm(self) -> None:
        """``algorithm != 'ed25519'`` raises ``InvalidManifestAlgorithmError``.

        Defense-in-depth against a future algorithm migration that could
        introduce downgrade attacks.
        """
        bad = {
            "key_id": "0" * 16,
            "algorithm": "rsa-pss",  # not supported
            "public_key_b64": base64.b64encode(b"\x00" * 32).decode("ascii"),
            "created_at": 0.0,
        }
        with pytest.raises(InvalidManifestAlgorithmError, match="unsupported manifest algorithm"):
            manifest_entry_from_dict(bad)

    def test_manifest_is_empty(self) -> None:
        """``PubkeyManifest()`` with no entries reports ``is_empty() == True``."""
        assert PubkeyManifest().is_empty() is True
        assert build_pubkey_manifest(generate_keypair()).is_empty() is False


class TestMultiEntryManifest:
    """Rotation scenario: a manifest with both old and new entries during
    the grace period. Both keys verify successfully."""

    def test_build_with_list_of_keypairs(self) -> None:
        old_kp = generate_keypair()
        new_kp = generate_keypair()
        manifest = build_pubkey_manifest([old_kp, new_kp])

        assert len(manifest) == 2
        assert old_kp.key_id in manifest
        assert new_kp.key_id in manifest

    def test_signature_from_old_key_verifies_against_multi_entry_manifest(self) -> None:
        """A signature from the old key still verifies during the grace period."""
        old_kp = generate_keypair()
        new_kp = generate_keypair()
        manifest = build_pubkey_manifest([old_kp, new_kp])

        old_signer = SkillsSigner.from_keypair(old_kp)
        canonical = canonicalize_payload({"data": "from_old_key"})
        signed = old_signer.sign(canonical)

        entry = verify_signature(
            canonical_payload=canonical,
            signature_b64=signed.signature_b64,
            key_id=signed.key_id,
            manifest=manifest,
        )
        assert entry.key_id == old_kp.key_id

    def test_signature_from_new_key_also_verifies(self) -> None:
        old_kp = generate_keypair()
        new_kp = generate_keypair()
        manifest = build_pubkey_manifest([old_kp, new_kp])

        new_signer = SkillsSigner.from_keypair(new_kp)
        canonical = canonicalize_payload({"data": "from_new_key"})
        signed = new_signer.sign(canonical)

        entry = verify_signature(
            canonical_payload=canonical,
            signature_b64=signed.signature_b64,
            key_id=signed.key_id,
            manifest=manifest,
        )
        assert entry.key_id == new_kp.key_id

    def test_merge_manifests_combines_entries(self) -> None:
        """``merge_manifests(a, b)`` combines entries; later wins on duplicates."""
        old_kp = generate_keypair()
        new_kp = generate_keypair()
        m1 = build_pubkey_manifest(old_kp)
        m2 = build_pubkey_manifest(new_kp)
        merged = merge_manifests(m1, m2)
        assert len(merged) == 2
        assert old_kp.key_id in merged
        assert new_kp.key_id in merged


class TestSkillsSignerPubkeyManifest:
    def test_pubkey_manifest_method_returns_signer_entries(self) -> None:
        """``SkillsSigner.pubkey_manifest()`` returns the signer's pubkey entries.

        Fixes review R1-H1: this method was documented but missing.
        """
        kp = generate_keypair()
        signer = SkillsSigner.from_keypair(kp)
        manifest = signer.pubkey_manifest()
        assert isinstance(manifest, PubkeyManifest)
        assert len(manifest) == 1
        assert manifest.get(kp.key_id) is not None


# ---------------------------------------------------------------------------
# End-to-end: sign on one side, verify on another
# ---------------------------------------------------------------------------


class TestEndToEndFlow:
    def test_server_signs_client_verifies(self) -> None:
        """Simulate the full server-publishes / client-loads flow."""

        server_kp = generate_keypair()
        server_signer = SkillsSigner.from_keypair(server_kp)
        server_manifest = server_signer.pubkey_manifest()

        # ``server_metadata`` has no signature yet (the signature is added
        # AFTER signing). Use ``canonical_payload_for_signing`` so future
        # schema additions that include a ``signature`` field default
        # don't accidentally sign over themselves.
        server_metadata = {
            "name": "crackerjack-search-insights",
            "version": "1.0.0",
            "description": "Search across Crackerjack-indexed systems",
            "tool_refs": ["mcp__crackerjack__search_all_systems"],
            "dependencies": [],
        }
        canonical_bytes = canonical_payload_for_signing(server_metadata)
        signed = server_signer.sign(canonical_bytes)

        # Server publishes: the manifest is published in /health; the
        # signed metadata is the SkillMetadata returned by get_skill.
        published_metadata = {**server_metadata, "signature": signed.signature_b64,
                              "server_pubkey_id": signed.key_id}
        published_health = server_manifest.as_dict()

        # Client: receives manifest + signed metadata, strips signature
        # fields, re-canonicalizes, verifies.
        client_manifest = manifest_from_dict(published_health)
        client_canonical = canonical_payload_for_signing(published_metadata)
        entry = verify_signature(
            canonical_payload=client_canonical,
            signature_b64=signed.signature_b64,
            key_id=signed.key_id,
            manifest=client_manifest,
        )
        assert entry.key_id == server_kp.key_id


# ---------------------------------------------------------------------------
# SignerFeedState (the /health wrapper around the manifest)
# ---------------------------------------------------------------------------


class TestSignerFeedState:
    """The SignerFeedState is the /health source of truth for the
    skills_signer feed. It bundles the manifest + the four mandatory
    feed signals (entities_count, last_updated_timestamp, cycles_total,
    errors_total) + a generation token for ownership checks.
    """

    def test_ok_true_when_manifest_has_entries(self) -> None:
        manifest = build_pubkey_manifest(generate_keypair())
        state = SignerFeedState(manifest=manifest)
        assert state.is_ok() is True

    def test_ok_false_when_manifest_is_empty(self) -> None:
        """Empty manifest → ``ok=False`` → /health returns 503.

        Fixes review R3-H2: ``ok`` is computed from manifest invariants,
        not hardcoded. An empty manifest is a degraded state.
        """
        state = SignerFeedState(manifest=PubkeyManifest())
        assert state.is_ok() is False

    def test_as_dict_exposes_all_four_mandatory_signals(self) -> None:
        """``as_dict()`` includes ``feed_entities_count``,
        ``feed_last_updated_timestamp``, ``cycles_total``, ``errors_total``.

        Fixes review R3-H1: these signals are required by
        ``mcp-backend-wiring-discipline.md``; the previous
        ``manifest.as_dict()`` exposed only ``key_count`` + ``pubkeys[]``.
        """
        manifest = build_pubkey_manifest(generate_keypair())
        state = SignerFeedState(manifest=manifest)
        payload = state.as_dict()

        assert "feed_entities_count" in payload
        assert "feed_last_updated_timestamp" in payload
        assert "cycles_total" in payload
        assert "errors_total" in payload
        assert "generation" in payload
        assert payload["feed"] == "skills_signer"

    def test_record_cycle_bumps_counter_and_timestamp(self) -> None:
        manifest = build_pubkey_manifest(generate_keypair())
        state = SignerFeedState(manifest=manifest)

        before_ts = state.last_updated_timestamp
        before_cycles = state.cycles_total

        state.record_cycle()
        assert state.cycles_total == before_cycles + 1
        assert state.last_updated_timestamp >= before_ts

    def test_record_error_bumps_errors_total(self) -> None:
        manifest = build_pubkey_manifest(generate_keypair())
        state = SignerFeedState(manifest=manifest)

        state.record_error()
        state.record_error()
        assert state.errors_total == 2

    def test_503_payload_shape(self) -> None:
        """The /health endpoint expects ``bool(c.get("ok"))`` — verify shape."""
        manifest = build_pubkey_manifest(generate_keypair())
        state = SignerFeedState(manifest=manifest)
        payload = state.as_dict()
        # The /health endpoint uses ``all(bool(c.get("ok")) for c in checks.values())``
        # so the dict must have a top-level ``ok`` key that's truthy/falsy.
        assert "ok" in payload
        assert isinstance(payload["ok"], bool)
        assert payload["ok"] is True

        empty_state = SignerFeedState(manifest=PubkeyManifest())
        empty_payload = empty_state.as_dict()
        assert empty_payload["ok"] is False
