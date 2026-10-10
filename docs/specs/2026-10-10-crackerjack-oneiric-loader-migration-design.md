---
status: draft
date: 2026-10-10
last_reviewed: 2026-10-10
title: "Crackerjack Settings Loader — Migration to Oneiric"
topic: settings-resolution
kind: design
---

# Spec: Crackerjack Settings Loader — Migration to Oneiric

## 1. Outcome

When this ships, Crackerjack's runtime settings are resolved through Oneiric's
`load_settings(project_name="crackerjack")` instead of `crackerjack/config/loader.py`'s
hand-rolled loader. Operators get XDG-user-override resolution for free (matching
Mahavishnu and Session-Buddy), and Crackerjack stops carrying bespoke merge /
filter / precedence logic that drifted three times in 2026.

**Observable success signals**:

- `crackerjack config validate` reads `~/.config/crackerjack/local.yaml` when
  present and overrides `<project>/settings/crackerjack.yaml` (new behavior).
- `crackerjack/cli --help` boots in the same wall-clock time as the current
  hand-rolled loader (within ±10%; regression budget for the per-process
  `load_settings` call).
- No new `crackerjack/config/` import path required by callers — the public
  `crackerjack.config.load_settings` and `crackerjack.config.load_settings_async`
  signatures are preserved.

## 2. Goals

1. **Single resolution path**: every Crackerjack settings consumer reads through
   `oneiric.core.config.load_settings`. No dual-mode loader.
2. **Layered precedence parity with the fleet**: match Oneiric's documented
   resolution order (XDG user override → XDG user config → project local →
   project committed → code defaults).
3. **Preserve bespoke behaviors**: the four behaviors unique to
   `crackerjack/config/loader.py` (env-var overlay, ecosystem publish
   synthesis, `*_timeout` reshape, `[tool.crackerjack.X]` sub-table validator)
   continue to fire — host in Pydantic `model_validator`s, not in the loader.
4. **Eliminate ~290 lines of loader glue**: net code reduction in
   `crackerjack/config/loader.py` once the public surface is preserved.

## 3. Non-Goals

1. **Migrating Bodai ecosystem components other than Crackerjack** (Akosha,
   Session-Buddy, Dhara, mcp-common). Each owns its loader; this spec is
   scoped to Crackerjack because the asymmetry was called out for it.
2. **Replacing `crackerjack/config/profile_loader.py`** (ProfileConfig,
   ProfileLoader). Profile loading is a separate concern (hook profile
   selection), not operator settings resolution.
3. **Changing the `OneiricMCPConfig` schema base** — already in place; the
   migration only changes the loader.
4. **Renaming `OneiricMCPConfig` to `CrackerjackMCPConfig`**. The naming
   mismatch is documented in `docs/audits/2026-09-09-crackerjack-docs-audit.md:139`
   but a rename is out of scope; the migration picks an env-var prefix
   strategy instead (see §6.5).
5. **Async loader semantics changes** beyond what Oneiric's `load_settings`
   provides. The current `load_settings_async` is a thin async wrapper
   around the sync loader — its tests cover semantics that survive the
   refactor.

## 4. Current Findings

**The asymmetry**

Crackerjack uses Oneiric's schema base but a hand-rolled loader:

| Layer | Crackerjack today | Mahavishnu (reference) | Citation |
|---|---|---|---|
| Schema base | `OneiricMCPConfig` (imported from `oneiric.core.config`) | `pydantic_settings.BaseSettings` + Oneiric extras | `crackerjack/config/settings.py:6`, `mahavishnu/core/config.py:22` |
| Resolution | Hand-rolled (`yaml.safe_load` + `tomllib.load` + manual merge + filter) | Delegates to `oneiric.core.config.load_settings(project_name="mahavishnu")` | `crackerjack/config/loader.py:34-205`, `mahavishnu/core/config.py:3153` |
| MCP bridge | `CrackerjackMCPSettings.load_for_crackerjack()` → calls hand-rolled `crackerjack.config.load_settings` | Routes through MahavishnuSettings → Oneiric | `crackerjack/config/mcp_settings_adapter.py:32-36` |

**Confirmation via CHANGELOG**

