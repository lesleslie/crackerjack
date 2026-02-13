---
name: session-start
description: Initialize Claude session with comprehensive project setup, dependency management, and workflow optimization for optimal development experience
---

# Session Start Workflow

Initialize a Claude session with intelligent project setup and workflow optimization.

## 🎯 What This Does

This skill orchestrates session initialization with:

1. **Project Detection**: Automatically detects git repository and project type
2. **Environment Setup**: Configures UV, dependencies, and tooling
3. **Session Context**: Loads previous session data for continuity
4. **Workflow Optimization**: Sets up automation and quality tools
5. **Integration**: Connects to crackerjack, MCP servers, and monitoring

## 📋 Before You Start

**Check your environment:**

```bash
# Verify you're in a git repository
git rev-parse --git-dir

# Check if session-buddy is available
python -m session_buddy --help

# Verify MCP servers
python -m crackerjack status
```

**Questions to consider:**

- Is this a new session or continuation?
- What type of work will you do? (feature, bugfix, refactoring, docs)
- Do you need UV dependency setup?
- Should quality checks be configured?

## 🚀 Interactive Session Setup

### Step 1: Session Type Selection

**What type of session is this?**

1. **New Project Session** (First time working on this project)
   - Full environment setup
   - Dependency installation via UV
   - Crackerjack initialization (if needed)
   - Session database creation

2. **Continuation Session** (Returning to previous work)
   - Loads previous session context
   - Restores workflow state
   - Shows quality trends
   - Displays recommendations

3. **Quick Start** (Jump right in)
   - Basic session initialization
   - Minimal setup overhead
   - Fastest path to coding

4. **Custom Session** (Specific configuration)
   - Choose specific features
   - Configure automation
   - Set up monitoring

### Step 2: Environment Configuration

**What setup do you need?**

**Dependency Management:**
- [ ] **UV Setup** - Fast Python package installer
  - Checks if UV is installed
  - Sets up UV project if needed
  - Syncs dependencies
  - Ideal for: New projects, dependency updates

- [ ] **Virtual Environment** - Ensure active venv
  - Checks for `.venv`
  - Activates if needed
  - Verifies Python version

**Quality Tools:**
- [ ] **Crackerjack Integration** - Quality checks and AI fixing
  - Initializes if not configured
  - Runs initial quality baseline
  - Sets up MCP server connection
  - Recommended for: All Python projects

- [ ] **Pre-commit Hooks** - Quality gates on commit
  - Configures git hooks
  - Sets up automated checks
  - Optional (crackerjack has native hooks)

**Session Features:**
- [ ] **Session Database** - Track session metrics and learnings
  - Creates SQLite database for project
  - Enables session continuity
  - Stores quality trends
  - Recommended for: Active development

- [ ] **Memory Integration** - Connect to Akosha/vector storage
  - Enables semantic search of past work
  - Cross-session learning
  - Advanced feature

### Step 3: Workflow Automation

**What automation should be enabled?**

- [ ] **Auto-initialization** - Start session automatically on git repo connection
  - Convenient for frequent work
  - Minimal friction
  - Recommended for: Active projects

- [ ] **Auto-cleanup** - Clean up on disconnect
  - Removes temp files
  - Consolidates logs
  - Updates session metrics

- [ ] **Progress Monitoring** - Track work during session
  - Quality checkpoints
  - Workflow metrics
  - Bottleneck detection

- [ ] **Quality Tracking** - Monitor code quality over time
  - Coverage trends
  - Test pass rates
  - Complexity metrics

## 💡 Common Workflows

### Workflow 1: New Project Setup

**Best for**: First time working on a Python project

```bash
# Session auto-detects git repository
# Prompt asks for setup preferences

Session Start: New Project detected
Project: my-project (Git repository)

Environment Setup:
[ ] UV dependency management
[ ] Crackerjack quality tools
[ ] Session database
[ ] MCP server integration

Select features to enable (all recommended): 1-4
> 1,2,3,4

✓ UV configured
✓ Crackerjack initialized
✓ Session database created
✓ MCP servers connected

📊 Baseline quality metrics:
  - Coverage: 0% (new project)
  - Tests: 0 tests
  - Complexity: Not measured

💡 Next steps:
  1. Review CLAUDE.md for project guidelines
  2. Run /crackerjack:run after first code changes
  3. Use /session:checkpoint for mid-session quality checks
```

**Timeline:** 1-2 minutes for full setup

### Workflow 2: Continuation Session

**Best for**: Returning to ongoing work

```bash
# Session loads previous context

Session Start: Welcome back!
Project: my-project

📋 Previous Session Summary:
  - Last session: 2 hours ago
  - Final quality score: 85/100
  - Work completed: Feature X implementation
  - Top recommendation: Add tests for new module

✨ Session continuity restored
  - Loaded 3 reflections from last session
  - Restored workflow preferences
  - Quality trends available

📊 Current Status:
  - Coverage: 47% (+5% from last session)
  - Tests: 42 passing
  - Active branch: feature/new-auth

💡 Suggested next steps:
  1. Continue feature implementation
  2. Run /crackerjack:run to check quality
  3. Review test coverage gaps
```

**Benefits:**
- Seamless context restoration
- Builds on previous learnings
- Informed recommendations

### Workflow 3: Quick Start

**Best for**: Fast session initiation, minimal overhead

```bash
# Minimal setup, immediate coding

Session Start: Quick mode
Project: my-project

✓ Session initialized
✓ Git repository detected
✓ Ready to code

No automatic setup performed.
Use /crackerjack:init or /session:checkpoint for setup.

To enable features, restart session with:
  python -m session_buddy start --interactive
```

