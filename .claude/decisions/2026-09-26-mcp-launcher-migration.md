---
status: active
role: implementation
kind: migration-design
date: 2026-09-26
last_reviewed: 2026-09-26
superseded_by: null
topic: mcp-launcher-migration
parent_plan: /Users/les/Projects/mahavishnu/docs/plans/2026-09-26-mcp-launcher-standardization.md
cookbook_example: /Users/les/Projects/mcp-common/docs/mcp/launcher-cookbook.md#example-4-cj-crackerjack-no-auth-no-settings--closure-passes-auth_confignone
---

# Crackerjack MCP Launcher Migration (Phase 4a, Task 4a.2)

> **Design note for the implementer agent.** READ-ONLY investigation; no source
> changes made. This document sketches the migration of crackerjack's MCP server
> startup from the bespoke `_run_mcp_server` path to the canonical
> `mcp_common.server.launcher.launch()` helper. The implementer will execute
> the change in Phase 4a per the parent plan.

## 1. Current state

### 1.1 Entry-point chain

```
~/Library/LaunchAgents/com.mcp.crackerjack.plist
    → /Users/les/.local/state/mcp/scripts/launch_with_healthcheck.sh
        (URL: http://127.0.0.1:8676/health, --timeout 60)
    → /Users/les/Projects/crackerjack/.venv/bin/python
    → -m crackerjack.mcp.server_core
        → module-level `if __name__ == "__main__":` (line 613)
        → main(project_path, http_mode, http_port)
            → _initialize_project_and_config()    [loads pyproject.toml]
            → _setup_server_context()             [MCPServerContext]
            → _create_and_validate_server()       [asyncio.run(create_mcp_server)]
            → _show_server_startup_info()         [ServerPanels]
            → write_runtime_health() / write_pid_file()
            → _run_mcp_server(mcp_app, mcp_config, http_mode)   ← MIGRATION TARGET
```

### 1.2 What each piece does

| File | LOC | Role |
|---|---|---|
| `crackerjack/mcp/server_core.py` | 629 | FastMCP factory + stdio/HTTP run loop |
| `crackerjack/cli/mcp_cli.py` | 638 | Typer `crackerjack mcp {start,stop,status,restart,health}` (Popen-based) |
| `~/Library/LaunchAgents/com.mcp.crackerjack.plist` | 86 | launchd supervision (KeepAlive on crash) |
| `/Users/les/.local/state/mcp/scripts/launch_with_healthcheck.sh` | (existing) | Pre-launch health probe; not part of this migration |

### 1.3 The migration target: `_run_mcp_server` (lines 480-509, 30 LOC)

```python
def _run_mcp_server(mcp_app, mcp_config, http_mode) -> None:
    console.print("[yellow]MCP app created, about to run...[/yellow]")
    try:
        if mcp_config.get("http_enabled", False) or http_mode:
            host = mcp_config.get("http_host", "127.0.0.1")
            port = mcp_config.get("http_port", 8676)
            asyncio.run(
                mcp_app.run_http_async(
                    host=host, port=port,
                    uvicorn_config={"timeout_graceful_shutdown": 30},
                )
            )
        else:
            mcp_app.run()
    except Exception as e:
        console.print(f"[red]MCP run failed: {e}[/red]")
        import traceback; traceback.print_exc(); raise
```

### 1.4 Verified facts (read at investigation time)

