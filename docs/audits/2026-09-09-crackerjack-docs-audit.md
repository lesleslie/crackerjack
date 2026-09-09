# Crackerjack Docs Audit — 2026-09-09

**Repo:** `/Users/les/Projects/crackerjack` (v0.80.8, branch `main`, clean merge state)
**Audit type:** Read-only five-lens fanout
**Scope:** All `.md` files under `docs/`, `README.md`, `AGENTS.md`, `CLAUDE.md`, `QUICKSTART.md`, `CHANGELOG.md`, `pyproject.toml` doc-adjacent keys, MCP specs, Bodai cross-component references
**Working tree touched:** None. The audit team did not modify any file (verified by 5 of 5 lens subagents being read-only). The user's 9 uncommitted `docs/superpowers/specs/*.md` edits + `report.txt` were explicitly excluded from edit scope.

---

## Executive summary

| Severity | Count | Description |
|---|---|---|
| **Blocker** | 18 | Docs claim a flag / subcommand / tool / class that does not exist. New user copy-pastes from the README will fail. |
| **Drift** | 27 | Code works, docs misdescribe it (wrong prefix, wrong port, dead config keys, removed AI-fix surface). |
| **Orphan** | 32 | Doc references a deleted module / class / subcommand. Readers waste time searching. |
| **Coverage gap** | 16 | Real code exists, no user-facing doc points at it (Phase 4 web hooks + Jinja formatter + new MCP tools are the biggest example). |
| **Frontmatter rot** | 252+ | YAML frontmatter corrupted (delimiters became setext `##` headings); blocks all date-staleness tooling. |

The audit found evidence of **two large refactors that the docs never picked up**:

1. **The 2026-08-06 AI-fix subsystem removal** — 12-agent AI-fix chain was deleted; `AI_AGENT=1` semantics changed; `crackerjack.agents.*` reduced to `base.py`; skill-tracking pipeline truncated to channel-restricted calls. ~9 historical remediation/audit docs still describe the deleted surface in detail.
2. **The 2026-09-04 stub-activation** — Many previously-stubbed adapters and CLI subcommands began real registration. Web adapter is the cleanest Phase 4 example; Swift/Kotlin are already done. None of this is documented in any user-facing doc except `CHANGELOG.md`.

Frontmatter rot is a *separate* infrastructure issue that predates both refactors and silently disables every doc-validation gate in the project.

---

## Cross-lens top findings (ranked by impact)

### F1 — Frontmatter corruption blocks 252 files' tooling (Lens 5)
- **Symptom:** Every `.md` file carries YAML frontmatter that was collapsed into a setext H2 heading. Example from `AGENTS.md`:
  ```
  ______________________________________________________________________

  ## status: active role: canonical date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: lifecycle
  ```
- **Effect:** `crackerjack_doc_frontmatter_validate` reads an H2 heading, not metadata. The 252 files stamped `last_reviewed: 2026-07-17` (54 days stale) look recent to grep but cannot be parsed by validators.
- **Pattern exception:** `docs/plans/PLAN_INDEX.md:1-13` still has the correct multi-line form — so the corpus has two competing frontmatter shapes.
- **Root cause hypothesis:** A mass reformat (likely mdformat, given `.mdformat.toml` is present) interpreted `---` as a thematic break and flattened the YAML block.

### F2 — README claims features that don't exist (Lens 1, 2, 3, 4)
The README is the most-referenced doc; it carries the worst mismatches:
- **CLI flags that don't exist:** `--enhanced-monitor`, `--monitor`, `--orchestrated`, `--update-precommit`, `--no-config-update` (typo for `--no-config-updates`), `--disable-global-locking` (typo for `--disable-global-locks`).
- **CLI subcommands that don't exist:** `crackerjack init-ci`, `set-threshold`, `add-check`, `gate create`, `gate add-check`, `gate set-threshold`.
- **MCP server that doesn't exist:** `session-mgmt` (conflated with `session-buddy`).
- **Dhara description wrong:** "SQLite + WAL" — current is DuckDB + Sqlite.
- **Session-Buddy feature drift:** "automatic git project tracking" via a `crackerjack_integration.py` module that does not exist in either repo.
- **Tool count understates reality:** lists 8 MCP tools; actual surface is ~42.
- **Slash-command framing wrong:** treats Claude Code slash commands (`/checkpoint`, `/quit`) as Crackerjack CLI invocations.