**Timeline:** <10 seconds

### Workflow 4: Custom Configuration

**Best for**: Specific workflow needs

```bash
# Interactive setup with custom choices

Session Start: Custom configuration

Project Analysis:
  - Type: MCP server project
  - Dependencies: 12 direct, 45 total
  - Python: 3.13
  - UV: Not configured
  - Crackerjack: Configured

Setup Options:

1. UV Setup
   Recommended: YES (MCP servers benefit from fast installs)
   Enable? [Y/n]: Y

2. Crackerjack
   Status: Already configured (minimal template)
   Update to library template? [y/N]: N

3. Session Database
   Recommended: YES (enables session continuity)
   Enable? [Y/n]: Y

4. Quality Automation
   Options:
     a) Auto-run quality on checkpoint
     b) Manual quality only
     c) Custom schedule
   Select [a/b/c]: a

✓ Custom configuration applied
```

## 🔍 Session Features

### Automatic Initialization

**How it works:**

When you connect to a git repository via MCP, session-buddy automatically:

1. **Detects git repository** - Checks for `.git` directory
2. **Initializes session** - Creates session record
3. **Loads previous context** - Restores last session data
4. **Provides recommendations** - Suggests next actions

**No manual intervention needed.**

### Previous Session Restoration

**What gets restored:**

- **Quality Metrics**: Coverage, test counts, complexity trends
- **Work Patterns**: Common workflows, preferred tools
- **Recommendations**: Previous session's suggestions
- **Reflections**: Learnings and insights from past work

**Example output:**
```
📋 Previous Session Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━
Ended: 2 hours ago
Duration: 3 hours 15 minutes
Quality Score: 85/100

Work Completed:
✓ Feature: User authentication
✓ Tests: 15 new tests
✓ Coverage: +5% improvement

Recommendations:
💡 Add integration tests for auth flow
💡 Refactor: login() complexity 18 > 15
💡 Docs: Update API documentation

Quality Trends:
  Coverage: 42% → 47% (↑5%)
  Tests: 27 → 42 (↑15)
  Complexity: Stable
```

### Integration Points

**Crackerjack Integration:**

Session-buddy integrates seamlessly with crackerjack:

```python
# Automatic crackerjack initialization
if not crackerjack_configured():
    suggest("/crackerjack:init")

# Quality checkpoints use crackerjack
await checkpoint()  # Runs crackerjack quality checks

# Session end includes quality summary
await end()  # Shows crackerjack metrics
```

**MCP Server Integration:**

```python
# Session-buddy can manage MCP servers
- Auto-start crackerjack MCP server (localhost:8676)
- Monitor server health
- Restart if needed
```

## 🎨 Configuration Options

### Session Modes

**Standard Mode** (Recommended):
- Full feature set
- Session database
- Quality tracking
- Workflow optimization

**Lite Mode**:
- Minimal overhead
- Essential features only
- Faster startup
- Good for: Quick tasks, documentation

**Custom Mode**:
- Choose specific features
- Configure behavior
- Optimize for workflow

### Environment Variables

```bash
# Session behavior configuration
export SESSION_BUDDY_MODE=standard  # standard, lite, custom
export SESSION_AUTO_INIT=true       # Auto-initialize on git repo
export SESSION_AUTO_CLEANUP=true    # Auto-cleanup on disconnect
export CRACKERJACK_AUTO_INIT=true   # Suggest crackerjack for Python
```

### Project Configuration

Create `.session-buddy.yaml` in project root:

```yaml
# Session configuration
session:
  mode: standard
  auto_init: true
  auto_cleanup: true

quality:
  tool: crackerjack
  auto_run: true
  checkpoint_interval: 30m

monitoring:
  track_coverage: true
  track_tests: true
  track_complexity: true
```

## ⚠️ Troubleshooting

### Issue: "Session initialization failed"

**Cause**: Git repository not detected or permissions issue

**Solution**:
```bash
# Verify git repository
git status

# Check session-buddy installation
python -m session_buddy --help

# Manually initialize session
python -m session_buddy start --working-dir /path/to/project
```

### Issue: "Previous session not restored"

**Cause**: Session database missing or corrupted

**Solution**:
```bash
# Check session database
ls -la .session-buddy/

# Reinitialize database
python -m session_buddy start --fresh

# Or start without previous context
python -m session_buddy start --no-history
```

### Issue: "Crackerjack integration not working"

**Cause**: Crackerjack not installed or not configured

**Solution**:
```bash
# Install crackerjack
uv add --dev crackerjack

# Initialize crackerjack
python -m crackerjack init

# Restart session
python -m session_buddy start
```

## 🎯 Best Practices

### DO ✅

- **Let session auto-initialize** - Works automatically with git repos
- **Enable session database** - Provides continuity and insights
- **Use checkpoints** - Mid-session quality verification
- **Review recommendations** - Previous session insights are valuable
- **Integrate with crackerjack** - Quality tracking and automation

### DON'T ❌

- **Don't skip initialization** - You'll miss valuable features
- **Don't ignore previous context** - Session continuity is powerful
- **Don't disable auto-cleanup** - Keeps system clean
- **Don't work without session tracking** - Lose learning opportunities

## 📚 Related Skills

- `crackerjack-init` - Set up crackerjack for your project
- `crackerjack-run` - Run quality checks with AI fixing
- `session-checkpoint` - Mid-session quality verification
- `session-end` - End session with cleanup and summary

## 🔗 Further Reading

- **Session Architecture**: `session_buddy/core/session_manager.py`
- **Quality Integration**: `session_buddy/quality_engine.py`
- **Workflow Optimization**: `docs/workflow-optimization.md`
