# Adapters

Interfaces and adapters to external tools/services or subsystems.

The QA adapter layer was removed on 2026-11-14. What remains here is the
language-adapter registry (`base.py`, `registry.py`, `kotlin/`, `python/`,
`swift/`, `web/`) and the AI provider registry (`ai/`).

## Index

- [AI](./ai/README.md) — Claude-powered code fixing and AI helpers
- [Language adapter base](./base.py) — The `LanguageAdapter` protocol and
  shared adapter primitives
- [Language adapter registry](./registry.py) — Entry-point discovery for
  third-party language adapters

## Historical note

The removed QA adapter categories are recorded in
`docs/plans/2026-11-14-consolidate-tool-taxonomies.md`. Their old package
README files and category pages were deleted along with the adapters they
used to describe.