### F3 — Phase 4 web adapter shipped but only documented in CHANGELOG (Lens 1, 2, 4)
- **Code:** `web.stylelint`, `web.eslint`, `web.tsc`, `web.html_validate` (`crackerjack/adapters/web/hooks.py`)
- **MCP tools:** `check_web_lint`, `format_jinja_templates` (`crackerjack/mcp/tools/language_tools.py:356, :393`)
- **API surface:** `WebAdapter`, `web_hooks()`, `format_template()` — `crackerjack/adapters/web/`
- **Docs:** Only `CHANGELOG.md` (under `[Unreleased]`) mentions any of this. README, CLI_REFERENCE, MCP_TOOLS_SPECIFICATION, QUICKSTART, ARCHITECTURE all have zero mention. New users cannot discover Phase 4 from any user-facing doc.

### F4 — `MCP_TOOLS_SPECIFICATION.md` is internally contradictory and out of date (Lens 2, 4)
- **Contradiction in §"Registration model" line 22:** "*Crackerjack does **not** use a profile gate (unlike Mahavishnu, …).*" — false; `profiles.py` shows it does.
- **"12 always-on tools" claim line 32:** there are 12 tools at STANDARD profile, not "always-on"; import locations quoted in the doc are also wrong (lines 75-90 vs. actual 228-248).
- **Phantom tool listings:** §"§3 git_semantic_tools" lists 4 tools (`index_git_history`, `search_git_history`, `find_workflow_patterns`, `recommend_git_practices`) — none exist anywhere in the codebase or registration map.
- **Stale tool reference:** `analyze_errors` is listed with a NOTE that it was removed, but is still in the table; `register_utility_tools → list_slash_commands` misattributes `list_slash_commands` to `utility_tools.py` (actual: `monitoring_tools.py:440`).
- **Profile drift:** `mahavishnu_tools` (4 tools) is in `REGISTRATION_MAP` but missing from `PROFILE_REGISTRATIONS`; uncertain whether it ends up registered in FULL profile.

### F5 — The deleted `crackerjack.agents.*` subsystem still has doc references (Lens 4)
- **Code state:** Only `crackerjack/agents/base.py` (`AgentContext`) remains.
- **Doc references:**
  - `docs/REMEDIATION_PLAN_2026-02-05.md` (8 sites)
  - `docs/IMPLEMENTATION_STATUS.md` (lines 383, 402, 534, 548, 554)
  - `docs/AI_FIX_TEST_FAILURE_IMPLEMENTATION_PLAN.md` (lines 642, 1173, 1226, 1284)
  - `docs/AUDIT_RESULTS.md` (lines 228–236)
  - `docs/AI_FIX_INVESTIGATION.md` (lines 265, 266, 267, 335, 336)
  - `docs/WARNING_SUPPRESSION_AGENT_DESIGN.md:327`
  - `docs/WARNING_AGENT_INTEGRATION.md:58`
  - `docs/PERFORMANCE_OPTIMIZATION_PLAN.md:193`
- All reference `TestEnvironmentAgent`, `DeadCodeRemovalAgent`, `FormattingAgent`, `AgentCoordinator`, `ISSUE_TYPE_TO_AGENTS`, `IssueType` — none exist.
- **Same pattern in `crackerjack.adapters.ai.*`:** `ClaudeCodeFixer`, `OpenAICodeFixer`, `QwenCodeFixer` replaced by `FallbackChainCodeFixer`. `PROVIDER_ARCHITECTURE.md` references the old classes throughout (entire file is orphaned).

### F6 — ADR-001 port conflict (Lens 3)
- **Doc claim:** `http_port: 8676, websocket_port: 8675` (`docs/adr/ADR-001-mcp-first-architecture.md:263-264`)
- **Live config:** `mcp_http_port: 8676`, `mcp_websocket_port: 8696` (`settings/crackerjack.yaml:175, 177`)
- **Risk register own admission:** Line 363 acknowledges "Port conflicts (8675/8676)" but no fix was committed.
- **External collision:** `mahavishnu/settings/local.yaml.example:53` claims `crow_http_port=8675` — directly collides with the ADR's `websocket_port=8675` claim.
- The ADR structurally needs an update, or the live setting needs a return to a non-conflicting range.

### F7 — Mahavishnu pool integration docs are mostly design-only (Lens 3)
- `docs/MAHAVISHNU_POOL_INTEGRATION.md:63` documents `pool_type="kubernetes"` — `kubernetes` is not a real pool type in Mahavishnu (`mahavishnu/pools/` only has `mahavishnu_pool`, `session_buddy_pool`, `runpod_pool`, `pi_pool`).
- Same file line 73: `worker_type="container"` — not a real worker type.
- Lines 320-345: `from mcp__mahavishnu import pool_spawn, ...` — Python `import mcp__mahavishnu` doesn't exist; the right idiom is JSON-RPC over `http://localhost:8680/mcp`.
- Line 93 ASCII diagram: "Worker 6: vulture" — vulture was replaced by Skylos 2+ releases ago.
- `docs/plans/2026-06-27-ty-cleanup-and-ai-fix.md:286` references `crackerjack/integration/mahavishnu_pool_dispatcher.py` (236 lines) — file does not exist in current tree. The Phase 1-3 plans for the pool dispatcher were scoped out during AI-fix removal.

