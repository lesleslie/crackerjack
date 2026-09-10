"""Deterministic JSON canonicalization for signature payloads.

All Bodai servers and clients MUST canonicalize SkillMetadata /
AgentMetadata instances using :func:`canonicalize_payload` before
signing or verifying. The wire format is canonicalized UTF-8 JSON
bytes — signatures are computed over those bytes only.

Canonicalization rules (intentionally simple):

- UTF-8 encoded
- ``json.dumps(obj, sort_keys=True, separators=(",", ":"))``
- No whitespace, sorted keys, no trailing newline
- ``ensure_ascii=False`` so non-ASCII strings round-trip cleanly

Pydantic v2 models are serialized via ``model_dump(mode="json")``
which coerces ``datetime``/``Decimal``/``UUID``/``Path``/``Enum``/
``frozenset`` to their JSON equivalents — without this, any
non-trivial schema addition would crash inside ``json.dumps`` with
an unhelpful ``TypeError``. Pydantic v1 (``BaseModel.dict()``) is
NOT supported; the duck-type guard matches only v2.

The function accepts a Pydantic v2 BaseModel, dict, list, or JSON-safe
primitive. Arbitrary callables / file handles / dataclasses that are
not Pydantic models are NOT supported — the caller is responsible for
converting to a JSON-safe representation first.

For SkillMetadata / AgentMetadata that include their own ``signature``
and ``server_pubkey_id`` fields, use
:func:`canonical_payload_for_signing` instead — it strips the
post-signing annotation fields before canonicalization so the
signature is not computed over itself.
"""

from __future__ import annotations

import json
from typing import Any

# Fields that, if present at the top level, MUST be stripped before
# signing. Including them in the canonical bytes would mean the client
# re-canonicalizing the *populated* metadata produces different bytes
# than the server signed → every install fails verification.
SIGNATURE_FIELDS_TO_STRIP: frozenset[str] = frozenset({"signature", "server_pubkey_id"})


def canonicalize_payload(payload: Any) -> bytes:
    """Return the canonical UTF-8 JSON byte string for ``payload``.

    Args:
        payload: a Pydantic v2 BaseModel, dict, list, or JSON-safe primitive.

    Returns:
        Canonical bytes (UTF-8). Two equivalent payloads always produce
        byte-identical output.

    Raises:
        TypeError: when ``payload`` contains non-JSON-serializable values
            after the Pydantic conversion.
    """
    if hasattr(payload, "model_dump"):
        # ``mode="json"`` coerces datetime/Decimal/UUID/Path/Enum/frozenset
        # to their JSON equivalents. Without it, ``json.dumps`` crashes
        # with ``TypeError`` the first time someone adds a non-primitive
        # field to the schema.
        payload = payload.model_dump(mode="json")
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_payload_for_signing(
    payload: Any,
    *,
    extra_exclude_keys: frozenset[str] | set[str] | None = None,
) -> bytes:
    """Strip post-signing annotation fields then canonicalize.

    Use this for any SkillMetadata / AgentMetadata that carries its
    own ``signature`` and ``server_pubkey_id`` fields. The fields are
    populated AFTER signing — including them in the canonical bytes
    means the server signs bytes that include the signature itself
    (circular), and any client re-canonicalizing the populated metadata
    produces different bytes than the server signed.

    Args:
        payload: same as :func:`canonicalize_payload`.
        extra_exclude_keys: additional top-level keys to strip beyond
            the default ``{"signature", "server_pubkey_id"}``.

    Returns:
        Canonical bytes (UTF-8) ready to pass to
        :meth:`crackerjack.skills_signer.sign.SkillsSigner.sign`.
    """
    if hasattr(payload, "model_dump"):
        dumped = payload.model_dump(mode="json")
    elif isinstance(payload, dict):
        dumped = dict(payload)
    elif isinstance(payload, list):
        # Lists at the top level cannot carry signature fields; just
        # canonicalize directly. Recursive stripping is intentionally
        # not implemented — the wire format keeps signature fields at
        # the top level only.
        dumped = list(payload)
    else:
        return canonicalize_payload(payload)

    if isinstance(dumped, dict):
        exclude = SIGNATURE_FIELDS_TO_STRIP
        if extra_exclude_keys:
            exclude = exclude | set(extra_exclude_keys)
        for key in exclude:
            dumped.pop(key, None)
        return canonicalize_payload(dumped)

    return canonicalize_payload(dumped)
