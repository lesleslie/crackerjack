---
status: active
role: canonical
date: 2026-07-17
last_reviewed: 2026-11-14
superseded_by:
blocks_on: []
topic: mcp-design
---

# Adapter UUID Registry

**Generated**: 2025-12-27
**Last updated**: 2026-11-14
**Purpose**: Static UUID assignments for the retired QA adapter layer
**Total**: 19 adapters (all retired)

## Status

The QA adapter layer was removed on 2026-11-14. Tool output is now parsed
through a single taxonomy — the parser registry in `crackerjack/parsers/`
— and the per-tool adapter wrappers that used to carry these UUIDs are
gone. See `docs/plans/2026-11-14-consolidate-tool-taxonomies.md`.

The UUIDs below are **retained as historical identifiers**. They are not
assigned to any live module, and no code reads this file. They are kept
so that an audit trail, migration note, or incident report that cites
one of these values can still be resolved to the adapter it referred to.

Do not reuse any of these UUIDs for a new module.

## Retired UUID Assignments

These UUIDs are **permanent** and must never change once assigned. They uniquely identify each adapter across all Crackerjack installations.

### AI Adapters

```python
claude = UUID("514c99ad-4f9a-4493-acca-542b0c43f95a")
```

### Complexity Adapters

```python
complexipy = UUID("33a3f9ff-5fd2-43f5-a6c9-a43917618a17")
```

### Dependency Adapters

```python
pip_audit = UUID("c0e53073-ee73-42c2-b42f-7a693708fd0c")
```

### Format Adapters

```python
mdformat = UUID("d6db665f-1aa2-43d7-954f-3d13a055bdbd")
ruff = UUID("c38609f7-f4a4-43ac-a7af-c55ef522c615")
```

### Lint Adapters

```python
codespell = UUID("b42b5648-52e1-4a89-866f-3f9821087b0b")
```

### LSP Adapters

```python
skylos_lsp = UUID("c39f341c-1563-4fe3-b662-117175c62c2b")
zuban_lsp = UUID("c423ea06-53f0-4ff8-84fd-554257fe2668")
```

### Refactor Adapters

```python
creosote = UUID("c4c0c9fc-43d8-4b17-afb5-4febacec2e90")
refurb = UUID("0f3546f6-4e29-4d9d-98f8-43c6f3c21a4e")
skylos_refactor = UUID(
    "445401b8-b273-47f1-9015-22e721757d46"
)  # Note: skylos appears in both LSP and refactor
```

### SAST (Security) Adapters

```python
bandit = UUID("1a6108e1-275a-4539-9536-aa66abfe7cd6")
pyscn = UUID("658dfd25-e475-4e28-9945-23ff31c30b0a")
semgrep = UUID("bff2e3e9-9b3c-49b7-a8c0-526fe56b0c37")
```

### Security Adapters

```python
gitleaks = UUID("6deed37d-f943-44f5-a188-f2b287f7a17d")
```

### Type Checking Adapters

```python
pyrefly = UUID("25e1e5cf-d1f8-485e-85ab-01c8b540734a")
ty = UUID("624df020-07cb-491f-9476-ca6daad3ba0b")
zuban_type = UUID(
    "e42fd557-ed29-4104-8edd-46607ab807e2"
)  # Note: zuban appears in LSP and type
```

### Utility Adapters

```python
checks = UUID("ed516d6d-b273-458a-a2fc-c656046897cd")
```

## Notes

- **Duplicate Detection**: `skylos` appears in both `lsp/` and `refactor/` directories - assigned separate UUIDs
- **Zuban**: Also appears in both `lsp/` and `type/` directories - assigned separate UUIDs
- **UUID Format**: Standard UUID4 format (fallback, as uuidv7 not installed)
- **Immutability**: These UUIDs are permanent identifiers - do not regenerate

## Retirement Checklist

Modules that carried these UUIDs. Every one was deleted on 2026-11-14
along with the QA adapter layer.

- [x] ai/claude.py
- [x] complexity/complexipy.py
- [x] dependency/pip_audit.py
- [x] format/mdformat.py
- [x] format/ruff.py
- [x] lint/codespell.py
- [x] lsp/skylos.py
- [x] lsp/zuban.py
- [x] refactor/creosote.py
- [x] refactor/refurb.py
- [x] refactor/skylos.py
- [x] sast/bandit.py
- [x] sast/pyscn.py
- [x] sast/semgrep.py
- [x] security/gitleaks.py
- [x] type/pyrefly.py
- [x] type/ty_adapter.py
- [x] type/zuban.py
- [x] utility/checks.py
