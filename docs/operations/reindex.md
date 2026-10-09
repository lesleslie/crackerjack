---
status: active
role: operations
kind: how-to
date: 2026-10-09
last_reviewed: 2026-10-09
superseded_by: null
blocks_on: []
topic: operations
---

# Semantic Search Index — Reindex Procedure

When `mcp__crackerjack__search_semantic` returns `status="degraded"` with
`hint` mentioning this doc, the on-disk semantic index at
`.crackerjack/semantic_index.db` is empty. This file documents the
supported procedure to populate it.

## Why the index is empty

The crackerjack project does **not** auto-index a workspace. The semantic
search surface (`search_semantic`) is a thin wrapper over a SQLite-backed
`VectorStore` at `<cwd>/.crackerjack/semantic_index.db` (one file per
working directory). Nothing writes to that file until an operator calls
`index_file_semantic` (MCP) or `crackerjack index <path>` (CLI).

The fallback design: crackerjack is a quality-gate tool that runs over the
caller's repo on demand. There is no cron job, no startup-time reindex, no
discovery scan. Every index entry is explicitly placed.

## How to populate

### Option A — MCP tool, one file at a time

```python
# from any MCP client (Claude Code, etc.)
await client.call_tool("index_file_semantic", {
    "file_path": "/abs/path/to/file.py",
})
```

This indexes one file's chunks (512-token windows with 50-token overlap)
into the current working directory's index. Repeat per file.

### Option B — MCP tool, walk a directory

The MCP tool `index_file_semantic` indexes one file. To walk a directory,
loop from the caller side:

```python
from pathlib import Path

for py_file in Path("crackerjack").rglob("*.py"):
    if ".venv" in py_file.parts or "node_modules" in py_file.parts:
        continue
    await client.call_tool("index_file_semantic", {"file_path": str(py_file)})
```

### Option C — CLI: `crackerjack index`

```bash
# From the directory where you want the index to live (DB lives at ./.crackerjack/):
cd /path/to/project
crackerjack index crackerjack/   # recursively index all .py under crackerjack/
```

`crackerjack index <path>` walks `*.py` under `<path>` and indexes each
file, printing per-file chunk counts.

## Verifying the index is populated

After a reindex, the `status` field of `search_semantic` responses should
flip from `"degraded"` to `"ok"`. The MCP tool
`mcp__crackerjack__get_semantic_stats` reports `total_files` and
`total_chunks` directly.

## Operational notes

- **Index scope is cwd-bound.** `.crackerjack/semantic_index.db` is
  created relative to the current working directory. Running
  `crackerjack index /tmp/x` from `/` produces `/crackerjack/semantic_index.db`.
  To switch the index, `cd` first.
- **No incremental write path is exposed.** Changing a file's content
  re-indexes it fully (delete-then-insert in the same transaction). The
  `crackerjack index` driver currently only adds new files; it does not
  refresh changed files. See `crackerjack/services/vector_store.py:101
  ::index_file()` for the add-or-update contract.
- **The `crackerjack run` quality gate does not depend on the semantic
  index.** The `crackerjack run -v` gate runs ruff, mypy, pyright, bandit,
  complexipy, pytest. Search is an observability surface; it is not on
  the gate. A degraded semantic index does not fail the gate.

## Related

- Tool source: `crackerjack/mcp/tools/semantic_tools.py:75` (handler).
- Indexer: `crackerjack/services/vector_store.py:101` (`index_file`).
- Plan: `mahavishnu/docs/plans/2026-10-09-bodai-search-infrastructure-fix.md`
  § Phase 2 (crackerjack).
