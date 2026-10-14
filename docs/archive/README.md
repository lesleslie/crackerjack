# Archived Documentation

This directory contains historical documentation from previous development phases, organized by topic.

## Directory Structure

### `sprints/`

Coverage improvement sprint documentation and completion reports:

- SPRINT2-7: Coverage ratchet improvement phases
- Test marking and optimization work
- Coverage analysis and progress tracking

### `config-automation/`

Configuration and template automation work:

- Template application and deployment automation
- Configuration simplification progress
- Pyproject.toml configuration audit

### `performance/`

Performance analysis and optimization recommendations:

- Critical performance findings
- Coverage optimization strategies
- General optimization recommendations

### `cleanup/`

Code cleanup and simplification work:

- Cleanup corrections and recommendations
- CLI options removal
- Stub cleanup initiatives

### `summaries/`

High-level initiative and completion summaries:

- Complete initiative summaries
- Cross-phase overview documents

### `test-fixing/`

Historical test fixing and debugging sessions:

- Test fix progress reports
- Test failure analysis
- Verification scripts and plans

### `sessions/`

Checkpoint and session documentation:

- Periodic checkpoint summaries
- Session progress tracking

## Active vs Archived

**Active Documentation** (kept in project root):

- `README.md` - Main project overview
- `CLAUDE.md` - AI agent instructions
- `CHANGELOG.md` - Version history
- `RULES.md` - Coding rules
- `SECURITY.md` - Security policy
- `TY_PYREFLY_MIGRATION_PLAN.md` - Active migration plan
- `SPRINT7_PLAN.md` - Active sprint plan

**Archived Documentation** (this directory):

- Historical sprint completions
- Superseded test fixing sessions
- Completed configuration work
- Past performance analysis

## Migration Policy

When archiving documentation:

1. Move to appropriate subdirectory by topic
1. Update this README with brief description
1. Add cross-references if related to active work
1. Do NOT delete without consensus (historical record)

## Searching Archived Docs

To find archived documentation:

```bash
# Search by keyword
grep -r "keyword" docs/archive/

# Find by date
find docs/archive/ -name "*.md" -mtime -30

# List all archived files
find docs/archive/ -type f -name "*.md"
```

## Restoration

If archived documentation becomes relevant again:

1. Copy back to project root (if active work)
1. Update cross-references
1. Consider merging with newer documentation
1. Delete from archive when superseded
