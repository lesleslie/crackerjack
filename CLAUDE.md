# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent Discovery Configuration

This project has access to **83 specialized AI agents** located in `/Users/les/.claude/agents/`. These agents are available via symlinks in `.claude/agents/` and through the global configuration.

### How to Use Agents

**Via Task Tool:**

```
Use the Task tool with subagent_type="agent-name" parameter
Example: subagent_type="python-pro" for Python-specific tasks
Example: subagent_type="security-auditor" for security reviews
```

**Via /agents Command:**
Run `/agents` in Claude Code to browse and manage all available agents interactively.

### Available Agent Categories

- **Programming Languages** (8): Python, JavaScript, TypeScript, Go, Rust, Java, C/C++, Flutter
- **Databases & Storage** (9): PostgreSQL, MySQL, SQLite, Redis, Vector Databases
- **AI & Machine Learning** (4): Gemini AI, Vector embeddings, General AI/ML, MLOps
- **Communication Protocols** (4): WebSocket, gRPC, GraphQL, REST APIs
- **Frontend & Design** (8): React/Vue, HTMX, CSS, Web Components, PWA, accessibility
- **Backend & Architecture** (6): Backend design, authentication, microservices, performance
- **DevOps & Infrastructure** (8): Docker, Terraform, cloud platforms, Kubernetes, monitoring
- **Testing & Quality** (5): General testing, pytest/hypothesis, test creation, consolidation
- **Security & Compliance** (3): Security auditing, authentication, critical audit reviews
- **Meta & Optimization** (13): Agent creation, code review, debugging, refactoring, DX optimization

### Tools & Workflows

- **49 Development Tools**: Located in `.claude/commands/tools/` (symlinked)
- **15 Multi-Agent Workflows**: Located in `.claude/commands/workflows/` (symlinked)

Use `/workflows:WORKFLOW-CATALOG` to discover the right workflow for any task.

### Troubleshooting

If agents are not discovered:

1. Check that `.claude/agents/` directory exists with symlinks
1. Verify `additionalDirectories` includes `/Users/les/.claude` in `.claude/settings.local.json`
1. Run `/agents` command to refresh agent list
1. Restart Claude Code session if needed

For more details, see `/Users/les/.claude/CLAUDE.md`