| Fact | Value | Evidence |
|---|---|---|
| FastMCP factory function name | `create_mcp_server` | `server_core.py:126` |
| Factory sync or async? | **ASYNC** (`async def`) | `server_core.py:126` |
| Factory signature | `async def create_mcp_server(config: dict[str, t.Any] \| None = None) -> t.Any \| None` | `server_core.py:126-128` |
| `auth_config` kwarg in factory? | **NO** (per the plan's "cj has no auth" claim) | `server_core.py:126` — only `config` |
| Existing `/health` route? | YES — inline `@mcp_app.custom_route("/health", methods=["GET"])` | `server_core.py:151-199` |
| Existing `/health` includes `"launcher"` field? | **NO** (REQ-005 gap) | `server_core.py:152-199` (no `"launcher"` key) |
| `register_http_health_route` used? | **NO** — custom route inline instead | `server_core.py:151` (decorator) vs. `mcp_common/health/__init__.py:836` (helper exists) |
| Existing `/health` returns 503 on degraded? | YES (custom semantics, NOT the mcp-common helper's "always 200") | `server_core.py:174, 189` |
| Plist invocation shape | `/Users/les/.Projects/crackerjack/.venv/bin/python -m crackerjack.mcp.server_core` | `com.mcp.crackerjack.plist:17-19` |
| Plist pre-launch wrapper? | YES — `launch_with_healthcheck.sh http://127.0.0.1:8676/health --timeout 60 --` | `com.mcp.crackerjack.plist:11-16` |
| CLI `crackerjack mcp start` shape | `subprocess.Popen([sys.executable, "-m", "crackerjack.mcp.server_core"], ...)` | `mcp_cli.py:177-186` |
| Server already built when `_run_mcp_server` is called? | **YES** — `main()` builds `mcp_app = asyncio.run(create_mcp_server(mcp_config))` at `_create_and_validate_server` then passes it down | `server_core.py:524, 569, 589` |

## 2. Target state

### 2.1 What `_run_mcp_server` becomes

Replace the manual `asyncio.run(mcp_app.run_http_async(host=, port=, uvicorn_config={"timeout_graceful_shutdown": 30}))` block with a `launch(...)` call. **Keep the pre-built `mcp_app`** (built upstream in `main()` via `asyncio.run(create_mcp_server(...))`) so the closure is sync and the nested-event-loop trap is avoided entirely.

```python
# crackerjack/mcp/server_core.py:_run_mcp_server — REPLACEMENT
def _run_mcp_server(mcp_app, mcp_config, http_mode) -> None:
    """Run the FastMCP server via mcp_common.server.launcher (REQ-001..005, REQ-013).

    HTTP mode → delegated to the canonical launcher.
    STDIO mode → kept as-is (launcher is HTTP-only).
    """
    if not (mcp_config.get("http_enabled", False) or http_mode):
        # Launcher only handles HTTP transport; STDIO path stays local.
        mcp_app.run()
        return

    host = mcp_config.get("http_host", "127.0.0.1")
    port = mcp_config.get("http_port", 8676)

    from mcp_common.server import launch

    def build_server():
        """Closure: returns the pre-built FastMCP app. build_server() takes no args.

        cj pre-builds mcp_app in main() via _create_and_validate_server
        (asyncio.run(create_mcp_server(...))) before this function is called,
        so the closure just returns the already-constructed instance — no
        nested-event-loop bridge required.
        """
        return mcp_app

    asyncio.run(
        launch(
            build_server=build_server,
            component_name="crackerjack",
            # cj has no auth subsystem → no secrets.env pre-bind (REQ-002 opt-out):
            secrets_path=None,
            # cj has no settings.yaml → launcher skips warm_settings_feed (REQ-004):
            settings_path=None,
            host=host,
            port=port,
        )
    )
```

**Why pre-build instead of recreating inside the closure:**
- `create_mcp_server` is **async** (`async def`, line 126 of server_core.py).
- The launcher's `build_server: Callable[..., Any]` is called **sync** from inside `launch()`'s async context.
- The cookbook Example 4 (`/Users/les/Projects/mcp-common/docs/mcp/launcher-cookbook.md:467-507`) suggests `asyncio.get_event_loop().run_until_complete(...)` inside the closure, but **this pattern is BUGGY** when called from a running loop — `run_until_complete()` raises `RuntimeError: This event loop is already running.` (Python 3.10+).
- Pre-building `mcp_app` upstream (where `main()` already calls `asyncio.run(create_mcp_server(mcp_config))`) sidesteps the nested-loop trap entirely. The closure becomes a trivial `return mcp_app`.

### 2.2 STDIO mode

The current `_run_mcp_server` falls back to `mcp_app.run()` (no HTTP). The launcher's `launch()` is HTTP-only (`run_with_uvicorn_config` pins `transport="http"`). **STDIO mode stays as-is** — do not delegate to the launcher for the stdio path. Document this in the commit message.

### 2.3 What gets DELETED from `_run_mcp_server`

- The `asyncio.run(mcp_app.run_http_async(host=, port=, uvicorn_config={"timeout_graceful_shutdown": 30}))` block — replaced by `asyncio.run(launch(build_server=..., ...))`.
- The `# Override FastMCP's hardcoded 2s graceful-shutdown timeout` comment — the launcher now owns this guarantee (REQ-007).

**Stays as-is:**
- STDIO branch (`mcp_app.run()`).
- The `try / except` with `console.print` + `traceback.print_exc()` (the launcher's exceptions still propagate to this handler).
- All of `main()`, `_initialize_project_and_config()`, `_setup_server_context()`, `_create_and_validate_server()`, `_show_server_startup_info()`, the `RuntimeHealthSnapshot` write, the PID file write.

### 2.4 What changes in `create_mcp_server` (the FastMCP factory, REQ-005)

The factory itself is unchanged — but the **inline `/health` route** (lines 151-199) needs the `"launcher"` field added per REQ-005:

```python
# Inside create_mcp_server, replace the health_check body with:

import mcp_common  # added at module top
from importlib.metadata import version as _pkg_version
try:
    _MCP_COMMON_VERSION = _pkg_version("mcp-common")
except Exception:
    _MCP_COMMON_VERSION = "unknown"

@mcp_app.custom_route("/health", methods=["GET"])
async def health_check(request):
    from starlette.responses import JSONResponse
    from crackerjack.mcp.signer_feed import get_signer_feed_state

    state = get_signer_feed_state()
    base = {
        "service": "crackerjack",
        "version": __version__,
        "launcher": f"mcp_common.server.launcher@{_MCP_COMMON_VERSION}",
    }
    if state is None:
        return JSONResponse(
            {**base, "status": "degraded",
             "checks": {"skills_signer": {"ok": False, "error": "not initialized"}}},
            status_code=503,
        )
    signer_dict = state.as_dict()
    signer_ok = bool(signer_dict.get("ok"))
    if not signer_ok:
        return JSONResponse(
            {**base, "status": "degraded",
             "checks": {"skills_signer": signer_dict}},
            status_code=503,
        )
    return JSONResponse(
        {**base, "status": "ok",
         "checks": {"skills_signer": signer_dict}},
    )
```

**Do NOT replace the custom route with `mcp_common.health.register_http_health_route`** — the existing route has crackerjack-specific semantics (degraded → 503, signer feed wiring) that the generic helper does not provide. The generic helper unconditionally returns 200 (per `mcp_common/health/__init__.py:899-908`), which would change cj's external /health contract.

### 2.5 Why not register `register_http_health_route`?

| Question | Answer |
|---|---|
| Is `register_http_health_route` generic enough? | Yes — but it has different return semantics (always 200, no signer-feed awareness) |
| Does it satisfy REQ-005 by emitting `"launcher"`? | **NO** — it emits `{"status", "service", "version", "components"}` but no `"launcher"` field |
| Is the crackerjack `/health` more specialized than the generic helper? | Yes — it surfaces the `skills_signer` feed state with 503 on degraded |
| Recommendation | **Keep the custom inline route + add the `"launcher"` field manually.** REQ-005 is a consumer-side contract, not a launcher-side enforcement. |

## 3. Migration steps

### A. Verify API (factual, not a step)

| Question | Answer |
|---|---|
| Is `create_mcp_server` sync or async? | **ASYNC** (verified `async def`, line 126) |
| Does it accept `auth_config`? | **NO** — only `config: dict[str, t.Any] \| None = None` (verified line 126) |
| Does the existing `/health` route inject `"launcher"`? | **NO** (REQ-005 gap — needs adding) |

### B. Refactor `_run_mcp_server`

Replace the body per §2.1 above. Net LOC change: roughly flat (30 LOC → ~35 LOC including the import + docstring), but the manual `run_http_async` call is gone.

### C. Add the `"launcher"` field to the inline `/health` route

Per §2.4 above. Modify `create_mcp_server` to include the field in all three response branches (degraded-not-init, degraded-signer-bad, ok). Read `mcp_common.__version__` at request time (not module-import time) so editable-install version drift doesn't lie.

### D. launchd plist — NO CHANGE

The plist invokes `python -m crackerjack.mcp.server_core` directly, which routes to `main()` → `_run_mcp_server()`. Since we modify `_run_mcp_server` in-place, the plist stays exactly as-is. The `launch_with_healthcheck.sh` pre-launch probe is independent of this migration.

### E. CLI `crackerjack mcp start` — NO CHANGE

`mcp_cli.py:177-186` spawns `[sys.executable, "-m", "crackerjack.mcp.server_core"]` via `subprocess.Popen` with `start_new_session=True`. The migration does not change the entry point — it changes what the entry point does internally. Backwards compat preserved.

### F. Smoke test (per REQ-005, REQ-014)

```bash
launchctl unload ~/Library/LaunchAgents/com.mcp.crackerjack.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.mcp.crackerjack.plist
sleep 5
curl -fsS http://127.0.0.1:8676/health | jq '.status, .launcher, .checks.skills_signer.ok'
# Expect:
#   "ok"
#   "mcp_common.server.launcher@<version>"
#   true

# Signal-handling smoke (REQ-014):
PID=$(curl -fsS http://127.0.0.1:8676/health >/dev/null; pgrep -f 'crackerjack.mcp.server_core' | head -1)
kill -TERM "$PID"
# Expect: exit code 0 within timeout_graceful_shutdown (30s) + 5s
```

### G. Backward Compatibility Test Matrix row for cj (REQ-013)

| Public surface | Before migration | After migration | Status |
|---|---|---|---|
| `crackerjack mcp start` (Typer, `cli/mcp_cli.py`) | Popen of `python -m crackerjack.mcp.server_core` | unchanged | green |
| `crackerjack mcp stop` | SIGTERM via PID file `/tmp/crackerjack-mcp.pid` | unchanged | green |
| `crackerjack mcp status` | reads PID file | unchanged | green |
| `crackerjack mcp restart` | stop + start | unchanged | green |
| `crackerjack mcp health` (with `--probe`) | hits `http://localhost: 8676/health` (note: literal space — pre-existing typo at `mcp_cli.py:27`) | unchanged | green |
| launchd plist `ProgramArguments` | `[wrapper.sh, /health, --timeout 60, --, python, -m, crackerjack.mcp.server_core]` | unchanged | green |
| `/health` body shape | `{status, service, version, checks.skills_signer}` | **additive**: + `"launcher"` field | green |
| `/health` HTTP status on degraded | 503 | unchanged | green |
| `/health` HTTP status on healthy | 200 | unchanged | green |
| `/healthz` (alias route) | `{status: ok}` 200 | unchanged | green |
| STDIO mode (`mcp_app.run()`) | unchanged | unchanged | green |

## 4. Risks

### R1. Cookbook Example 4's `asyncio.get_event_loop().run_until_complete(...)` is buggy

The cookbook (`launcher-cookbook.md:482-486`) shows:

```python
def build_server():
    server = asyncio.get_event_loop().run_until_complete(create_mcp_server(mcp_config))
    return server
```

But `launch()` calls `build_server()` from inside its own async context, where a loop is already running. `asyncio.get_event_loop().run_until_complete()` raises `RuntimeError: This event loop is already running.` (Python 3.10+). The cookbook's Example 4 would crash at runtime.

**Mitigation:** The pre-build pattern (this design note §2.1) sidesteps the trap. `mcp_app` is built upstream in `main()` via `_create_and_validate_server` (which already calls `asyncio.run(create_mcp_server(mcp_config))`); the closure just returns it.

**Trap to surface in the implementer brief:** if the implementer copy-pastes the cookbook's `asyncio.get_event_loop().run_until_complete(...)` pattern, the migration will silently break. Recommend pre-build.

### R2. No settings.yaml → no `settings` feed pre-warm → cj /health may report 503

The launcher pre-warms the `settings` feed with `entities_count > 0` so `/health=200` on first probe (REQ-004). cj has no settings.yaml, so `settings_path=None` → launcher skips `warm_settings_feed` → no `settings` feed exists.

**cj's `/health` route is independent of the `settings` feed.** It reads `crackerjack.mcp.signer_feed.get_signer_feed_state()` (a per-component feed). So the lack of a `settings` feed does not affect cj's /health.

**Verify at smoke time:** `curl /health | jq .checks` should show `skills_signer` (the per-component feed), not `settings`. If the implementer swaps to `register_http_health_route`, the body shape changes and the migration breaks the wire contract.

**Acceptable:** Yes — cj is a code-quality tool, MCP clients don't call it for `/health` for routing decisions. The plan §4 "Wire-up contract" goal is per-component, and cj's `skills_signer` feed already satisfies it.

### R3. `create_mcp_server` is async — bridge concerns

Documented in §R1. The pre-build pattern eliminates the bridge entirely. **Risk resolved** by the pre-build choice.

### R4. REQ-005 (`"launcher"` field on /health) is consumer-side, not launcher-side

The launcher doesn't write to `/health`. The crackerjack `/health` route handler must include `"launcher": f"mcp_common.server.launcher@{mcp_common.__version__}"` itself. Without this, the migration satisfies REQ-001, REQ-007, REQ-013 but **NOT REQ-005**.

**Mitigation:** §2.4 above — modify the existing inline `/health` route to include the field. The cookbook example doesn't show this step explicitly for cj, so the implementer needs this design note as the explicit guidance.

### R5. cj's `/health` returns 503 on degraded (not 200 like the generic helper)

This is a deliberate wire contract. `register_http_health_route` returns 200 unconditionally (per `mcp_common/health/__init__.py:899-908`). If the implementer replaces the custom route with the helper, the 503-on-degraded contract breaks and load balancers may mis-route.

**Mitigation:** Do NOT replace the custom route. Add the `"launcher"` field manually (§2.4).

### R6. SIGTERM return-code contract

Per cookbook's failure-modes table (`launcher-cookbook.md:561`), vanilla FastMCP/uvicorn exits with `returncode=-15` on SIGTERM, NOT 0. The cookbook recommends `signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))` BEFORE `launch(...)` so REQ-014 holds.

**Mitigation:** Add the explicit SIGTERM handler inside the `if HTTP-mode:` branch of `_run_mcp_server`, before the `launch(...)` call:

```python
import signal
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
```

### R7. `mcp-common>=0.28.0` not yet released

Per `feedback-mcp-common-version-bump-is-user.md`, the mcp-common version bump is user-owned. If this migration lands before mcp-common 0.28.0 is published, the import `from mcp_common.server import launch` will fail.

**Mitigation:** Coordinate the version bump. The crackerjack commit should land AFTER mcp-common 0.28.0 is on PyPI. If coordination fails, gate with `try: from mcp_common.server import launch except ImportError: ...` (fallback to the existing `_run_mcp_server` body).

### R8. Plist `launch_with_healthcheck.sh` pre-launch probe

The plist's wrapper script polls `http://127.0.0.1:8676/health --timeout 60` before launching. The wrapper is independent of this migration. No action needed.

## 5. Acceptance gates

Five-gate pattern from the vishnu design note:

| # | Gate | Command | Pass criterion |
|---|---|---|---|
| 1 | mcp-common launcher importable | `python -c "from mcp_common.server import launch"` | Exit 0, no ImportError |
| 2 | crackerjack module imports cleanly | `python -c "import crackerjack.mcp.server_core"` | Exit 0 |
| 3 | `main()` is callable (smoke) | `python -m crackerjack.mcp.server_core . --http` (foreground) | Server starts, binds 8676, /health responds |
| 4 | `curl /health` returns 200 with `"launcher"` field | `curl -fsS http://127.0.0.1:8676/health \| jq '.status, .launcher'` | `"ok"`, `"mcp_common.server.launcher@<version>"` |
| 5 | ruff clean | `crackerjack run` (or `ruff check crackerjack/mcp/server_core.py`) | Exit 0 |

## 6. Commit sketch

Per the parent plan §5 Phase 4a Task 4a.3 and `feedback-mcp-common-version-bump-is-user.md`:

```bash
# Inside crackerjack repo (the version is unchanged; user bumps via crackerjack run -p minor):
git -c user.email=les@wedgwoodwebworks.com -c user.name=les \
    add crackerjack/mcp/server_core.py
git -c user.email=les@wedgwoodwebworks.com -c user.name=les \
    commit -m "feat(crackerjack): migrate MCP server startup to mcp-common launcher (REQ-013)

Replace manual mcp_app.run_http_async(host=, port=, uvicorn_config={...})
call in _run_mcp_server with mcp_common.server.launcher.launch().

* cj has no auth subsystem (secrets_path=None) and no settings.yaml
  consumed by the launcher (settings_path=None); both opt-outs are
  explicit per REQ-002/REQ-004.
* The pre-built mcp_app is returned from build_server() — avoids the
  nested-event-loop trap that cookbook Example 4 hits with
  asyncio.get_event_loop().run_until_complete(...) (see R1 in
  .claude/decisions/2026-09-26-mcp-launcher-migration.md).
* The inline /health route adds a 'launcher' field per REQ-005
  (read mcp_common.__version__ at request time).
* STDIO mode (mcp_app.run()) stays as-is; the launcher is HTTP-only.
* launchd plist + 'crackerjack mcp start' CLI surface unchanged.
* SIGTERM handler installed before launch() so REQ-014 holds.

Verified: curl /health returns 200 with launcher field; degraded 503
preserved; existing /healthz alias untouched.

See: mahavishnu/docs/plans/2026-09-26-mcp-launcher-standardization.md
See: mcp-common/docs/mcp/launcher-cookbook.md#example-4
See: .claude/decisions/2026-09-26-mcp-launcher-migration.md"
```

## 7. Cross-references

- **Parent plan**: `/Users/les/Projects/mahavishnu/docs/plans/2026-09-26-mcp-launcher-standardization.md` §5 Phase 4a Task 4a.2 + §4 (REQs)
- **Cookbook Example 4**: `/Users/les/Projects/mcp-common/docs/mcp/launcher-cookbook.md#example-4-cj-crackerjack-no-auth-no-settings--closure-passes-auth_confignone`
- **Launcher source**: `/Users/les/Projects/mcp-common/mcp_common/server/launcher.py` (~280 LOC; signature uses variadic `build_server: Callable[..., Any]` per REQ-003)
- **Tracker row**: `/Users/les/Projects/mahavishnu/docs/mcp/server-migration-tracker.md` (cj row updated `migration_status: in-progress` → `done` post-commit)
- **Backward Compat Matrix**: `/Users/les/Projects/mahavishnu/docs/mcp/launcher-backcompat-matrix.md` (to be written per plan §5 Phase 4b Task 4b.2; this design note's §3G is the cj row)

## 8. Open questions

1. **STDIO mode fallback for `launch()`?** The launcher is HTTP-only. If a future phase needs STDIO migration, the launcher would need a `transport="stdio"` kwarg. Out of scope for Phase 4a.
2. **Should `_create_and_validate_server` stay as `asyncio.run(create_mcp_server(...))`?** Yes — it's the natural pre-build site. The pre-build pattern in `main()` is the cleanest bridge. Don't move the build into `build_server` itself.
3. **Should we replace the custom `/health` route with `register_http_health_route`?** **NO** — the 503-on-degraded semantic and the `skills_signer` feed wiring are crackerjack-specific. Keep the custom route, add the `"launcher"` field manually.
4. **What happens to the `RateLimitingMiddleware`?** Stays as-is — registered inside `create_mcp_server` (lines 207-214), unaffected by the launcher migration.

## 9. Summary for the implementer

| What to do | Where |
|---|---|
| Replace `_run_mcp_server` HTTP-mode body with `launch(...)` call | `crackerjack/mcp/server_core.py:480-509` |
| Keep pre-built `mcp_app` (do NOT re-call `create_mcp_server` inside `build_server`) | `crackerjack/mcp/server_core.py:_run_mcp_server` |
| Add `"launcher": f"mcp_common.server.launcher@{mcp_common.__version__}"` to the inline `/health` route | `crackerjack/mcp/server_core.py:151-199` |
| Add `signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))` before `launch(...)` for REQ-014 | `crackerjack/mcp/server_core.py:_run_mcp_server` (HTTP branch) |
| DO NOT change the launchd plist | `~/Library/LaunchAgents/com.mcp.crackerjack.plist` |
| DO NOT change `crackerjack mcp start` | `crackerjack/cli/mcp_cli.py` |
| DO NOT replace the custom `/health` route with `register_http_health_route` | `crackerjack/mcp/server_core.py:151` |
| DO NOT bump the crackerjack version — user does via `crackerjack run -p minor` | per `feedback-mcp-common-version-bump-is-user.md` (applies to mcp-common only) |