### F8 — Tool-count claims are hand-maintained and stale (Lens 2, 3)
- `README.md:1778` lists 8 tools; actual ~42.
- `docs/MCP_GLOBAL_MIGRATION_GUIDE.md:32` claims `12/14` for session-buddy; actual 19+.
- `docs/MCP_GLOBAL_MIGRATION_GUIDE.md:36` claims `11/14` for crackerjack; actual ~42.
- `README.md:1389-1406, 1778` "Available MCP Tools" — 8 names, same gap.

---

## Per-lens detail

### Lens 1 — CLI flag / env-var / hook doc sync

#### Blockers (won't work as documented)
| Doc | Claimed | Actual |
|---|---|---|
| `README.md:1534, 1592`, `docs/CLI_REFERENCE.md:531-538` | `--enhanced-monitor` | Not in `cli/options.py` `CLI_OPTIONS` dict |
| `README.md:1538, 1591`, `docs/CLI_REFERENCE.md:497-528` | `--monitor` | Not in `CLI_OPTIONS` |
| `README.md:1539, 1583`, `docs/CLI_REFERENCE.md:760-768` | `--orchestrated` | Not in `CLI_OPTIONS` |
| `README.md:1689` | `--no-config-update` | Singular typo; actual is `--no-config-updates` |
| `README.md:1654` | `--disable-global-locking` | Typo; actual is `--disable-global-locks` |
| `README.md:1690, 1878` | `--update-precommit` | Not anywhere in `CLI_OPTIONS` |
| `README.md:1605`, `docs/CLI_REFERENCE.md:144, 154` | `crackerjack health --probe` | `--probe` is on `crackerjack mcp health` only |
| `docs/CLI_REFERENCE.md:103` | `crackerjack start --mcp-port 8676` | `crackerjack start` has only `--force`, `--detach/--no-detach`, `--json` |
| `docs/CLI_REFERENCE.md:226-233` | `--quality-tier` bronze/silver/gold | Not in `CLI_OPTIONS` |
| `docs/CLI_REFERENCE.md:29` | `crackerjack run --preview` | Not in `CLI_OPTIONS` (only a ruff subprocess arg) |
| `docs/CLI_REFERENCE.md:31` | `crackerjack run --no-fix` | Same — not a top-level flag |
| `QUICKSTART.md:79-85` | `crackerjack init-ci --platform …` | Entire subcommand fictional |
| `QUICKSTART.md:128-157` | `set-threshold`, `add-check`, `gate create`, `gate add-check`, `gate set-threshold` | All fictional subcommands |
| `QUICKSTART.md:346` | `crackerjack run --timeout 600` | `--timeout` is only on `run_tests` |
| `QUICKSTART.md:317` | `crackerjack run --check pytest --verbose` | No `--check` flag on `run` |

#### Drift (works but inconsistent)
- `README.md:1344` `AI_AGENT=1` — actual semantics are Ruff auto-fix and settings creation, not "AI agent mode with structured JSON output" (AI subsystem was removed 2026-08-06).
- `README.md:421` `enable_zuban` location — actual is a Pydantic field on `HookSettings`, not a `[tool.crackerjack]` pyproject key.
- `README.md:421, 1451-1466` `enable_ty` / `enable_pyrefly` / `enable_zuban` uniform contract — only `zuban_lsp_*` keys live in `pyproject.toml`; `enable_*` are settings fields.
- `README.md:1020` env-var prefix — docs say `CRACKERJACK_*`, but `OneiricMCPConfig` is `env_prefix="ONEIRIC_MCP_"`.
- `README.md:1307-1343`, `docs/CLI_REFERENCE.md:787-790` `UV_KEYRING_PROVIDER` / `EDITOR` — claimed but not read by crackerjack.
- `docs/CLI_REFERENCE.md:796-797`, `docs/MIGRATION_GUIDE.md:433-434` `CRACKERJACK_MCP_HOST` / `CRACKERJACK_MCP_PORT` — claimed but not read; actual config is `pyproject.toml [tool.crackerjack]` `mcp_http_host`/`mcp_http_port`. Docs disagree on whether port is `8676` or `8696`.
- `docs/CLI_REFERENCE.md:246-254` claims `--max-iterations`, `--quick`, `--thorough`, `--ai-debug`, `--dry-run` were removed along with `--ai-fix` — code shows they are all still in `CLI_OPTIONS` (lines 542, 547, 603, 608, 700). Only `--ai-fix` was actually removed.
- `pyproject.toml:442` `mcp_websocket_port = 8675` — never read.
- `pyproject.toml:444, 445, 448` `zuban_lsp_enabled` / `zuban_lsp_host` / `zuban_lsp_strict_mode` — only `zuban_lsp_timeout` and `zuban_lsp_port` are actually read.
- `settings/crackerjack.yaml:181-185` `zuban_enabled`/`zuban_port`/`zuban_mode`/`zuban_auto_start` — naming has `zuban_` prefix on settings keys but not on the `ZubanLSPSettings` Pydantic model fields.

