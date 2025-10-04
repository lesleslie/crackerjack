# Crackerjack Documentation

**Complete technical documentation for the Crackerjack Python project management tool**

---

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Documentation Structure](#-documentation-structure)
- [For New Users](#-for-new-users)
- [For Contributors](#-for-contributors)
- [Directory Guide](#-directory-guide)
- [Cross-References](#-cross-references)
- [Maintenance](#-maintenance)

---

## 🚀 Quick Start

### Most Common Documentation Needs

| I want to... | Go to... |
|--------------|----------|
| **Learn basic commands** | [`ai/AI-REFERENCE.md`](ai/AI-REFERENCE.md) - Command decision trees |
| **Understand the architecture** | [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md) - System overview |
| **Configure my IDE** | [`development/IDE-SETUP.md`](development/IDE-SETUP.md) - IDE integration |
| **Use AI auto-fix** | [`guides/AUTO_FIX_GUIDE.md`](guides/AUTO_FIX_GUIDE.md) - AI agent guide |
| **Find advanced features** | [`guides/ADVANCED-FEATURES.md`](guides/ADVANCED-FEATURES.md) - 82 enterprise flags |
| **Integrate with MCP** | [`systems/MCP_INTEGRATION.md`](systems/MCP_INTEGRATION.md) - MCP server setup |
| **Set up monitoring** | [`systems/UNIFIED_MONITORING_ARCHITECTURE.md`](systems/UNIFIED_MONITORING_ARCHITECTURE.md) - Dashboard system |
| **Review security** | [`security/SECURITY_AUDIT.md`](security/SECURITY_AUDIT.md) - Security audit |

---

## 📁 Documentation Structure

```
docs/
├── ai/                  # AI agent system & command reference
├── architecture/        # System architecture & API reference
├── development/         # Development setup & tooling
├── guides/              # User guides & feature documentation
├── planning/            # Active planning & implementation docs
├── security/            # Security audits & hardening
├── systems/             # Core system documentation
└── history/             # Historical records & archives
    ├── investigations/  # Bug investigations & fixes
    ├── phases/          # Development phase summaries
    ├── planning/        # Archived planning documents
    ├── precommit/       # Pre-commit system history
    └── security/        # Historical security audits
```

---

## 👤 For New Users

### Recommended Reading Order

1. **Start Here** 🎯
   - [`ai/AI-REFERENCE.md`](ai/AI-REFERENCE.md) - Learn the essential commands
   - Visual decision trees help you choose the right command

2. **Understand the System** 🏗️
   - [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md) - System overview
   - [`architecture/WORKFLOW-ARCHITECTURE.md`](architecture/WORKFLOW-ARCHITECTURE.md) - How workflows operate

3. **Set Up Your Environment** ⚙️
   - [`development/IDE-SETUP.md`](development/IDE-SETUP.md) - IDE configuration
   - [`development/RUST_TOOLING_FRAMEWORK.md`](development/RUST_TOOLING_FRAMEWORK.md) - Rust tool integration

4. **Master Key Features** 🔑
   - [`guides/AUTO_FIX_GUIDE.md`](guides/AUTO_FIX_GUIDE.md) - AI auto-fix capabilities
   - [`guides/ADVANCED-FEATURES.md`](guides/ADVANCED-FEATURES.md) - Power user features

5. **Explore Advanced Topics** 🚀
   - [`systems/MCP_INTEGRATION.md`](systems/MCP_INTEGRATION.md) - MCP server integration
   - [`systems/UNIFIED_MONITORING_ARCHITECTURE.md`](systems/UNIFIED_MONITORING_ARCHITECTURE.md) - Monitoring dashboards
   - [`security/SECURITY_AUDIT.md`](security/SECURITY_AUDIT.md) - Security best practices

---

## 💻 For Contributors

### Development Documentation Path

1. **Architecture Deep Dive** 🏛️
   ```
   architecture/ARCHITECTURE.md           → System design & layers
   architecture/API_REFERENCE.md          → Public API documentation
   architecture/WORKFLOW-ARCHITECTURE.md  → Workflow orchestration
   ```

2. **AI Agent System** 🤖
   ```
   ai/AI-REFERENCE.md          → Command reference & decision trees
   ai/AGENT-CAPABILITIES.json  → Agent metadata (machine-readable)
   ai/AGENT_SELECTION.md       → Agent selection algorithm
   ai/ERROR-PATTERNS.yaml      → Automated error pattern matching
   ```

3. **Development Setup** 🛠️
   ```
   development/IDE-SETUP.md               → IDE configuration
   development/RUST_TOOLING_FRAMEWORK.md  → Rust integration patterns
   ```

4. **Active Planning** 📝
   ```
   planning/                              → Current implementation plans
   - COMPLEXITY_REFACTORING_PLAN.md       → Code complexity management
   - RESILIENT_HOOK_ARCHITECTURE_PLAN.md  → Hook system design
   - ZUBAN_LSP_INTEGRATION_PLAN.md        → LSP integration
   - [12 more active plans...]
   ```

5. **System Documentation** 📚
   ```
   systems/CACHING_SYSTEM.md              → Caching architecture
   systems/BACKUP_SYSTEM.md               → Backup & restore
   systems/DASHBOARD_ARCHITECTURE.md      → Dashboard design
   systems/MONITORING_INTEGRATION.md      → Monitoring integration
   ```

---

## 📖 Directory Guide

### `ai/` - AI Agent System (4 files)

The AI agent system powers automatic code fixing and quality improvements.

| File | Purpose | Key Contents |
|------|---------|--------------|
| [`AI-REFERENCE.md`](ai/AI-REFERENCE.md) | **Command reference guide** | Decision trees, command finder, workflow selection |
| [`AGENT-CAPABILITIES.json`](ai/AGENT-CAPABILITIES.json) | **Agent metadata** | Machine-readable agent capabilities, confidence scores |
| [`AGENT_SELECTION.md`](ai/AGENT_SELECTION.md) | **Selection algorithm** | How Crackerjack chooses the right agent for each issue |
| [`ERROR-PATTERNS.yaml`](ai/ERROR-PATTERNS.yaml) | **Error pattern matching** | Automated pattern recognition for common issues |

**Use Cases:**
- Finding the right command for your situation
- Understanding which AI agent handles which issues
- Contributing new error patterns

---

### `architecture/` - System Architecture (3 files)

Core architectural documentation for understanding and extending Crackerjack.

| File | Purpose | Key Contents |
|------|---------|--------------|
| [`ARCHITECTURE.md`](architecture/ARCHITECTURE.md) | **System overview** | Layers, components, data flow, performance characteristics |
| [`API_REFERENCE.md`](architecture/API_REFERENCE.md) | **Public API** | CLI interface, MCP tools, Python API, protocols |
| [`WORKFLOW-ARCHITECTURE.md`](architecture/WORKFLOW-ARCHITECTURE.md) | **Workflow design** | Orchestration patterns, phase coordination, execution flow |

**Use Cases:**
- Understanding the system design
- Contributing to core components
- Integrating Crackerjack into other tools

---

### `development/` - Development Setup (2 files)

Essential documentation for setting up your development environment.

| File | Purpose | Key Contents |
|------|---------|--------------|
| [`IDE-SETUP.md`](development/IDE-SETUP.md) | **IDE configuration** | VSCode, PyCharm, NeoVim settings and plugins |
| [`RUST_TOOLING_FRAMEWORK.md`](development/RUST_TOOLING_FRAMEWORK.md) | **Rust tool integration** | Skylos, Zuban integration patterns |

**Use Cases:**
- Setting up your IDE for Crackerjack development
- Understanding Rust tool integration
- Optimizing your development workflow

---

### `guides/` - User Guides (2 files)

Comprehensive user documentation and feature guides.

| File | Purpose | Key Contents |
|------|---------|--------------|
| [`AUTO_FIX_GUIDE.md`](guides/AUTO_FIX_GUIDE.md) | **AI auto-fix guide** | Agent capabilities, usage patterns, troubleshooting |
| [`ADVANCED-FEATURES.md`](guides/ADVANCED-FEATURES.md) | **Power user features** | 82 enterprise flags, advanced workflows, optimization |

**Use Cases:**
- Learning to use AI auto-fix effectively
- Discovering advanced features
- Enterprise deployment configuration

---

### `planning/` - Active Planning (15 files)

Current implementation plans and design documents. These are **living documents** updated during active development.

#### Implementation Plans
- [`COMPLEXITY_REFACTORING_PLAN.md`](planning/COMPLEXITY_REFACTORING_PLAN.md) - Code complexity reduction strategy
- [`COVERAGE_BADGE_IMPLEMENTATION_PLAN.md`](planning/COVERAGE_BADGE_IMPLEMENTATION_PLAN.md) - Coverage badge system
- [`FEATURE_IMPLEMENTATION_PLAN.md`](planning/FEATURE_IMPLEMENTATION_PLAN.md) - New feature roadmap
- [`RESILIENT_HOOK_ARCHITECTURE_PLAN.md`](planning/RESILIENT_HOOK_ARCHITECTURE_PLAN.md) - Resilient hook system design
- [`STAGE_HEADERS_IMPLEMENTATION_PLAN.md`](planning/STAGE_HEADERS_IMPLEMENTATION_PLAN.md) - Stage header UI design
- [`TIMEOUT_ARCHITECTURE_SOLUTION.md`](planning/TIMEOUT_ARCHITECTURE_SOLUTION.md) - Timeout handling architecture
- [`TYPE_ANNOTATION_FIXING_PLAN.md`](planning/TYPE_ANNOTATION_FIXING_PLAN.md) - Type annotation improvements
- [`ZUBAN_LSP_INTEGRATION_PLAN.md`](planning/ZUBAN_LSP_INTEGRATION_PLAN.md) - Zuban LSP integration

#### Documentation & System Design
- [`DOCUMENTATION_SYSTEM_ARCHITECTURE.md`](planning/DOCUMENTATION_SYSTEM_ARCHITECTURE.md) - Documentation architecture
- [`EXPERIMENTAL-EVALUATION.md`](planning/EXPERIMENTAL-EVALUATION.md) - Experimental feature evaluation criteria
- [`FUTURE-ENHANCEMENTS.md`](planning/FUTURE-ENHANCEMENTS.md) - Future roadmap
- [`SEMANTIC-SEARCH-IMPLEMENTATION.md`](planning/SEMANTIC-SEARCH-IMPLEMENTATION.md) - Semantic search design

#### Implementation Summaries
- [`CURRENT_IMPLEMENTATION_STATUS.md`](planning/CURRENT_IMPLEMENTATION_STATUS.md) - Current project status
- [`RESILIENT_HOOK_ARCHITECTURE_IMPLEMENTATION_SUMMARY.md`](planning/RESILIENT_HOOK_ARCHITECTURE_IMPLEMENTATION_SUMMARY.md) - Hook implementation summary
- [`UVXUSAGE.md`](planning/UVXUSAGE.md) - UVX usage patterns
- [`ZUBAN_TOML_PARSING_BUG_ANALYSIS.md`](planning/ZUBAN_TOML_PARSING_BUG_ANALYSIS.md) - Zuban bug analysis

**Use Cases:**
- Understanding upcoming features
- Contributing to active development
- Reviewing implementation strategies

---

### `security/` - Security Documentation (1 file)

Consolidated security audit and hardening documentation.

| File | Purpose | Key Contents |
|------|---------|--------------|
| [`SECURITY_AUDIT.md`](security/SECURITY_AUDIT.md) | **Security audit** | Vulnerability assessment, hardening measures, compliance |

**Use Cases:**
- Reviewing security posture
- Understanding security best practices
- Compliance verification

---

### `systems/` - System Documentation (6 files)

Core system documentation for advanced features and infrastructure.

| File | Purpose | Key Contents |
|------|---------|--------------|
| [`BACKUP_SYSTEM.md`](systems/BACKUP_SYSTEM.md) | **Backup & restore** | Backup strategies, restore procedures |
| [`CACHING_SYSTEM.md`](systems/CACHING_SYSTEM.md) | **Caching architecture** | Cache layers, invalidation, performance |
| [`DASHBOARD_ARCHITECTURE.md`](systems/DASHBOARD_ARCHITECTURE.md) | **Dashboard design** | UI components, data flow, visualization |
| [`MCP_INTEGRATION.md`](systems/MCP_INTEGRATION.md) | **MCP server** | MCP protocol, tools, slash commands |
| [`MONITORING_INTEGRATION.md`](systems/MONITORING_INTEGRATION.md) | **Monitoring integration** | Metrics, alerts, observability |
| [`UNIFIED_MONITORING_ARCHITECTURE.md`](systems/UNIFIED_MONITORING_ARCHITECTURE.md) | **Unified monitoring** | Comprehensive monitoring architecture |

**Use Cases:**
- Setting up monitoring and dashboards
- Understanding caching behavior
- MCP server integration
- Implementing backup strategies

---

### `history/` - Historical Records

Archived documentation organized by topic. These documents provide historical context and are **read-only references**.

#### `history/investigations/` (2 files)
Bug investigations and resolution documentation.

- [`ai-fix-flag-bug-fix.md`](history/investigations/ai-fix-flag-bug-fix.md) - AI fix flag bug resolution
- [`workflow-routing-fix.md`](history/investigations/workflow-routing-fix.md) - Workflow routing bug fix

#### `history/phases/` (11 files)
Development phase completion summaries and reports.

- Phase 1-5 completion summaries
- Cross-reference analyses
- Optimization plans
- Task completion reports

#### `history/planning/` (10 files)
Archived planning documents from completed initiatives.

- Config management replacement plans
- Documentation reorganization plans
- PyTorch compatibility fixes
- Refactoring summaries
- Workflow audit reports

#### `history/precommit/` (5 files)
Pre-commit system evolution and implementation history.

- [`README.md`](history/precommit/README.md) - Pre-commit history overview
- Cleanup summaries
- Implementation summaries
- Verification reports

#### `history/security/` (6 files)
Historical security audits and hardening reports.

- Input validator security audits
- Security audit reports
- Subprocess hardening reports
- Status disclosure documents

**Use Cases:**
- Understanding project evolution
- Learning from past decisions
- Finding historical context for current features

---

## 🔗 Cross-References

### Command to Documentation Mapping

| Command Flag | Primary Documentation |
|--------------|----------------------|
| `--ai-fix` | [`guides/AUTO_FIX_GUIDE.md`](guides/AUTO_FIX_GUIDE.md), [`ai/AGENT_SELECTION.md`](ai/AGENT_SELECTION.md) |
| `--dashboard` | [`systems/DASHBOARD_ARCHITECTURE.md`](systems/DASHBOARD_ARCHITECTURE.md) |
| `--unified-dashboard` | [`systems/UNIFIED_MONITORING_ARCHITECTURE.md`](systems/UNIFIED_MONITORING_ARCHITECTURE.md) |
| `--start-mcp-server` | [`systems/MCP_INTEGRATION.md`](systems/MCP_INTEGRATION.md) |
| `--benchmark` | [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md#performance-characteristics) |
| `--enterprise-*` | [`guides/ADVANCED-FEATURES.md`](guides/ADVANCED-FEATURES.md#enterprise-features) |
| `--zuban-lsp` | [`development/RUST_TOOLING_FRAMEWORK.md`](development/RUST_TOOLING_FRAMEWORK.md), [`planning/ZUBAN_LSP_INTEGRATION_PLAN.md`](planning/ZUBAN_LSP_INTEGRATION_PLAN.md) |

### Topic to Documentation Mapping

| Topic | Documentation Files |
|-------|-------------------|
| **AI Agents** | [`ai/AI-REFERENCE.md`](ai/AI-REFERENCE.md), [`ai/AGENT_SELECTION.md`](ai/AGENT_SELECTION.md), [`guides/AUTO_FIX_GUIDE.md`](guides/AUTO_FIX_GUIDE.md) |
| **Architecture** | [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md), [`architecture/WORKFLOW-ARCHITECTURE.md`](architecture/WORKFLOW-ARCHITECTURE.md) |
| **Performance** | [`systems/CACHING_SYSTEM.md`](systems/CACHING_SYSTEM.md), [`development/RUST_TOOLING_FRAMEWORK.md`](development/RUST_TOOLING_FRAMEWORK.md) |
| **Monitoring** | [`systems/UNIFIED_MONITORING_ARCHITECTURE.md`](systems/UNIFIED_MONITORING_ARCHITECTURE.md), [`systems/MONITORING_INTEGRATION.md`](systems/MONITORING_INTEGRATION.md) |
| **Security** | [`security/SECURITY_AUDIT.md`](security/SECURITY_AUDIT.md), [`history/security/`](history/security/) |
| **Development** | [`development/IDE-SETUP.md`](development/IDE-SETUP.md), [`planning/`](planning/) |
| **API Integration** | [`architecture/API_REFERENCE.md`](architecture/API_REFERENCE.md), [`systems/MCP_INTEGRATION.md`](systems/MCP_INTEGRATION.md) |

---

## 🔧 Maintenance

### Documentation Lifecycle

#### Active Documents
Located in top-level directories (`ai/`, `architecture/`, `development/`, `guides/`, `planning/`, `security/`, `systems/`)

- **Updated regularly** during development
- **Reflect current state** of the system
- **Living documents** that evolve with the codebase

#### Archived Documents
Located in `history/` subdirectories

- **Historical reference** only
- **Not updated** after archiving
- **Provide context** for current decisions

### When to Archive a Document

Archive a planning document when:
1. ✅ Implementation is complete
2. ✅ Feature is stable and tested
3. ✅ No active development planned
4. ✅ Content is fully integrated into active documentation

### Archive Process

```bash
# Move completed planning document to history
mv docs/planning/COMPLETED_FEATURE.md docs/history/planning/

# Update cross-references in active docs
# Document archive date in HISTORY.md
```

### Document Organization Rules

| Directory | Purpose | Update Frequency |
|-----------|---------|-----------------|
| `ai/` | AI system reference | As AI agents evolve |
| `architecture/` | System architecture | When architecture changes |
| `development/` | Dev environment | When tools/setup changes |
| `guides/` | User documentation | When features added/changed |
| `planning/` | **Active** planning | During implementation |
| `security/` | Current security state | After security reviews |
| `systems/` | System documentation | When systems change |
| `history/*` | **Archive** only | Never (read-only) |

### Documentation Standards

1. **Every document must have:**
   - Clear title and purpose
   - Table of contents (if >200 lines)
   - Last updated date
   - Cross-references to related docs

2. **Planning documents should include:**
   - Implementation status
   - Dependencies
   - Success criteria
   - Next steps

3. **Architecture documents should include:**
   - System diagrams
   - Code examples
   - Performance characteristics
   - Integration points

4. **Guide documents should include:**
   - Use cases
   - Step-by-step instructions
   - Troubleshooting section
   - Related commands/features

---

## 📊 Documentation Statistics

**Total Documentation Files:** 61

### By Category
- **AI System:** 4 files
- **Architecture:** 3 files
- **Development:** 2 files
- **Guides:** 2 files
- **Planning (Active):** 15 files
- **Security:** 1 file
- **Systems:** 6 files
- **History (Archive):** 34 files
  - Investigations: 2
  - Phases: 11
  - Planning: 10
  - Precommit: 5
  - Security: 6

### Quick Stats
- 📝 **Active Documents:** 27
- 📚 **Archived Documents:** 34
- 🤖 **AI-Related:** 4
- 🏗️ **Architecture:** 9
- 🔧 **Development:** 17
- 📖 **User Guides:** 2
- 🔒 **Security:** 7

---

## 🎯 Quick Navigation by Role

### I'm a New User
→ Start with [`ai/AI-REFERENCE.md`](ai/AI-REFERENCE.md) then [`guides/AUTO_FIX_GUIDE.md`](guides/AUTO_FIX_GUIDE.md)

### I'm a Developer/Contributor
→ Read [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md) then [`development/IDE-SETUP.md`](development/IDE-SETUP.md)

### I'm Setting Up CI/CD
→ Check [`guides/ADVANCED-FEATURES.md`](guides/ADVANCED-FEATURES.md) and [`systems/MCP_INTEGRATION.md`](systems/MCP_INTEGRATION.md)

### I'm Debugging an Issue
→ Use [`ai/ERROR-PATTERNS.yaml`](ai/ERROR-PATTERNS.yaml) and search `history/investigations/`

### I'm Planning a Feature
→ Review [`planning/`](planning/) and [`architecture/API_REFERENCE.md`](architecture/API_REFERENCE.md)

### I'm Doing a Security Review
→ See [`security/SECURITY_AUDIT.md`](security/SECURITY_AUDIT.md) and `history/security/`

---

## 📞 Getting Help

If you can't find what you need:

1. **Check the command reference:** [`ai/AI-REFERENCE.md`](ai/AI-REFERENCE.md)
2. **Search the docs:** `grep -r "your search term" docs/`
3. **Review related history:** Check `history/` for context
4. **Check the main README:** `/Users/les/Projects/crackerjack/README.md`
5. **Ask in discussions:** Open a GitHub discussion

---

**Last Updated:** 2025-10-04

**Maintained by:** Crackerjack Documentation Team
