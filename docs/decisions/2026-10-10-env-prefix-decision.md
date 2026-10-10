# Env-var prefix decision for the Oneiric-backed MCP settings

Status: Active (R8 ruling recorded in the migration plan ledger; this commit codifies it.)
Date: 2026-10-10
Migration: `2026-10-10-crackerjack-oneiric-loader-migration`

## Context

`CrackerjackSettings` (`crackerjack/config/settings.py:485`) inherits from
`OneiricMCPConfig` (`oneiric/core/config.py:296-308`), which hard-codes:

```python
class OneiricMCPConfig(BaseModel):
    ...
    model_config = SettingsConfigDict(
        env_prefix="ONEIRIC_MCP_",
        env_file=".env",
        extra="allow",
    )
```

The README at line 1020 (`docs/audits/2026-09-09-crackerjack-docs-audit.md:139`)
asserts that the operator-facing contract is `CRACKERJACK_*` env vars. The
2026-09-09 docs audit flagged this as a drift item: docs claim `CRACKERJACK_*`,
the model wires `ONEIRIC_MCP_*`.

The migration spec §6.5 (per the task brief) flagged this as a potential
collision. Two resolutions are mathematically possible:

1. **Override `env_prefix` to `CRACKERJACK_MCP_` on a `_CrackerjackMCPConfig`
   subclass** of `OneiricMCPConfig`, and re-parent the ~38 settings classes
   in `crackerjack/config/settings.py` onto the subclass.
1. **Route `CRACKERJACK_*` env vars through an explicit overlay**, as
   Mahavishnu does at `mahavishnu/core/config.py:3209`.

A mechanical probe (subclassing `OneiricMCPConfig` with a new
`model_config = SettingsConfigDict(env_prefix="CRACKERJACK_MCP_", ...)`) shows
that pydantic-settings does honor the override — the subclass's `model_config`
takes the new prefix while the parent retains `ONEIRIC_MCP_`. Option B is
therefore mechanically feasible.

## Decision

Adopt Option 2 (explicit overlay, `_crackerjack_env_overlay`) and leave
`OneiricMCPConfig.env_prefix="ONEIRIC_MCP_"` unmodified for this migration.
Do **not** introduce `_CrackerjackMCPConfig(OneiricMCPConfig)`.

The `_crackerjack_env_overlay` helper at `crackerjack/config/loader.py:17-41`
walks `os.environ` for `CRACKERJACK_*` keys, strips the prefix, lowercases
the suffix, and merges per-key into the loaded dict (`_merge_env_overlay` at
`crackerjack/config/loader.py:44`). REQ-006 calls for layered precedence
(XDG → YAML → overlay), and the overlay is the last step in
`_main_cli.py`'s config-stack wiring (`crackerjack/config/loader.py:120`).

Adding the pydantic auto-binding for `CRACKERJACK_MCP_*` would create a
**dual-path** to the same fields — one path via the explicit overlay, one
via pydantic-settings' auto-binding. That duplicate path would conflict
with REQ-006's explicit layered precedence:

- pydantic-settings auto-binding happens *before* the loader finishes
  composing the dict from XDG + YAML, so the auto-bound values would be
  clobbered by the YAML merge (or, worse, would silently win over the
  XDG/user-local layer).
- It also re-parents 38 settings classes onto a new base, expanding the
  blast radius of every subsequent OneiricMCPConfig change.

The overlay is sufficient because:

1. `OneiricMCPConfig`'s `extra="allow"` means top-level `CRACKERJACK_*`
   keys without a matching field are silently dropped (verified via
   `crackerjack_env_overlay` returning `{}` for unknown keys such as
   `CRACKERJACK_LOG_LEVEL`).
1. Operators who hit a top-level field via env var get the exact value
   the loader computed from the layered precedence.

## Status

Active. The `_crackerjack_env_overlay` helper is the single, audited
mechanism for `CRACKERJACK_*` env vars. The 2026-09-09 docs audit drift
item at line 139 of `docs/audits/2026-09-09-crackerjack-docs-audit.md`
closes against this decision (the model `env_prefix` stays
`ONEIRIC_MCP_`, but operators only ever need to author `CRACKERJACK_*`
env vars because the overlay strips the prefix).

## Future work

If operator-facing docs grow to require per-MCP-config pydantic
auto-binding (Option B from spec §5.5), a follow-up PR should:

1. Introduce `_CrackerjackMCPConfig(OneiricMCPConfig)` with the new
   `env_prefix="CRACKERJACK_MCP_"`.
1. Re-parent the ~38 settings classes in `crackerjack/config/settings.py`.
1. Verify that pydantic-settings' auto-binding composition order does
   not violate REQ-006's layered precedence (XDG → YAML → env overlay).
1. Add an integration test that asserts pydantic-settings auto-binding
   matches `_crackerjack_env_overlay` for every declared top-level field
   (catch any field that diverges between the two paths).

Until then, the overlay carries the full operator-facing surface, and
the `OneiricMCPConfig` base class is shared with other Bodai MCP servers
without divergence.

## References

- `oneiric/core/config.py:296-308` — `OneiricMCPConfig` declaration
- `crackerjack/config/settings.py:485` — `CrackerjackSettings(OneiricMCPConfig)`
- `crackerjack/config/loader.py:17-41` — `crackerjack_env_overlay`
- `crackerjack/config/loader.py:120` — overlay applied as the final step
- `docs/audits/2026-09-09-crackerjack-docs-audit.md:139` — README drift item
- `mahavishnu/core/config.py:3209` — Mahavishnu's `_mahavishnu_env_overlay`
  (the surface this implementation mirrors)