`crackerjack/CHANGELOG.md:1351` records an earlier partial migration:
"Migrate 37 settings classes to OneiricMCPConfig". The loader was
deliberately *not* part of that migration. The 2026-09-29 Mahavishnu
migration (commit history at `mahavishnu/core/config.py:3134`) is the
working template this spec re-uses.

**Call-site inventory (blast radius — 18 files reference `load_settings`,
7 reference the loader module directly)**

Production call sites (must keep public API stable):

- `crackerjack/config/__init__.py:16` — re-exports `load_settings`, `load_settings_async`
- `crackerjack/config/__init__.py:54` — module-level `settings_instance = load_settings(CrackerjackSettings)`
- `crackerjack/config/mcp_settings_adapter.py:32-35` — `load_for_crackerjack()` factory
- `crackerjack/core/phase_coordinator.py`, `crackerjack/managers/test_executor.py`
- `crackerjack/services/{config_cleanup,doc_update_service,documentation_cleanup,git_cleanup_service,unified_config}.py`
- `crackerjack/models/config.py`
- `crackerjack/mcp/tools/{utility_tools,core_tools}.py`
- `crackerjack/adapters/_tool_adapter_base.py`
- `crackerjack/cli/handlers/main_handlers.py`
- `crackerjack/config/global_lock_config.py`
- `crackerjack/services/logging.py` (likely; check during implement)
- `crackerjack/plugins/{__init__,managers}.py`
- `crackerjack/config/ecosystem_synthesis.py:187` (in-loader call site)
- `crackerjack/cli/handlers/changelog.py`
- `crackerjack/mcp/server_core.py`

Test call sites (must rewrite against public surface):

- `tests/config/test_loader.py` — imports 13 private symbols + `load_settings`/`load_settings_async` (the largest surface to update)
- `tests/unit/test_config_settings.py`, `tests/unit/config/test_hooks.py`
- `tests/test_config_cleanup_drift_repair.py`
- `tests/unit/{shell,managers,cli/handlers,executors,fixers}/...` (multi)

**Bespoke behaviors that must survive**

1. **`_validate_pyproject_subtables`** (`crackerjack/config/loader.py:78-108`)
   Warns on `[tool.crackerjack.X]` blocks that Crackerjack does not read.
   Without this, operators can silently write a `pyproject.toml` block
   expecting it to configure a hook and get no effect. Currently a
   loader-side concern.

