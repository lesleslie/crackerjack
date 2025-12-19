> Crackerjack Docs: [Main](../../../README.md) | [Adapters](../README.md) | [SAST](./README.md)

# SAST Adapters

Static Application Security Testing tools for finding code vulnerabilities and security anti-patterns.

## Overview

SAST (Static Application Security Testing) adapters analyze source code for security vulnerabilities, insecure practices, and exploitable weaknesses. Unlike secret detection (gitleaks), SAST tools focus on application code quality and security patterns.

## Built-in Implementations

| Module | Description | Status | Recommended |
| ------ | ----------- | ------ | ----------- |
| `semgrep.py` | Multi-language static analysis with extensive rulesets | Stable | ✅ Primary |
| `bandit.py` | Python security linter with severity/confidence thresholds | Stable | Legacy |
| `pyscn.py` | Python security static analyzer | Experimental | ❌ No |

## Protocol Interface

All SAST adapters implement `SASTAdapterProtocol` defined in `_base.py`:

```python
from crackerjack.adapters.sast import SASTAdapterProtocol, SemgrepAdapter

adapter: SASTAdapterProtocol = SemgrepAdapter()
await adapter.init()
result = await adapter.check(files=[Path("src/")])
```

## Recommended: Semgrep

Semgrep is the recommended SAST tool for Crackerjack due to:

- **Multi-language support** (Python, JS, Go, etc.)
- **Extensive rulesets** (`p/security-audit`, `p/python`, custom rules)
- **Active development** (r2c/semgrep community)
- **Better accuracy** than legacy Python-only tools

### Example: Semgrep

```python
from pathlib import Path
from crackerjack.adapters.sast.semgrep import SemgrepAdapter, SemgrepSettings


async def run_semgrep() -> None:
    adapter = SemgrepAdapter(
        settings=SemgrepSettings(
            config="p/security-audit",  # Comprehensive security ruleset
            exclude_tests=True,
        )
    )
    await adapter.init()
    result = await adapter.check(files=[Path("src/")])

    for issue in result.issues:
        print(f"{issue.severity}: {issue.file_path}:{issue.line_number}")
        print(f"  {issue.message}")
```

## Legacy: Bandit

Bandit remains available but is superseded by Semgrep:

```python
from pathlib import Path
from crackerjack.adapters.sast.bandit import BanditAdapter, BanditSettings


async def run_bandit() -> None:
    adapter = BanditAdapter(
        settings=BanditSettings(
            severity_level="high",  # Reduce noise
            confidence_level="high",
        )
    )
    await adapter.init()
    result = await adapter.check(files=[Path("src/")])
```

## Configuration

### SAST in Comprehensive Hooks

SAST tools run in the **comprehensive stage** (after fast hooks):

```python
# crackerjack/config/hooks.py
HookDefinition(
    name="semgrep",
    command=[],
    timeout=1200,  # 20 minutes for thorough scanning
    stage=HookStage.COMPREHENSIVE,
    manual_stage=True,
    security_level=SecurityLevel.CRITICAL,
    use_precommit_legacy=False,
    accepts_file_paths=True,
)
```

### QACheckType

All SAST adapters use `QACheckType.SAST`:

```python
from crackerjack.models.qa_results import QACheckType

# SAST = code vulnerability analysis
# SECURITY = secret leak prevention (gitleaks)
assert adapter._get_check_type() == QACheckType.SAST
```

## Comparison: SAST vs Security

| Category | Purpose | Tools | Stage | Scope |
|----------|---------|-------|-------|-------|
| **SAST** | Find code vulnerabilities | Semgrep, Bandit, Pyscn | Comprehensive | `**/*.py` |
| **Security** | Prevent credential leaks | Gitleaks | Fast | `**/*` |

## Notes

- **Semgrep is recommended** for new projects and comprehensive coverage
- Bandit legacy support maintained for existing workflows
- Pyscn is experimental and disabled by default
- SAST tools complement (not replace) secret detection

## Related

- [Security](../security/README.md) — Secret leak prevention with Gitleaks
- [Type](../type/README.md) — Type safety prevents classes of vulnerabilities
- [Lint](../lint/README.md) — Code quality supports secure coding practices
