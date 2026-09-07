# >>> bodai-shared-gitignore >>>
# Source of truth: crackerjack/templates/GITIGNORE_BODAI.md
# Enforced by: crackerjack check `gitignore-conformance`
# Fleet list: /Users/les/Projects/mahavishnu/BODAI_REPO_REGISTRY.md
# Do NOT remove the marker line above — `crackerjack gitignore sync` uses it
# to detect already-applied state.

# Editor / pre-edit backups (foo.py.backup, foo.py.backup.json)
*.backup
*.backup.*
*.bak
*.tmpl
# XDG mistake dirs (env var expansion failed; literal names)
# Note: both `{` and `}` are escaped (`{` -> `[{]`, `}` -> `[}]`)
# because gitignore parsers interpret `${...}` as a brace-expansion
# alternate group; escaping only the open brace leaves a stray `}`.
~
[{]HOME[}]
[{]XDG_DATA_HOME:-$HOME[}]
# pytest-benchmark autosave cache (sibling of the tracked `benchmarks/` test suite)
.benchmarks/
# Vitest config timestamp cache
vitest.config.js.timestamp-*.mjs
# Playwright output cruft
playwright-junit.xml
playwright-report/
playwright-results.json
test-results/
# <<< bodai-shared-gitignore <<<