#### Coverage gaps (real code, missing docs)
- Phase 4 web hooks (`web.stylelint`, `web.eslint`, `web.tsc`, `web.html_validate`) — only in `CHANGELOG.md`.
- `check_web_lint`, `format_jinja_templates` MCP tools — not in `docs/MCP_TOOLS_SPECIFICATION.md`.
- `WebAdapter`, `web_hooks()`, `jinja_formatter.format_template()` — not in API reference.
- Env var `CRACKERJACK_DISABLE_AUTO_WORKERS` — wired in `cli/options.py:335` but undocumented.
- Env var `CRACKERJACK_DEBUG` — wired but undocumented.
- Env vars `ACB_LOG_LEVEL`, `ACB_DISABLE_STRUCTURED_STDERR`, `ACB_FORCE_STRUCTURED_STDERR` — wired as internal logging contract but never user-documented.
- `crackerjack/docs/generated/api/CLI_REFERENCE.md` (41, 70, 76, 77, 102) — generated doc stale; lists removed flags.

#### Clean
- Web hook IDs (`web.stylelint`, etc.) match between code and `CHANGELOG.md`.
- Comprehensive hook tools (Ruff, mdformat, Codespell, Bandit, etc.) all documented and wired.
- `--start-mcp-server`/`--stop-mcp-server`/`--restart-mcp-server`, `--test-workers`, `--zuban-lsp-port`, `--zuban-lsp-timeout`, `--zuban-lsp-mode` all wired correctly.
- `UV_PUBLISH_TOKEN`, `ANTHROPIC_API_KEY`, `MINIMAX_API_KEY` documented and wired.

### Lens 2 — MCP tool surface parity

#### Tool counts (verified by reading every `@mcp_app.tool()` in `crackerjack/mcp/tools/`)
| Profile | Tools registered | Notes |
|---|---|---|
| MINIMAL | ~6 | 4 health probes + `discover_tools` |
| STANDARD | 12 | core_tools, execution_tools, utility_tools, doc_tools + health + discover |
| FULL | 42–43 | STANDARD + eventbridge_tools (conditional) + language_tools (7) + monitoring_tools (6) + otel_tools (1) + progress_tools (2) + proactive_tools (3) + pycharm_tools (5) + semantic_tools (6) |

#### Blockers
- **`docs/MCP_TOOLS_SPECIFICATION.md:32`** falsely claims crackerjack doesn't use a profile gate; the same doc contradicts itself at line 22.
- **`docs/MCP_TOOLS_SPECIFICATION.md:72-75`** lists 4 `git_semantic_tools` (`index_git_history`, `search_git_history`, `find_workflow_patterns`, `recommend_git_practices`) — none exist in any tool file or registration map.
- **`docs/MCP_TOOLS_SPECIFICATION.md:42`** — `analyze_errors` listed with its own NOTE that it was removed; should be dropped from the table.
- **`docs/MCP_TOOLS_SPECIFICATION.md:167`** — `register_utility_tools` → `list_slash_commands` misattributes the function to `utility_tools.py`; actual is `monitoring_tools.py:440`.

#### Drift
- README's 8-tool list (lines 1389-1406, 1778) omits ~35 of the FULL-profile surface.
- `docs/MCP_TOOLS_SPECIFICATION.md:55` says "Skill/intelligence tools were removed 2026-08-12" — true for skill tools but `git_semantic_tools` row is not pruned.
- `mahavishnu_tools` (4 tools) — present in `REGISTRATION_MAP` but missing from `PROFILE_REGISTRATIONS`; ambiguous registration.
- `workspace_tools` (4 tools) — defined in `workspace_tools.py` but never in `REGISTRATION_MAP`; registration deferral should be made explicit.

