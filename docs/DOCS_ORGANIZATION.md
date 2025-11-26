# Crackerjack Documentation Organization

## Overview

This document provides a comprehensive overview of the documentation organization in the Crackerjack project after the cleanup and reorganization effort.

## Documentation in Root Directory

The following documentation files are intentionally kept in the root directory as they serve as key reference documents for the project:

- `README.md` - Main project overview and usage documentation
- `AGENTS.md` - Repository guidelines and agent-related information
- `CLAUDE.md` - AI assistant guidelines and developer commands
- `RULES.md` - Coding standards and style rules
- `QWEN.md` - Project overview specific to Qwen Code integration
- `CHANGELOG.md` - Project release history
- `SECURITY.md` - Security policy and practices

## Documentation in ./docs Directory

The `./docs` directory is organized into subdirectories based on the purpose and audience of the documentation:

### ./docs/reference

- `COVERAGE_POLICY.md` - Test coverage policies and requirements

### ./docs/implementation

- Implementation plans, audit reports, and technical documentation
- Files related to hooks, issue tracking, and development workflows

### ./docs/development

- Development-related documentation, including logging and display implementations

### ./docs/archives

- Historical implementation plans and audit results
- Completed project summaries and planning documents
- Implementation plans, investigation reports, and analysis documents

## Notes

1. Key documentation files (AGENTS.md, CLAUDE.md, RULES.md, QWEN.md) are kept in the root directory as they are frequently accessed and provide essential guidance for developers.

1. The `./docs` directory contains more specialized documentation that is less frequently accessed but still important for project understanding and maintenance.

1. All internal documentation references have been updated to point to the correct locations after reorganization.

1. The overall documentation structure is now cleaner with a clear separation between primary reference documents (in root) and specialized documentation (in docs subdirectories).
