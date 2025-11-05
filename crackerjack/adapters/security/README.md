> Crackerjack Docs: [Main](../../../README.md) | [Adapters](../README.md) | [Security](./README.md)

# Security Adapters

Static analysis for common vulnerabilities and secret leakage with structured diagnostics.

## Overview

- Security linting for Python code (Bandit)
- Secrets and credential scanning (Gitleaks)
- Additional static analysis (Pyscn; experimental)

## Built-in Implementations

| Module | Description | Status |
| ------ | ----------- | ------ |
| `bandit.py` | Python security linter with severity/confidence thresholds | Stable |
| `gitleaks.py` | Git-aware secrets/credentials detection with redaction | Stable |
| `pyscn.py` | Python security static analyzer | Experimental |

## Examples

Bandit:

```python
from pathlib import Path
from crackerjack.adapters.security.bandit import BanditAdapter, BanditSettings


async def run_bandit() -> None:
    adapter = BanditAdapter(settings=BanditSettings(severity_level="medium"))
    await adapter.init()
    result = await adapter.check(files=[Path("src/")])
```

Gitleaks (protect mode for working tree):

```python
from pathlib import Path
from crackerjack.adapters.security.gitleaks import GitleaksAdapter, GitleaksSettings


async def scan_secrets() -> None:
    adapter = GitleaksAdapter(settings=GitleaksSettings(scan_mode="protect", redact=True))
    await adapter.init()
    result = await adapter.check(files=[Path(".")])
```

## Notes

- Keep Bandit thresholds realistic (`severity_level` and `confidence_level`)
- Use Gitleaks baseline/config to manage known false positives
- Pyscn is experimental and disabled by default

## Related

- [Type](../type/README.md) — Type safety can prevent classes of security bugs
- [Lint](../lint/README.md) — Clean text and naming supports code clarity