#### Coverage gaps
- `language_tools` (7 tools, including new Phase 4 `check_web_lint` + `format_jinja_templates`) — zero coverage in `docs/MCP_TOOLS_SPECIFICATION.md`.
- `proactive_tools` (3 tools: `plan_development`, `validate_architecture`, `suggest_patterns`) — zero coverage.
- `execution_tools` `suggest_agents` — registered at STANDARD but missing from the "12 always-on" enumeration.
- `monitoring_tools.list_slash_commands` — registered but only referenced in the misattribution row.

#### Clean
- All Phase 4 names (`check_web_lint`, `format_jinja_templates`) verified at `language_tools.py:356, :393`; tests assert the names in the registered surface.
- `core_tools`, `execution_tools`, `utility_tools`, `semantic_tools`, `pycharm_tools`, `progress_tools`, `otel_tools`, `eventbridge_tools` — names and signatures match.

### Lens 3 — Bodai integration claims

#### Port references verified clean
- Session-Buddy 8678 (HTTP) + 8765 (WS) — confirmed.
- Akosha 8682 — confirmed.
- Dhara 8683 — confirmed.
- Mahavishnu 8680 — confirmed.
- Crackerjack HTTP 8676 — confirmed.

#### Port references with drift
- **`docs/adr/ADR-001-mcp-first-architecture.md:263-264`** claims `http_port: 8676, websocket_port: 8675`; live is `mcp_websocket_port: 8696`. Risk register at line 363 acknowledges the conflict but no fix was committed. `mahavishnu/settings/local.yaml.example:53` claims `crow_http_port=8675`, colliding with the ADR's `websocket_port=8675` claim.
- **`docs/MCP_GLOBAL_MIGRATION_GUIDE.md:218-219, 326-327, 340`** uvicorn launch form `uvicorn crackerjack.mcp.server_core:http_app --port 8676` — `http_app` symbol does not exist; launch is via `mcp_app.run_http_async(...)`.

#### Component role / version drift
- `README.md:26, 86, 605` says "Dhara Storage (SQLite + WAL)" — actual is DuckDB + Sqlite.
- `README.md:444` "Crackerjack integrates with **session-buddy** for AI agent metrics tracking" — the 12-agent AI-fix subsystem that produced these was removed 2026-08-06.
- `README.md:1782-1840` "session-buddy" section claims automatic git project tracking via `crackerjack_integration.py` — no such file in session-buddy source.

#### Integration claims (unsubstantiated)
- `docs/MAHAVISHNU_POOL_INTEGRATION.md:63` documents `pool_type="kubernetes"` and `docs/MAHAVISHNU_POOL_QUICKSTART.md:79-95` lists "KubernetesPool" — not a real pool type.
- Same files document `worker_type="container"` — not a real worker type.
- `docs/MAHAVISHNU_POOL_INTEGRATION.md:73` ASCII diagram lists "Worker 6: vulture" — vulture was replaced by Skylos.
- `docs/MCP_GLOBAL_MIGRATION_GUIDE.md:218-219` `uvicorn crackerjack.mcp.server_core:http_app` — symbol doesn't exist.
- `README.md:1810-1816` `session-mgmt` MCP server — does not exist.
- `README.md:1810-1820`, `docs/MAHAVISHNU_POOL_INTEGRATION.md:320-345` `from mcp__mahavishnu import …` — Python import of MCP namespace is wrong; real idiom is JSON-RPC over `http://localhost:8680/mcp`.
- `docs/MCP_GLOBAL_MIGRATION_GUIDE.md:32, 36` "12/14" and "11/14" tool counts — hand-maintained, stale.
- `docs/plans/2026-06-27-ty-cleanup-and-ai-fix.md:286` references `crackerjack/integration/mahavishnu_pool_dispatcher.py` — file does not exist.

#### Stale cross-component references
- All `MAHAVISHNU_POOL_INTEGRATION.md` Phase 1-3 design narratives — design only; never implemented due to AI-fix removal scoping.
- `docs/symbiotic-ecosystem-quick-start.md:164-170` "Track Skills with Session-Buddy" via `SessionBuddyDirectTracker` — class exists, but the upstream 12-agent skill-feed pipeline was removed 2026-08-06.

#### Clean
- `mahavishnu/mahavishnu/ingesters/content_ingester.py:611` calls `mcp__crackerjack__index_file_semantic` — strongest evidence of a *real* wired Bodai integration.
- `mahavishnu/mahavishnu/core/skill_mcp_validator.py:18-44` KNOWN_TOOLS / KNOWN_PORTS registry agrees with crackerjack's live surface.
- Ecosystem table in `mahavishnu/CLAUDE.md:11-19` agrees with every verified port in the lens.

### Lens 4 — Orphaned doc references

