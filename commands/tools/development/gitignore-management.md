______________________________________________________________________

name: gitignore-management
description: Manage and standardize .gitignore files across project repositories. Ensures consistent ignore patterns for Python development, build artifacts, caches, and project-specific files.

## model: sonnet

## Overview

This tool helps maintain consistent `.gitignore` files across all repositories by:

- Standardizing common Python/development patterns
- Managing project-specific ignore rules
- Preventing accidental commits of generated files
- Ensuring all repos have proper .gitignore coverage

## Features

### Check Repository Gitignores

Verify `.gitignore` exists and contains essential patterns for:

- Python cache files (__pycache__/)
- Build artifacts (dist/, build/, \*.egg-info)
- Test coverage (htmlcov/, .coverage, \*.py,cover)
- Development tools (.vscode/, .idea/)
- IDE files (\*.swp, \*.swo)
- Log files (\*.log, logs/)
- Environment files (.env, .venv/)
- OS files (.DS_Store, Thumbs.db)
- Crackerjack files (.crackerjack/)
- Tool caches (.complexipy_cache/, .oneiric_cache/)
- Analysis results (complexipy_results*.json)

### Standardize Gitignore Patterns

Apply standardized template to repositories:

1. Python-generated patterns
1. Python C extensions
1. Distribution/packaging
1. Test/coverage reports
1. Type checking/linting
1. Package management
1. IDE/editor files
1. Logs
1. OS-specific files
1. Local configuration
1. Sensitive configuration
1. Crackerjack integration
1. Archived files
1. Project-specific section

### Verify Coverage

Check which repositories have `.gitignore` and identify gaps:

```bash
cd /Users/les/Projects
for dir in */; do
  if [ ! -f "$dir/.gitignore" ]; then
    echo "$dir - Missing .gitignore"
  fi
done
```

### Add Archive Patterns

Ensure `.archive/` is in `.gitignore` for all repos to prevent archiving generated files:

```bash
echo ".archive/" >> /path/to/repo/.gitignore
```

### Update Crackerjack Workflows

Add `.gitignore` management steps to:

- crackerjack run: Create .gitignore workflow
- crackerjack sweep: Check .gitignore coverage
- crackerjack init: Verify .gitignore presence

## Usage

### Interactive Mode

```bash
# Check which repos need .gitignore
crackerjack run gitignore-management check

# Standardize a specific repo
crackerjack run gitignore-management standardize --repo mahavishnu

# Standardize all repos
crackerjack run gitignore-management standardize-all
```

### CLI Mode

```bash
# List all repos and their .gitignore status
crackerjack run gitignore-management list

# Apply template to repo
crackerjack run gitignore-management apply --repo /path/to/repo
```

## Implementation

### Requirements

- [ ] Template system exists (GITIGNORE_TEMPLATE.md)
- [ ] Check command works across all project types
- [ ] Handle non-Python projects (skip certain patterns)
- [ ] Preserve project-specific section when updating
- [ ] Backup existing .gitignore before changes

### Priority

1. **HIGH**: Create basic check/apply commands
1. **MEDIUM**: Add interactive mode with --options
1. **LOW**: Add batch mode for multiple repos
