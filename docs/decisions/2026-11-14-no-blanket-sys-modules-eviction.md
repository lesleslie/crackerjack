# Do not evict `oneiric.*` from `sys.modules` between tests

**Date:** 2026-11-14

## Context

`tests/conftest_reset.py` has reset oneiric's cross-test state by deleting
every `sys.modules` entry whose name starts with `"oneiric"`, on the theory
that re-importing a module resets whatever state it holds. The function was
added in `dc705b65` (2026-05-23), when oneiric was a small local editable
package and its module-level state was mostly import-time singletons.

That is no longer sufficient, and it is actively harmful. Evicting a module
breaks the *identity* of the classes it defines:

- A module that was already imported keeps the **old** class object.
- A fresh import produces a **new** class object with the same name.
- Pydantic validates by `isinstance`, which compares identity.

The failure this produced was a `ValidationError` from `OneiricSettings()`:

```
observability
  Input should be a valid dictionary or instance of OTelStorageSettings
  [type=model_type, input_value=OTelStorageSettings(...), input_type=OTelStorageSettings]
auth
  Input should be a dictionary or an instance of OneiricMCPAuthConfig
  [type=dataclass_type, input_value=OneiricMCPAuthConfig(...), input_type=OneiricMCPAuthConfig]
```

The input type and the expected type have the *same name and the same
source file*. They are different class objects.

The mechanism is specific. `oneiric.core.config` is imported at collection
time, so its `observability` annotation resolved to the
`OTelStorageSettings` class of that generation. The eviction removed
`oneiric.adapters.observability.settings` from `sys.modules`, but
`crackerjack.runtime.oneiric_workflow` still held the **old**
`OneiricSettings` class, whose default factory performs a *fresh*
`from oneiric.adapters.observability.settings import OTelStorageSettings`
at call time -- and got the **new** generation.

## Decision rule

Reset oneiric's **state**, not its **modules**.

oneiric ships a targeted escape hatch for exactly this:
`oneiric.core.build_settings.clear_project_settings_cache()`, documented in
its own source as a "Test-only escape hatch". It clears the memoized
per-project settings model classes -- the only oneiric state the blanket
eviction was actually there for.

Two further oneiric module-level caches carry genuine per-test runtime
state and are reset explicitly:
`oneiric.core.resiliency._ADAPTIVE_RETRY_STATE` and
`oneiric.adapters.observability.embeddings._EMBED_CACHE`.

`oneiric.modes.base._MODE_REGISTRY` is deliberately **not** reset. It is a
permanent registry filled by `@register_mode` decorators at import time;
clearing it would leave mode resolution empty until the module happened to
be re-imported.

## Consequences

- `OneiricSettings()` constructs reliably inside a test session.
- The isolation the autouse fixture promised is preserved, through targeted
  resets instead of a module wipe.
- Any future oneiric module that grows module-level state must be added to
  `reset_oneiric_state()` explicitly. That is the trade: a list to maintain
  in exchange for class identity that survives a test session.

## Related

The same failure mode -- two class objects for one source file -- was hit
independently in `tests/adapters/test_provider_chain.py`, where the patch
target had to be `crackerjack.adapters.ai.unified.FallbackChain.from_settings`
rather than the `oneiric` module path. Recorded as a Ruling in
`oneiric/docs/plans/2026-10-11-move-llm-from-mcp-common-to-oneiric.md`.