#### Whole-file orphans (largest fix surface)
- **`docs/features/PROVIDER_ARCHITECTURE.md`** — every class name, factory, and import path is from a deleted provider architecture (`OpenAICodeFixer`, `ClaudeCodeFixer`, `ProviderFactory`, `QwenCodeFixer`). Replaced by `FallbackChainCodeFixer`. Full rewrite or archival needed.
- **`docs/REMEDIATION_PLAN_2026-02-05.md`** — 8 sites reference deleted `crackerjack.agents.*` modules; also references `crackerjack.services.batch_processor`, `crackerjack.services.regex_patterns.SAFE_PATTERNS`, `crackerjack.services.async_file_io.AsyncIOError`, `crackerjack.services.safe_code_modifier.get_safe_code_modifier` (none exist).
- **`docs/IMPLEMENTATION_STATUS.md`** — lines 383, 402, 534, 548, 554 reference deleted `crackerjack.agents.*`.
- **`docs/AI_FIX_TEST_FAILURE_IMPLEMENTATION_PLAN.md`** — 642, 1173, 1226, 1284 reference deleted classes and stale import paths.
- **`docs/AUDIT_RESULTS.md`** — lines 228-236 reference deleted `crackerjack.agents.coordinator`.
- **`docs/AI_FIX_INVESTIGATION.md`**, **`docs/WARNING_SUPPRESSION_AGENT_DESIGN.md`**, **`docs/WARNING_AGENT_INTEGRATION.md`**, **`docs/PERFORMANCE_OPTIMIZATION_PLAN.md`** — same pattern.

#### Module / path drift
- `docs/bandit-performance-investigation.md:253` imports `crackerjack.adapters.security.bandit.BanditAdapter` — actual is `crackerjack.adapters.sast.bandit.BanditAdapter`.
- `docs/architecture/protocols.md:19` imports `crackerjack.models.protocols.Console` — actual class is `ConsoleInterface`.
- `docs/IMPLEMENTATION_STATUS.md:402` imports `crackerjack.agents.coordinator.{AgentCoordinator,ISSUE_TYPE_TO_AGENTS,IssueType}` — module only has `base.py`.
- `docs/SESSION_CHECKPOINT_2025-01-22.md:167` imports `crackerjack.models.protocols.Priority` — not in `protocols.py`.
- `docs/python-review-logging-progress-implementation.md:261, 599` imports `crackerjack.utils.logger_config` and `crackerjack.utils.logger_state` — neither module exists in `crackerjack/utils/`.
- `docs/AI_FIX_TEST_FAILURE_IMPLEMENTATION_PLAN.md:642, 1173` imports `crackerjack.parsers.test_result_parser.TestResultParser` and `TestFailureCategory` — actual path is `crackerjack.services.testing.test_result_parser`; exports are `TestErrorType` and `TestFailure` (not `TestFailureCategory`).
- `docs/reporting_tools_investigation.md:318` + `docs/archive/analysis/PHASE_3.3_SOLID_ANALYSIS.md:93` import `crackerjack.adapters.format.ruff_adapter.RuffAdapter` and `crackerjack.adapters.format.ruff.RuffAdapter,RuffSettings` — actual is `crackerjack.adapters.format.ruff` (`ruff.py`); no `_adapter` suffix.
- `docs/superpowers/specs/2026-06-03-dhara-mcp-migration-design.md:581, 647` references `crackerjack.services.aiosqlite_cleanup` — module does not exist.

#### Subcommand / CLI drift
- `docs/reference/service-dependencies.md:67` documents `crackerjack init-ci --platform github` — no such subcommand. Real Typer apps: `audit_cli`, `gitignore_cli`, `docs_cli`, `coverage_ratchet_cli`, `clone_cli`, `mcp_cli`, `hypothesis_lock_cli`, `skills_cli`, `anti_ai_flavor_cli`.

#### Hook references
- Review docs in `docs/superpowers/plans/reviews/2026-09-07-phase4-*.md` (8 files) still describe the pre-split `web.eslint_tsc` hook — historical record of the discovery+split, OK as historical, but the recurring mention can mislead readers. The plan itself (`2026-09-07-crackerjack-multi-language-phase4.md`) describes the converged 4-hook split correctly.

#### Env var name drift
- `docs/architecture/tool-profile-rationale.md:7` and `docs/architecture/MEMORY_ARCHITECTURE.md:1328` reference `MAHAVISHNU_TOOL_PROFILE` as a crackerjack-side env var — crackerjack's actual env var is `CRACKERJACK_TOOL_PROFILE`. (Mahavishnu's analog is `MAHAVISHNU_TOOL_PROFILE`; the cross-reference is intentional, but verify context.)

