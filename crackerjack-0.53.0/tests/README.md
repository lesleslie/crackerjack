# Tests

Test suite mirroring the `crackerjack/` package layout. Prefer fixtures from `tests/conftest.py` and reuse documentation assets from `test_docs_site/`.

- Run: `uv run pytest --maxfail=1`
- Markers: `chaos`, `ai_generated`, `breakthrough`
- Coverage target: ≥42% (see `coverage.json` / `htmlcov/`)
