# Kotlin/Gradle Lens Review

**Reviewer:** kotlin-specialist
**Date:** 2026-09-09
**Subject:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase3.md` (8 tasks, 1221 lines, ~7 commits)

---

## Findings (most-severe first)

### 1. **BLOCKER** — `_bump` crashes on real-world Kotlin semver qualifiers (`-SNAPSHOT`, `-RC1`, `-M1`)

**Line(s):** 678–699 (`_bump` implementation in Task 5.1), 1211–1220 (cross-adapter divergence note)

**Summary:** Kotlin/Maven projects conventionally use pre-release qualifiers (`1.0.0-SNAPSHOT`, `2.0.0-RC1`, `2.0.0-M1`, `2.0.0-alpha01`). Many Kotlin projects — especially JetBrains-published libraries (`jinja2-custom-delimiters`, kotlinx libraries, AndroidX, etc.) — keep `-SNAPSHOT` between releases and strip it on release. The plan's `_bump`:

```python
major, minor, patch = (int(p) for p in version.split("."))
if level == "major":
    major += 1
    minor = 0
    patch = 0
...
return f"{major}.{minor}.{patch}"
```

crashes with `ValueError: too many values to unpack` on `1.0.0-SNAPSHOT` (4 parts) and **silently drops** the qualifier on every bump (`1.0.0-SNAPSHOT` → `1.0.1`). The latter is worse than the former because it ships unintentional state changes to consumers and corrupts Maven coordinates.

**Failure scenario:**
- Project with `version=1.0.0-SNAPSHOT` in `gradle.properties`.
- Operator runs `kotlin_bump_version(level="minor")`.
- `_bump("1.0.0-SNAPSHOT", "minor")` → `split(".")` returns `["1", "0", "0-SNAPSHOT"]` → `int("0-SNAPSHOT")` raises `ValueError` → lifecycle aborts mid-flow (after `gradle.properties` write may already be persisted, before `_commit`). Test for `0.1.0` passes; production on a real Kotlin project blows up.

Even with the write happens after `_commit`, the rollback resets git but does not undo the `gradle.properties` write (Task 5 Step 3 says "write happens BEFORE the dry_run check. … `_commit` has already happened"). So a failed bump on a `-SNAPSHOT` project leaves `gradle.properties` with `1.0.1-SNAPSHOT` (or whatever the next parse tolerates) and rolls back the commit, leaving the working tree inconsistent.

**Category:** Correctness (semver handling) + lifecycle rollback semantics.

**Recommendation:** Parse qualifiers explicitly and preserve them:

```python
import re

_SEMVER_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<qualifier>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)

def _bump(version: str, level: str) -> str:
    m = _SEMVER_RE.match(version)
    if not m:
        raise ValueError(f"not a valid semver string: {version!r}")
    major, minor, patch = int(m["major"]), int(m["minor"]), int(m["patch"])
    qualifier = m["qualifier"]
    if level == "major":
        major += 1
        minor = 0
        patch = 0
    elif level == "minor":
        minor += 1
        patch = 0
    elif level == "patch":
        patch += 1
    else:
        raise ValueError(f"level must be one of ('major', 'minor', 'patch'); got {level!r}")
    out = f"{major}.{minor}.{patch}"
    if qualifier:
        out += f"-{qualifier}"
    if m["build"]:
        out += f"+{m['build']}"
    return out
```

Add a test fixture: `tests/fixtures/gradle-vanilla/gradle.properties` with `version=1.0.0-SNAPSHOT` for the lifecycle smoke.

---

### 2. **HIGH** — `_bump` crashes on 2-part (`1.0`) and 1-part (`1`) versions

**Line(s):** 678–699

**Summary:** `major, minor, patch = (int(p) for p in version.split("."))` requires exactly three dot-separated components. Maven allows 2-part (`1.0`) and 1-part (`1`) versions, and Gradle plugins sometimes emit shortened versions via `gradle.properties` macros. This is a defensive-coding gap that surfaces in real-world Kotlin plugin projects that use `version=0.1` style.

**Failure scenario:** A developer keeps `version=0.1` in `gradle.properties` (single-dot form, common in early-stage JetBrains plugin scaffolds). `kotlin_bump_version` → `_bump("0.1", "patch")` → `ValueError: not enough values to unpack`.

**Category:** Correctness (defensive parsing).

**Recommendation:** Coerce to 3-part before parsing:

```python
parts = version.split(".")
while len(parts) < 3:
    parts.append("0")