#### Clean
- All `LanguageAdapterBase`, `KotlinAdapter`, `SwiftAdapter`, `PythonAdapter`, `WebAdapter`, `RuffAdapter`, `BanditAdapter`, `lsp_client`, `zuban_lsp_service`, `discover_adapters`, `language_tools.check_web_lint`, `language_tools.format_jinja_templates`, etc. verified present.
- Web hook split `web.stylelint` + `web.eslint` + `web.tsc` + `web.html_validate` matches `crackerjack/adapters/web/hooks.py:web_hooks()`.
- `CRACKERJACK_TOOL_PROFILE`, `CRACKERJACK_AUTH_ENABLED`, `CRACKERJACK_JWT_SECRET` correctly wired.

### Lens 5 — Version drift + dead links

#### Version stamp drift
- **`CHANGELOG.md:1-75`** — `[Unreleased]` block contains the full Phase 4 Web-adapter entry; immediately below it is `## [0.80.5] - 2026-09-07`. **Three tags have no CHANGELOG entry:** `v0.80.6` (commit 36d55124), `v0.80.7` (4226fedc), `v0.80.8` (cff936ae). All shipped 2026-09-07. The shipped release notes imply nothing changed since 0.80.5.
- **`docs/reference/CHANGELOG.md:3,7`** — frontmatter says `status: active role: canonical`. Newest entry `## [0.44.29] - 2025-11-19`. **36 minor versions behind**, ~10 months stale. Two competing CHANGELOGs; the dead one is the one labeled canonical.
- Frontmatter-corruption pattern affects both CHANGELOGs (see F1).

#### Stale dates
- `README.md:1140` `**Status:** ✅ Production Ready (as of 2025-10-09)` — 11 months stale.
- `docs/README.md:9` `— Last updated: 2025-11-07` — 10 months stale.
- `docs/plans/PLAN_INDEX.md:20` `**Last regenerated:** 2026-07-20` — 51 days stale. The header says "Generated by `scripts/regenerate_plan_index.py`. Do not edit by hand" — script never ran. The 4 `2026-09-07-crackerjack-multi-language-phase{1..4}.md` plans are not indexed.
- `docs/CLI_REFERENCE.md:889`, `docs/QUICK_START.md:497`, `docs/MIGRATION_GUIDE.md:781` all `role: canonical` but stamp `2025-02-06` (~19 months stale).
- `docs/reference/COVERAGE_POLICY.md:7` — 10 months stale.
- `docs/IMPLEMENTATION_STATUS.md:17` has no date at all (unfalsifiable).
- **Bulk stamp noise:** `last_reviewed: 2026-07-17` appears in 252 files (single mass write). The field now carries no per-file signal.

#### Cross-component URL drift
- `README.md:11, 13` `https://github.com/lesleslie/bodai` — verified live (BSD-3-Clause, 64 commits).
- All third-party URLs in references are well-known repos — not spot-checked individually.
- No dead or example URL drift in user prose.

#### Dead internal links
- `docs/guides/AGENTS.md:31` → `docs/reference/COVERAGE_POLICY.md` — root-relative path used from `docs/guides/`. Resolves to `docs/guides/docs/reference/COVERAGE_POLICY.md`. Should be `../reference/COVERAGE_POLICY.md`.
- `docs/guides/CLAUDE.md:270` → `docs/architecture/tool-profile-rationale.md` — same bug.
- `docs/guides/CLAUDE.md:285` → `docs/reference/COVERAGE_POLICY.md` — same bug.
- `docs/guides/CLAUDE.md:291` → `./README.md` — `docs/guides/README.md` does not exist.
- `docs/guides/CLAUDE.md:292` → `./docs/` — `docs/guides/docs/` does not exist.
- `docs/reference/BREAKING_CHANGES.md:7-8` — plain-text refs `ONEIRIC_MIGRATION_EXECUTION_PLAN.md` and `MIGRATION_AUDIT.md` — neither file exists.
- `docs/reference/BREAKING_CHANGES.md:6` — `**Migration Date:** TBD (after Phase 0 complete)` while `role: canonical`.

#### Dead anchor refs
- `crackerjack/decorators/README.md:179` → `../../docs/guides/CLAUDE.md#critical-architectural-pattern-protocol-based-di` — truncated. Actual heading slug ends `based-design`.
- `docs/CLI_REFERENCE.md:16` (TOC) → `#mcp-server-commands` — no such heading.
- `docs/architecture/protocols.md:38` → `../README.md#architecture` — `docs/README.md` has no Architecture heading.
- `docs/architecture/protocols.md` sibling → `../README.md#quality-process` — same issue.
- **`docs/architecture/MEMORY_ARCHITECTURE.md`** has a systematic corruption from `crackerjack` → `crackers` (10 sites) and `improvementgenerator(maybe_generate)` slug form (3 sites). Example: line 55 reads `#contract-51--crackers-shell-git_metrics_schema-sql-fails-executescript` (real slug: `#contract-51--crackerjackmemorygit_metrics_schemasql-fails-executescript`).

