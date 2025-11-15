> Crackerjack Docs: [Main](<../../../README.md>) | [Adapters](<../README.md>) | [Security](<./README.md>)

# Security Adapters

Secret leak prevention and credential detection for git repositories.

## Overview

Security adapters focus on **preventing credential leaks** by detecting hardcoded secrets, API keys, and tokens before they enter the repository. This complements SAST tools (which analyze code vulnerabilities).

## Built-in Implementations

| Module | Description | Status |
| ------ | ----------- | ------ |
| `gitleaks.py` | Git-aware secrets/credentials detection with redaction | Stable |

**Note:** SAST tools (Bandit, Semgrep, Pyscn) have been moved to [crackerjack.adapters.sast](<../sast/README.md>)

## Example: Gitleaks

Gitleaks runs in **fast stage** as a pre-commit security gate:

```python
from pathlib import Path
from crackerjack.adapters.security.gitleaks import GitleaksAdapter, GitleaksSettings


async def scan_secrets() -> None:
    adapter = GitleaksAdapter(
        settings=GitleaksSettings(
            scan_mode="protect",  # Scan working tree (pre-commit)
            redact=True,  # Redact secrets in output
        )
    )
    await adapter.init()
    result = await adapter.check(files=[Path(".")])

    for issue in result.issues:
        print(f"🔴 Secret detected: {issue.file_path}:{issue.line_number}")
        print(f"   Rule: {issue.code} - {issue.message}")
```

## Configuration

### Gitleaks in Fast Hooks

Gitleaks runs early in the workflow to **prevent** secrets from being committed:

```python
# crackerjack/config/hooks.py
HookDefinition(
    name="gitleaks",
    command=[],
    timeout=45,
    stage=HookStage.COMPREHENSIVE,  # Critical security check
    manual_stage=True,
    security_level=SecurityLevel.CRITICAL,
    use_precommit_legacy=False,
)
```

### Scan Modes

- **`protect` mode** (recommended): Scans staged files before commit
- **`detect` mode**: Scans entire git history for existing secrets

### Managing False Positives

Create `.gitleaks.toml` to allowlist known non-secrets:

```toml
[allowlist]
description = "Known false positives"
paths = [
    "tests/fixtures/mock_credentials.py",
    "docs/examples/api_key_template.md",
]
```

## Comparison: Security vs SAST

| Category | Purpose | Tools | Stage | Scope |
|----------|---------|-------|-------|-------|
| **Security** | Prevent credential leaks | Gitleaks | Fast | `**/*` |
| **SAST** | Find code vulnerabilities | Semgrep, Bandit | Comprehensive | `**/*.py` |

**Security** = Policy enforcement (no secrets in repo)
**SAST** = Vulnerability detection (exploitable code patterns)

## QACheckType

Security adapters use `QACheckType.SECURITY`:

```python
from crackerjack.models.qa_results import QACheckType

assert adapter._get_check_type() == QACheckType.SECURITY
```

## Notes

- **Universal scope**: Scans all files (`**/*`), not just Python
- **Git-aware**: Can scan history or working tree
- **Redaction**: Automatically redacts secrets in reports
- **Baseline support**: Manage known false positives with baseline files

## Related

- [SAST](<../sast/README.md>) — Code vulnerability analysis (Semgrep, Bandit)
- [Type](<../type/README.md>) — Type safety prevents classes of bugs
- [Lint](<../lint/README.md>) — Code quality supports security