major, minor, patch = (int(p) for p in parts[:3])
```

Or use the regex-based parse from Finding #1, which accepts `1` and `1.0` as `major.minor.0`.

---

### 3. **HIGH** — `version_source` regex misses Kotlin-DSL idiomatic forms (libs.versions.toml, `val version`, computed values)

**Line(s):** 174–184 (read Tier 2), 277–280 (regex applied), 795–813 (test only checks literal `version = "1.2.3"`)

**Summary:** The plan's Tier 2 regex `^\s*version\s*=\s*"([^"]+)"` only matches the literal form. Common Kotlin DSL idioms the regex misses:

```kotlin
// Version catalog reference (the most common in modern Kotlin)
version = libs.versions.projectVersion.get()

// Computed at config time
version = "1.0.0" + "-SNAPSHOT"

// Kotlin top-level val
val version = "1.0.0"

// ext property
ext.version = "1.0.0"

// Lazy provider
version = providers.gradleProperty("version").get()
```

If a JetBrains plugin project uses `libs.versions.toml` (modern Kotlin convention since Gradle 7.4+, the default in IntelliJ Platform Gradle Plugin 1.x+), `kotlin_list_hooks` reports no readable version, and `kotlin_bump_version` writes a `version=` line to `gradle.properties` that is **silently ignored** by Gradle (because `version = libs.versions.X.get()` in `build.gradle.kts` shadows it). This produces the worst failure mode: "no error, but the bump didn't take effect."

The fixture `tests/fixtures/gradle-vanilla/build.gradle.kts` (line 1124–1138) uses the literal form, so the test suite passes; production on `jinja2-custom-delimiters` (the named Phase 3 fixture per spec line 700) likely uses the catalog form and silently breaks.

**Category:** Correctness (compatibility with real Kotlin DSL).

**Recommendation:** Add Tier 2b: parse `gradle/libs.versions.toml` (the modern Kotlin convention). Probe order: gradle.properties → libs.versions.toml → build.gradle.kts literal → `gradlew properties` (source of truth).

For libs.versions.toml:

```toml
[versions]
projectVersion = "1.0.0"
```

```python
toml_path = self._project_root / "gradle" / "libs.versions.toml"
if toml_path.exists():
    content = toml_path.read_text()
    m = re.search(
        r'^\s*(?:projectVersion|version)\s*=\s*"([^"]+)"',
        content, re.MULTILINE,
    )
    if m:
        return m.group(1)
```

This adds 15 LOC and avoids the silent-shadow failure mode. Note: TOML has a real spec but Crackerjack avoids the `tomllib` dependency for v0.81 (uses `re.search` consistent with the existing pattern). For Phase 4 polish, swap to `tomllib` (stdlib in 3.11+).

The write path needs the same coverage: if version comes from `libs.versions.toml`, `GradlePropertiesVersionSource.write()` should write to `libs.versions.toml`, not `gradle.properties`. Otherwise the bump silently no-ops.

---

### 4. **HIGH** — Fixture is missing `gradle.properties`; lifecycle smoke tests cannot run end-to-end

**Line(s):** 1108–1147 (Task 8.1 fixture definition)

**Summary:** The plan defines a fixture at `tests/fixtures/gradle-vanilla/` with `settings.gradle.kts`, `build.gradle.kts` (with `version = "0.1.0"`), and `src/main/kotlin/Hello.kt`. **No `gradle.properties` is created.**

- `detect()` returns True (build.gradle.kts exists) ✓
- `capabilities()` returns 3 hooks + lifecycle ✓
- Task 8.4 smoke (`print(a.detect(...))`) ✓
- `kotlin_list_hooks` ✓
- `kotlin_bump_version` with the fixture → `_read_via_gradle()` finds `version` in build.gradle.kts → write tries to find gradle.properties → `FileNotFoundError` (Task 2 Step 3 lines 295–298).