2. **`_extract_adapter_timeouts`** (`crackerjack/config/loader.py:65-75`)
   Reshapes `*_timeout` top-level keys into a nested
   `adapter_timeouts.{*_timeout}` sub-dict. The timing matters — must run
   *before* the `[tool.crackerjack.adapter_timeouts]` validation check
   (so the synthesised sub-dict isn't mistaken for a user-written block).

3. **`apply_ecosystem_publish_synthesis`** (called at `crackerjack/config/loader.py:189`)
   Reads `BODAI_ECOSYSTEM_CONFIG` (typically `settings/ecosystem.yaml` in
   the Mahavishnu repo) and synthesises a missing `publishing.publish_url`
   for the cwd-matching repo. Priority slot: between CLI/env vars and
   YAML, per `crackerjack/config/ecosystem_synthesis.py:18-23`.

4. **Env-var overlay** (Oneiric's `env_prefix="ONEIRIC_"` would apply to
   Crackerjack unless overridden — see §6.5).

## 4.5 Requirements

```yaml
requirements:
  - id: REQ-001
    title: "Crackerjack settings resolve through Oneiric's load_settings"
  - id: REQ-002
    title: "Public load_settings / load_settings_async API preserved"
  - id: REQ-003
    title: "[tool.crackerjack.X] validation migrates to Pydantic model_validator"
  - id: REQ-004
    title: "adapter_timeouts reshape migrates to Pydantic model_validator"
  - id: REQ-005
    title: "Ecosystem publish_url synthesis runs at Oneiric-equivalent precedence slot"
  - id: REQ-006
    title: "Env-var overlay applies CRACKERJACK_* env vars over YAML (decision documented)"
  - id: REQ-007
    title: "Loader behavior preserved under test coverage >= current test count for loader paths"
```

## 5. Design

### 5.1 Public surface

`crackerjack.config.load_settings` and `crackerjack.config.load_settings_async`
**drop the legacy `settings_dir` parameter** in this migration. New signature:

```python
def load_settings(settings_class: type[T]) -> T: ...
async def load_settings_async(settings_class: type[T]) -> T: ...
```

The pre-migration signature accepted `settings_dir: Path | None`; the new
factory anchors the project root at `Path.cwd()` and delegates to
`oneiric.core.config.load_settings(project_name="crackerjack", project_root=cwd)`.
Per Bodai pre-1.0 policy (`~/.claude/.../feedback-no-backwards-compat-pre-1.0.md`)
we replace rather than extend. The 18 known production call sites already
invoke `load_settings(CrackerjackSettings)` with no arguments — see the
call-site inventory below.

### 5.2 Factory body (the new `load_settings`)

```python
from oneiric.core.config import load_settings as _oneiric_load
from .ecosystem_synthesis import apply_ecosystem_publish_synthesis
from .validators import AdapterTimeoutsValidator, PyprojectSubtableValidator

def load_settings(settings_class):
    anchor = Path.cwd()
    oneiric_obj = _oneiric_load(
        project_name="crackerjack",
        project_root=anchor,
    )
    extras = getattr(oneiric_obj, "__pydantic_extra__", None) or {}
    merged = {k: v for k, v in extras.items()
              if k in settings_class.model_fields and v is not None}
    # Apply ecosystem synthesis between Oneiric resolution and env-var
    # overlay, matching the loader's current priority slot.
    apply_ecosystem_publish_synthesis(merged, anchor)
    # Apply CRACKERJACK_* env overlay (after Oneiric, before Pydantic).
    _crackerjack_env_overlay(merged)
    return settings_class(**merged)
```

The `_crackerjack_env_overlay` helper mirrors Mahavishnu's
`_mahavishnu_env_overlay` at `mahavishnu/core/config.py:3209`: walk
`os.environ` for `CRACKERJACK_*` keys, map to nested dicts via `__`
delimiter, then merge per-key to keep siblings intact.

### 5.3 Behaviors → validators

The two bespoke behaviors in `loader.py` move to Pydantic
`model_validator`s on `CrackerjackSettings`:

```python
# crackerjack/config/settings.py (additions)
class CrackerjackSettings(OneiricMCPConfig):
    ...existing fields...

    @model_validator(mode="before")
    @classmethod
    def _reshape_adapter_timeouts(cls, data: t.Any) -> t.Any:
        """Reshape ``*_timeout`` scalars into nested ``adapter_timeouts``. REQ-004."""
        if isinstance(data, dict):
            timeouts = {k: v for k, v in data.items() if k.endswith("_timeout")}
            if timeouts:
                data.setdefault("adapter_timeouts", {}).update(timeouts)
                for k in timeouts:
                    data.pop(k, None)
        return data

    @model_validator(mode="after")
    def _warn_unknown_pyproject_subtables(self) -> "CrackerjackSettings":
        """Surface misplaced [tool.crackerjack.X] blocks at WARNING. REQ-003."""
        for key in type(self).model_fields:
            ...iterate sub-configs and warn on unknown sub-dict keys...
        return self
```

The `_validate_pyproject_subtables` mechanism in the current loader
operates on the raw dict read from `pyproject.toml`'s
`[tool.crackerjack.X]`. The new validator must read `pyproject.toml`
itself because by the time `model_validator(mode="after")` runs, the
flat pyproject data has been merged into model fields. This is a small
loss of fidelity (we lose the loader's pre-merge inspection) but it's
still actionable — any sub-table the model doesn't declare surfaces as
a warning.

**Trade-off accepted**: the warning text moves from "block in
pyproject.toml is not read" to "sub-table on `CrackerjackSettings` is
not declared". Same operator-facing signal, slightly different shape.

### 5.4 Async path

`load_settings_async` becomes a thin `asyncio.to_thread(load_settings, ...)`
wrapper. Behavior parity preserved (the current async path uses
`yaml.safe_load` inside `asyncio.to_thread`-style loops already).

### 5.5 Env-var prefix decision

Two options on the table:

**Option A (recommended)**: keep `OneiricMCPConfig` as the base class,
overriding `model_config.env_prefix = "CRACKERJACK_MCP_"`. Oneiric's
`load_settings` will load YAML + XDG layers; the explicit
`_crackerjack_env_overlay` applies `CRACKERJACK_*` env vars after Oneiric
parses its own `ONEIRIC_*` overrides. The `ONEIRIC_MCP_*` env vars
documented in `crackerjack/docs/audits/2026-09-09-crackerjack-docs-audit.md:139`
become moot for Crackerjack-specific keys.

**Option B**: define `class CrackerjackMCPConfig(OneiricMCPConfig)`
with `env_prefix="CRACKERJACK_MCP_"`. Switch all 37 settings classes
to inherit from `CrackerjackMCPConfig`. Larger diff, cleaner naming.

The plan picks Option A. Reasoning: Option B's rename is a documentation
follow-up, not a loader concern; the env prefix can be supplied as a
`model_config` override on `OneiricMCPConfig` without proliferating
classes.

## 6. Required Code Changes

(Detailed file-by-file changes live in the implementation plan.)

## 7. Validation Matrix

| Check | Command | Expected outcome |
|---|---|---|
| Public surface preserved | `crackerjack config validate` with settings/local.yaml | exit 0, log shows Oneiric resolution path |
| Async parity | `pytest tests/config/test_loader.py::test_load_settings_async_smoke -v` | PASS |
| Sub-table validator | unit test that injects `[tool.crackerjack.betterleaks]` and inspects warning | WARNING emitted |
| Timeout reshape | unit test passing `{"ruff_timeout": 60}` | `settings.adapter_timeouts.ruff_timeout == 60` |
| XDG precedence | `~/.config/crackerjack/local.yaml` overrides `settings/local.yaml` | confirmed via test |
| Ecosystem synthesis | unit test with `BODAI_ECOSYSTEM_CONFIG` env | `settings.publishing.publish_url` populated |

## 8. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Oneiric unavailable during import (test envs without the dep) | Low | Mirror Mahavishnu's `try/except ... logger.exception(...); fall back to defaults + env-var-only` pattern at `mahavishnu/core/config.py:3192-3199` |
| Backward-compat alias swallows CRACKERJACK_* env vars (Mahavishnu hit `LOG_LEVEL → logging.level` at `oneiric/core/config.py:702`) | Medium | Audit `oneiric.core.config` backward-compat aliases before merging; explicitly apply CRACKERJACK_* overlay AFTER Oneiric parsing per §5.2 |
| Private-symbol tests break (13 imports in `tests/config/test_loader.py:7-21`) | High | Rewrite to test through public surface (`load_settings`) and model validators; preserve count of behavior-coverage tests |
| `__test__ = False` flag on `TestSettings` survives | Low | Verify in plan's first task |
| Settings classes use `extra="allow"` shape that Oneiric's extras-filter strips | Medium | Audit each of the 37 settings classes for declared top-level vs nested fields; reject any field declared in `CrackerjackSettings` that isn't delivered by Oneiric |
| Operators relying on `settings_dir=Path.cwd() / "settings"` heuristic | Low | Accept the new anchor (`project_root=anchor`) and keep `settings_dir` parameter as a backward-compat no-op for the first release; deprecate in plan §6.5 |

## 9. Decision Rule (cut-off)

The migration is "done enough" when:
- All call sites compile and run on `load_settings` (resolution parity),
- Tests in `tests/config/test_loader.py` are rewritten to test through the public surface with behavior parity (or strictly more coverage),
- The 4 bespoke behaviors fire (env overlay, ecosystem synthesis, timeout reshape, sub-table validator),
- `crackerjack config validate` exits 0 on a fresh checkout with no `local.yaml` and 0 on a checkout with valid `local.yaml`,
- `crackerjack docs` and `MEMORY_ARCHITECTURE.md` §1277/§1346 reflect Oneiric as the resolver.

Out of scope for this cut: the `CRACKERJACK_*` env-var audit (Doc fix only,
separate PR), `Option B` rename, and async-cache-tier refactors.