#### Clean
- All relative image links resolve.
- No path typos (`docs./`, `doc/s`, `crackerjack./`) anywhere.
- README.md, CLAUDE.md, AGENTS.md, QUICKSTART.md, docs/index.md, docs/README.md, docs/ARCHITECTURE.md, docs/MCP_TOOLS_SPECIFICATION.md carry no stale "current version" claims.

---

## Remediation categories (not fixes)

These are *category buckets* the audit surfaces. Each maps to a concrete cleanup with its own scope:

### Category A — Frontmatter mass-reformat (blocker for tooling)
The 252 corrupted files share the same single-line H2 form. Root cause is the YAML-to-setext conversion. Remediation is mechanical re-emit of the YAML block with proper `---` delimiters.

### Category B — CLI/flag/index correction (blocker for new users)
README.md and `docs/CLI_REFERENCE.md` together contain the bulk of "feature documented but not implemented" claims. A focused pass to align both with `CLI_OPTIONS` and `__main__.py @app.command` decorators would address most of the blockers in F2.

### Category C — Phase 4 docs push-out (coverage gap)
Phase 4 (Web adapter + Jinja formatter + new MCP tools) shipped in CHANGELOG only. A 4-section docs push (CLI/hooks, MCP tools, API reference, ecosystem guide) would close this.

### Category D — `MCP_TOOLS_SPECIFICATION.md` rewrite
The spec has internal contradiction (no profile gate vs. uses profile gate), phantom tools (`git_semantic_tools`), stale entries (`analyze_errors`), and missing entries (`language_tools`, `proactive_tools`). A full rewrite aligned with `profiles.py` + `crackerjack/mcp/tools/` is the right scope.

### Category E — Two-CHANGELOG ambiguity
Choose between `CHANGELOG.md` (canonical, real) and `docs/reference/CHANGELOG.md` (frozen, 36 versions stale). Add the missing [0.80.6/0.80.7/0.80.8] entries to the canonical one; either delete or freeze the reference one.

### Category F — Orphaned remediation/audit doc archival
~9 historical remediation/audit doc files reference the deleted `crackerjack.agents.*` and `crackerjack.adapters.ai.*` surfaces. These describe work that was scoped away in the 2026-08-06 AI-fix removal. Decision needed: rewrite or archive (move to `docs/archive/`).

### Category G — ADR-001 port stance
Either update the ADR to reflect `mcp_websocket_port: 8696` (live) and add a "Port Conflicts" decision row, or change the live setting to a non-conflicting range.

### Category H — Bodai integration doc rewrite
`docs/MAHAVISHNU_POOL_INTEGRATION.md` and `docs/MAHAVISHNU_POOL_QUICKSTART.md` describe work that was scoped out during AI-fix removal. Either rewrite to current reality (no kubernetes pool, no container worker, vulture → Skylos, JSON-RPC not import) or move to `docs/superpowers/plans/.archive/`.

### Category I — Internal dead-link repair
Six in-corpus dead links (5 in `docs/guides/`, 1 in `docs/reference/BREAKING_CHANGES.md`). Each is a one-line Edit.

### Category J — Anchor-slug cleanup
`docs/architecture/MEMORY_ARCHITECTURE.md` has 10 corrupted anchors from `crackerjack → crackers` rewriting. `crackerjack/decorators/README.md:179` has a truncated anchor. These are mechanical repairs (or regen the doc).

### Category K — `PLAN_INDEX.md` regen
Header documents the regen script. Run `scripts/regenerate_plan_index.py` to incorporate the 4 phase plans already on disk but missing from the index.

---

## Methodology notes

- 5 read-only subagents dispatched in parallel from `/Users/les/Projects/crackerjack/main`.
- Each agent was given a single lens and explicit read-only/no-git-state-change instructions.
- The user's working tree (9 uncommitted spec edits in `docs/superpowers/specs/` + `report.txt`) was excluded from edit scope.
- No edits, no writes, no commits. This audit report is the only new file produced.
- All findings are anchored to file:line + a code-side anchor in the crackerjack repo.
- Three cross-repo ground-truth checks were performed in `MAHAVISHNU` and `SESSION_BUDDY`; both were strictly read-only (no git operations on those repos either).
- Tool counts cross-checked by grepping every `@mcp_app.tool()` and `@mcp.tool()` decorator in `crackerjack/mcp/tools/` and counting registrations in `crackerjack/mcp/tools/profiles.py`.