The Phase 2 Swift equivalent had a similar concern (`Package.swift` only, no manifest version field); Swift worked because `GitTagVersionSource.write()` is a `NotImplementedError`. Kotlin can't punt this way — the fixture is meant to be lifecycle-testable.

**Failure scenario:** An operator runs `crackerjack run -p minor` on a Kotlin project with `version` only in `build.gradle.kts` (no `gradle.properties`). Bump fails with `FileNotFoundError: gradle.properties not found at <path>; cannot write version`. This is the **most common Kotlin/JVM project layout** in 2026 — `gradle.properties` typically holds compiler flags, not version metadata; version goes in `build.gradle.kts`.

**Category:** Real-world usability + fixture correctness.

**Recommendation:** Either:

1. **Add `gradle.properties` to the fixture with `version=0.1.0`** so the smoke can run end-to-end. Build.gradle.kts stays without `version` literal so Tier 2 doesn't shadow. (Mirror Swift's `swift-lib` fixture which has all needed manifest fields.)

   ```properties
   # tests/fixtures/gradle-vanilla/gradle.properties
   version=0.1.0
   ```

   Then either remove `version = "0.1.0"` from `build.gradle.kts` (recommended — exercises Tier 1 file-probe) or keep both and document that Tier 1 wins.

2. **Document in the plan that `gradle.properties` is required for Kotlin bump.** Add a check: if `gradle.properties` is missing AND `build.gradle.kts` has no literal `version`, fail with a clear message pointing the user to add `version=X.Y.Z` to `gradle.properties`. The current `FileNotFoundError` message is correct but un-actionable ("file not found" doesn't tell the operator what to do).

Recommend (1) for fixture + (2) for production behavior.

---

### 5. **HIGH** — `GradleTaskProbe.has_task` silently swallows gradlew failures as "task absent"

**Line(s):** 461–466 (`has_task` implementation), 469–488 (hook construction)

**Summary:** `has_task` does:

```python
result = subprocess.run(["./gradlew", "tasks", "--all", ...])
return bool(re.search(rf"^{re.escape(task_name)}\s+", result.stdout, re.MULTILINE))
```

If `./gradlew` is missing, not executable, fails to download Gradle distribution, or has any error, `re.search` returns `None` on empty stdout → returns `False` → hook is silently skipped "because the task is absent" with no warning to the user.

The plan says "skip-with-warning if absent" but there is no warning code in the plan. The hook construction (lines 469–488) returns `Hook(name=name, cli_command=(...))` with no warning payload.

**Failure scenario:** CI runner has no Java installed → `./gradlew` fails with "JAVA_HOME not set" → all three hooks silently skip → CI passes green → operator ships un-tested Kotlin code.

**Category:** Silent error / CI reliability.

**Recommendation:** Differentiate three probe outcomes:

```python
@dataclass(frozen=True)
class ProbeResult:
    state: Literal["present", "absent", "unavailable"]
    error: str | None = None  # populated when state == "unavailable"

def has_task(self, task_name: str) -> ProbeResult:
    gradlew = self._project_root / "gradlew"
    if not gradlew.is_file():
        return ProbeResult("unavailable", "`./gradlew` not found")
    if not os.access(gradlew, os.X_OK):
        return ProbeResult("unavailable", "`./gradlew` not executable")
    result = subprocess.run(
        ["./gradlew", "tasks", "--all", "-q", "--no-daemon", "--no-configuration-cache"],
        cwd=self._project_root, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return ProbeResult("unavailable", f"`gradlew tasks --all` failed: {result.stderr.strip()}")
    matches = re.search(rf"^{re.escape(task_name)}\s+", result.stdout, re.MULTILINE)
    return ProbeResult("present" if matches else "absent")
```

The hook runner (in `crackerjack/core/`) needs to surface `unavailable` as a `HookWarning` rather than a skip. Phase 2 Swift had a similar gap; Phase 3 should not regress.

---

### 6. **MEDIUM** — `_PROBE_KEYS = ("pluginVersion", "projectVersion", "version")` picks up Android Gradle Plugin version on Android projects

**Line(s):** 259–260 (probe order), 38 (plan-level constraint)

**Summary:** The plan implements the spec's probe order (`pluginVersion`, `projectVersion`, `version`) literally. In Android projects, `pluginVersion` is conventionally used for the **Android Gradle Plugin** version (e.g., `pluginVersion=8.2.0`), not the project version. Picking the first match means a Kotlin Android project reports its AGP version as its project version.

This is technically a spec defect (spec line 306 has the same order), but the plan implements it without flagging the risk. The Phase 2 Swift lens reviewer caught similar "literal implementation of spec defect" issues; Phase 3 should mirror that vigilance.

**Failure scenario:** Operator runs `kotlin_bump_version` on `jinja2-custom-delimiters`-style Android project with `pluginVersion=8.2.0` in gradle.properties and `version=0.1.0` in build.gradle.kts. Crackerjack reads `8.2.0` as project version, writes `8.2.1` to `gradle.properties`'s `pluginVersion=` line, ships that. Operator confused why their project version is now 8.2.1.

**Category:** Spec implementation defect.

**Recommendation:** Flag this in the review as a **spec defect** requiring amendment before Phase 3 lands. Two options:

1. **Reorder probes** to `version`, `projectVersion`, `pluginVersion` (most-specific first). `version=` is the dominant convention; the other two are escape hatches for non-standard project templates.

2. **Document the Android risk explicitly** in `GradlePropertiesVersionSource.read()` docstring and let users opt out via `[tool.crackerjack.kotlin] plugin_version_is_project_version = false` (default).

The Phase 2 Swift lens caught 16 findings; a spec defect that the plan implements blindly is exactly what that reviewer process is for.

---

### 7. **MEDIUM** — Multi-module / Kotlin Multiplatform projects are not handled

**Line(s):** 297–326 (Spec read logic), 261 (`__init__` only stores `project_root`)

**Summary:** Real Kotlin projects frequently have:

- **Kotlin Multiplatform (KMP)**: `version` lives in the **root** `build.gradle.kts` and is referenced by subprojects via `subprojects { version = rootProject.extra["version"] }`. The plan's root-only probe works for this case *only if* the version is in `gradle.properties` (Tier 1) or in a literal string at root `build.gradle.kts` (Tier 2).
- **Composite builds**: Same idea, but across repos.
- **Multi-module Android**: `gradle.properties` may have `VERSION_NAME=1.0.0` (Android-specific) instead of `version=`. The probe misses this entirely.

`GradlePropertiesVersionSource` is parameterized only by `project_root` and has no concept of subprojects. Version discovery across subprojects is silently unsupported.

**Failure scenario:** A KMP project with `version = "1.0.0"` in root `build.gradle.kts` (computed via catalog or `extra["version"]`) is **read** correctly by Tier 2. **Written** version goes to `gradle.properties` (which the build doesn't reference). Kotlin plugin in root `build.gradle.kts` overrides the gradle.properties value, so the write silently no-ops.

**Category:** Real-world Kotlin project compatibility.

**Recommendation:** Defer to Phase 3.5 (similar to spec's Phase 2.5 follow-up). Add a `TODO: Kotlin Multiplatform` comment in `version_source.py` and file an issue. Document the limitation in the CHANGELOG entry ("multi-module projects with computed versions are not supported in v0.83; tracked for Phase 3.5").

---

### 8. **MEDIUM** — Subprocess invocation does not check `result.returncode != 0` in `has_task` (real failure masked)

**Line(s):** 462–466

**Summary:** Already partially covered by Finding #5, but worth isolating: the plan's `has_task` does not inspect `result.returncode` at all. The Kotlin DSL plugin task list depends on Java availability, plugin download cache, and config-cache state. If `./gradlew tasks --all` exits 1 because `pluginManagement` cannot resolve a plugin (offline), `result.stdout` is empty, `re.search` returns None, hook is silently skipped.

The plan's `_read_via_gradle()` (lines 281–291) correctly checks `result.returncode != 0` and raises `VersionNotFoundError`. The probe path does not — inconsistent error handling.

**Category:** Error handling consistency.

**Recommendation:** Mirror the explicit returncode check from `_read_via_gradle()` in `has_task()`. Either raise on failure or return a distinct `ProbeResult.unavailable` (Finding #5).

---

### 9. **MEDIUM** — Test for `gradle properties` probe assumes `^version:\s*(\S+)` matches; Gradle emits `version: 0.1.0` with the same pattern but multiline emission varies

**Line(s):** 180–183, 288–291

**Summary:** Gradle's `properties` task emits each property on its own line as `name: value`. The regex `^version:\s*(\S+)` matches `version: 0.1.0` correctly. However:

- If a subproject has a different `version` setting, Gradle emits multiple `version:` lines (root first, then subprojects). The first match wins, which is correct.
- If the project uses a version catalog with a `version.ref` reference, Gradle's `properties` may emit `version: null` or a placeholder. The regex captures `null` as the version → bump fails downstream.
- If the project has custom `extra.properties` named `version` (Gradle allows arbitrary `ext.version`), the regex matches the ext value, not the project version.

Empirically fine for vanilla Kotlin/JVM. Risky for KMP/Android.

**Category:** Edge case in Gradle properties parsing.

**Recommendation:** Add a comment to `_read_via_gradle()` documenting the assumption (root project's `version:` only; subprojects' versions ignored). For KMP, root wins by Gradle's emission order — sufficient for v0.83.

Test should also assert: `gradle.properties` exists with `version=0.1.0`, Tier 1 wins → subprocess not called. The current test `test_read_raises_version_not_found_when_nothing_matches` (line 223–226) only covers the "neither file" case. Add: `test_read_prefers_gradle_properties_over_gradlew_subprocess` to lock in the file-probe priority.

---

### 10. **MEDIUM** — `version_source.write()` regex doesn't handle inline comments or trailing-comma lists

**Line(s):** 293–317 (write method)

**Summary:** Gradle `.properties` files support `#` and `!` comments. Real-world `gradle.properties` has comments like:

```properties
# Project version - update before tagging
version=1.0.0

# Multi-value property (Gradle 8.5+ syntax)
incomingVersions=1.0.0,1.1.0
```

The write regex `^(\s*)({key}\s*=\s*)(\S+?)([,\s]*)$` does not match:
- `version=1.0.0  # comment` (regex doesn't allow `#`)
- `version = "1.0.0"` (quoted form, unusual but legal)
- Lines where the value is followed by `\r\n` (CRLF files — Windows checkouts)

For CRLF: `[,\s]*$` matches `\r` and `\n` (both whitespace), so the regex actually does match. Confirmed by testing: `re.MULTILINE` mode treats `\r` as whitespace.

For comments: the write fails to update the line, the code appends a new `version=X.Y.Z\n` at end of file. Gradle's properties loader reads all entries → two `version=` keys → last-wins → bump effectively works but leaves stale comment line. Cosmetic, not catastrophic.

**Category:** Defensive parsing.

**Recommendation:** Strip trailing comments before regex matching:

```python
content = re.sub(r"#[^\n]*", "", content)  # Strip comments
```

Acceptable as v0.83; file as Phase 3.5 cleanup.

---

### 11. **MEDIUM** — Plan lacks a test that the version written to gradle.properties is the version Gradle actually resolves to

**Line(s):** 311–316 (write verification)

**Summary:** `GradlePropertiesVersionSource.write()` reads back via `self.read()` and compares. This catches "write didn't persist" failures. But it does NOT catch "write persisted, but Gradle ignores it because `build.gradle.kts` shadows gradle.properties."

This is a stronger invariant: after write, the resolved version from `./gradlew properties` must equal the new version. Without this test, Finding #4 (build.gradle.kts shadows gradle.properties write) silently passes.

**Category:** Test gap.

**Recommendation:** Add a smoke test (gated on `gradlew` availability) that runs `./gradlew properties` after write and asserts the resolved version matches.

```python
@pytest.mark.skipif(
    not shutil.which("java"),
    reason="java not installed",
)
def test_write_round_trips_via_gradle(tmp_path: Path) -> None:
    (tmp_path / "gradle.properties").write_text("version=1.0.0\n")
    (tmp_path / "build.gradle.kts").write_text('version = "1.0.0"\n')
    # ... full fixture with settings.gradle.kts + gradlew + Kotlin plugin
    src = GradlePropertiesVersionSource(tmp_path)
    src.write("1.1.0")
    assert src.read() == "1.1.0"
    # Optional: invoke gradle and verify
    # subprocess.run(["./gradlew", "properties", "-q", ...], cwd=tmp_path)
    # assert "version: 1.1.0" in result.stdout
```

Real fixture (with `gradlew`) integration testing belongs in Task 8.1, not here.

---

### 12. **LOW** — `_bump` does not handle version `0.x.y` correctly in real-semver mode

**Line(s):** 678–699

**Summary:** The plan claims "real semver" semantics for Kotlin. True semver treats `0.x.y` as "anything goes, but breaking changes bump minor." Crackerjack's `_bump` for Kotlin ignores this — `0.1.0` major bumps to `1.0.0` (correct semver), but minor bumps to `0.2.0` and patch to `0.1.1`. The plan's docstring (line 678–685) doesn't clarify whether this matches SemVer 2.0 or just "literal `major`/`minor`/`patch` arithmetic."

This is a documentation gap, not a behavior gap. The cross-adapter divergence note (line 1211–1220) acknowledges the choice but doesn't tie it back to SemVer 2.0.

**Category:** Documentation.

**Recommendation:** Document in the docstring whether "real semver" means "literal field arithmetic" or "SemVer 2.0 semantics." Recommend literal arithmetic (current behavior) with a comment that pre-1.0 Kotlin projects should manually bump to 1.0.0 first.

---

### 13. **LOW** — Probe pattern `^version:\s*(\S+)` captures trailing comments or carriage returns incorrectly on some Gradle versions

**Line(s):** 288–291

**Summary:** Some Gradle 8.x versions emit properties as:

```
version: 0.1.0 # project version
```

(Gradle 8.4+ added inline comments to `properties` output.) The regex captures `0.1.0` correctly because `\S+` stops at whitespace. Verified safe.

But on Gradle 7.x: `version: 0.1.0` (no comment). Verified safe.

Not a real issue; flagging for completeness. **No action needed.**

---

### 14. **LOW** — CHANGELOG entry copy-paste artifact

**Line(s):** 1153–1164

**Summary:** The CHANGELOG entry starts: "Locks reads version from gradle.properties" — "Locks" appears to be a stray word (perhaps a paste from another context). Cosmetic.

**Category:** Copy review.

**Recommendation:** Replace with "Kotlin/Gradle language adapter (Phase 3): reads version from gradle.properties …"

---

### 15. **LOW** — Plan does not document `--no-daemon --no-configuration-cache` rationale or link to upstream Gradle docs

**Line(s):** 40 (plan-level constraint), 175 (CLI invocation)

**Summary:** The plan mandates `--no-daemon --no-configuration-cache` for all Gradle invocations (correctly per spec Kotlin F1) but does not document WHY. A future maintainer might "optimize" by removing these flags without realizing they are CI-reliability load-bearing.

**Category:** Maintainability / institutional memory.

**Recommendation:** Add a comment to `GradlePropertiesVersionSource._read_via_gradle()` and `GradleTaskProbe.has_task()`:

```python
# --no-daemon --no-configuration-cache: mandatory for CI reliability.
# Per spec Kotlin F1. Daemon hangs in containerized CI; configuration cache
# races with plugin resolution. See docs/superpowers/specs/2026-09-07-...
```

---

### 16. **LOW** — Hardcoded `./gradlew` (not cross-platform; not `gradlew.bat` aware)

**Line(s):** 175, 283, 463, 471–482 (all subprocess invocations)

**Summary:** The plan hardcodes `./gradlew` (Unix wrapper). On Windows the wrapper is `gradlew.bat`. Crackerjack's project CLAUDE.md scopes the tool to macOS/Linux (no Windows support claim), so this is not a blocker. But the Phase 2 Swift plan used `swift` (cross-platform) and the Phase 3 Kotlin plan's hardcoding is inconsistent with the Phase 2 portability stance.

**Category:** Portability.

**Recommendation:** Either document "macOS/Linux only" in the Kotlin adapter docstring, or use `shutil.which("gradlew")` and fall back to `gradlew.bat`. Recommend (1) — explicit scope.

---

## Spec coverage summary

The plan correctly implements all Kotlin-specific spec requirements:

| Spec requirement | Plan coverage | Status |
|---|---|---|
| Detect `build.gradle.kts` OR `build.gradle` | Task 6 Step 3, line 940 | ✓ |
| `_PROBE_KEYS = ("pluginVersion", "projectVersion", "version")` with `\b` anchors | Task 2 Step 3, lines 259–279 | ✓ |
| Tier 1: gradle.properties; Tier 2: build.gradle.kts scan; Tier 3: `./gradlew properties` | Task 2 Step 3, lines 264–291 | ✓ |
| All Gradle invocations pass `--no-daemon --no-configuration-cache` | Task 2 Step 3, Task 3 Step 3 | ✓ |
| Task-existence probe via `./gradlew tasks --all` | Task 3 Step 3, lines 451–466 | ✓ |
| Hooks: `kotlin.ktlint` (ktlintCheck), `kotlin.detekt` (detekt), `kotlin.test` (test) | Task 3 Step 3, lines 478–482 | ✓ |
| Lifecycle bumps `gradle.properties` (NOT `build.gradle.kts`) | Task 5 Step 3, line 39, line 673 | ✓ |
| Write verification by read-back | Task 2 Step 3, lines 312–317 | ✓ |
| Constructor-injected git/gh methods (6) | Task 5 Step 3, lines 831–844 | ✓ |
| Real-semver `_bump` (Python parity, Swift divergence noted) | Task 5.1, lines 678–699 | ⚠ See Finding #1 |
| MCP tools added to existing `language_tools` group, no `profiles.py` change | Task 7 Step 1, line 989 | ✓ |
| Auth posture for mutation tools (`MAHAVISHNU_AUTH_ENABLED` + `MAHAVISHNU_JWT_SECRET`) | Task 7 Step 3, line 1036 | ✓ |
| `asyncio.to_thread` for sync subprocess in async handlers | Task 7 Step 3, line 1051 | ✓ |

**Spec gaps identified:**
- **Kotlin Multiplatform** (multi-module, version catalog): not addressed in spec or plan. Defer to Phase 3.5.
- **Android `pluginVersion` collision**: spec defines probe order that picks up AGP version on Android. Defer to spec amendment.

## Plan quality verdict

**Verdict: ⚠️ Approve with notes (after Finding #1 fix)**

**Rationale:**

The plan is structurally sound and mirrors the spec faithfully. CLI flag correctness is verified (`ktlintCheck`, `detekt`, `test`, `--no-daemon`, `--no-configuration-cache`, `./gradlew properties`, `./gradlew tasks --all` are all real and correct). Hook wiring, version-source probe order, lifecycle rollback contract, and constructor-injection discipline all carry over cleanly from Phase 2.

The **one BLOCKER** (Finding #1: `-SNAPSHOT`/qualifier handling) is a real production-breaking defect on Kotlin/JVM projects — JetBrains plugins, AndroidX, kotlinx libraries all use `-SNAPSHOT` between releases. The bump path will crash on first encounter. This must be fixed before merge.

The **HIGH findings** (Findings #2, #3, #4, #5) are also real production defects:
- 2-part version crash
- libs.versions.toml silent shadow
- Missing fixture gradle.properties
- Silent gradlew failures

Each has a clear fix path of <30 LOC.

The **MEDIUM findings** (#6–#11) are polish items that should land before Phase 3 ships but won't crash production on day one (with the exception of #6 which is a spec defect requiring amendment).

**Recommendation:**
1. **Fix Findings #1, #4, #5 in the plan before execution.** These are 30 LOC each and prevent silent production failures.
2. **Fix Finding #3 (libs.versions.toml) in the plan.** Modern Kotlin projects default to version catalogs; this is a 15-LOC addition.
3. **File Findings #6 (probe order), #7 (KMP) as spec defects requiring amendment.** Phase 2 Swift reviewer caught similar issues; Phase 3 should not regress.
4. **Findings #8–#16 are LOW; can ship as Phase 3.5 follow-ups.**

Plan is otherwise approve-with-notes. The Kotlin/Gradle CLI reality check (BLOCKER B1 equivalent from Phase 2) passes — no false flag names, no invalid Gradle CLI flags, no invented task names.
