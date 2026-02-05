# AI-Fix Progress Bar Design

**Date**: 2026-02-03
**Library**: alive-progress
**Goal**: Futuristic, informative progress tracking during AI-fix iterations

---

## Progress Bar Layout

### Top Bar: Overall Progress
```
╔══════════════════════════════════════════════════════════════════╗
║  🤖 AI-FIX STAGE: FAST                                           ║
║  ████████████░░░░░░░░░░░░░  Iteration 3/∞  (45% convergence)     ║
║  Issues: 127 → 84 → 52 → 31  (76% reduction)                     ║
╚══════════════════════════════════════════════════════════════════╝
```

### Middle Bars: Active Agents (Parallel)
```
🔧 RefactoringAgent  ████████████████████░░  12 issues
🔒 SecurityAgent     ██████████████░░░░░░░   8 issues
📝 DocumentationAgent ████████░░░░░░░░░░░   5 issues
⚡ PerformanceAgent   █████████████████████  3 issues
```

### Bottom Bar: Current Operation
```
⚙️  Processing: complexity issues → RefactoringAgent
    File: crackerjack/services/parallel_executor.py:247
    ETA: 00:23  |  Confidence: 0.87
```

---

## Implementation Plan

### Phase 1: Add alive-progress Dependency

**File**: `pyproject.toml`

```toml
dependencies = [
    ...
    "alive-progress>=3.1.5",
]
```

### Phase 2: Create Progress Manager

**File**: `crackerjack/services/ai_fix_progress.py`

```python
"""
Futuristic progress tracking for AI-fix iterations using alive-progress.

Provides multi-level progress visualization:
1. Stage-level progress (iteration, issue reduction)
2. Agent-level progress (parallel agent execution)
3. Operation-level progress (current file, operation)
"""

from alive_progress import alive_bar, config_handler
from rich.console import Console
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crackerjack.agents.base import Issue, IssueType

# Custom theme for futuristic appearance
config_handler.set_global(
    theme="smooth",  # Smooth animations
    bar="smooth",  # █░ blocks
    spinner="waves",  # Wave animation
    stats="false",  # Hide time stats (we show custom)
    force_tty=True,  # Force colors
)

# Agent icons for visual distinction
AGENT_ICONS = {
    "RefactoringAgent": "🔧",
    "SecurityAgent": "🔒",
    "PerformanceAgent": "⚡",
    "FormattingAgent": "✨",
    "TestCreationAgent": "🧪",
    "TestSpecialistAgent": "🔬",
    "DocumentationAgent": "📝",
    "DRYAgent": "🔄",
    "ImportOptimizationAgent": "📦",
    "SemanticAgent": "🧠",
    "ArchitectAgent": "🏗️",
    "EnhancedProactiveAgent": "🔮",
}

# Issue type colors for terminal highlighting
ISSUE_TYPE_COLORS = {
    "formatting": "cyan",
    "security": "red",
    "complexity": "yellow",
    "performance": "blue",
    "test_failure": "magenta",
}


class AIFixProgressManager:
    """Manages multi-level progress bars for AI-fix iterations."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.iteration_bar = None
        self.agent_bars: dict[str, any] = {}
        self.current_agent = None
        self.issue_history: list[int] = []

    def start_iteration(
        self,
        iteration: int,
        total_issues: int,
        stage: str = "fast",
    ) -> None:
        """Start a new iteration progress bar."""
        self.issue_history.append(total_issues)
        reduction_pct = self._calculate_reduction()

        # Main iteration bar
        text = f"🤖 AI-FIX STAGE: {stage.upper()}"
        self.iteration_bar = alive_bar(
            total=100,  # Percentage based
            title=text,
            title_length=40,
            enrich_print=False,  # We handle custom printing
        )
        self.iteration_bar.start()

        # Print issue history
        self._print_issue_history(iteration, reduction_pct)

    def update_agent_progress(
        self,
        agent_name: str,
        completed: int,
        total: int,
        current_issue: "Issue | None" = None,
    ) -> None:
        """Update progress for a specific agent."""

        if agent_name not in self.agent_bars:
            # Create new agent bar
            icon = AGENT_ICONS.get(agent_name, "🤖")
            bar = alive_bar(
                total=total,
                title=f"{icon} {agent_name}",
                enrich_print=False,
                manual=True,
            )
            self.agent_bars[agent_name] = {"bar": bar, "total": total}
            bar.start()

        agent_data = self.agent_bars[agent_name]

        # Update total if changed
        if total != agent_data["total"]:
            agent_data["total"] = total
            # Would need to recreate bar with new total

        # Update progress
        agent_data["bar"](completed)

        # Print current operation details
        if current_issue:
            self._print_current_operation(agent_name, current_issue)

    def update_iteration_progress(
        self,
        iteration: int,
        issues_remaining: int,
        no_progress_count: int = 0,
    ) -> None:
        """Update the main iteration progress bar."""

        # Calculate convergence percentage
        # (arbitrary heuristic based on no_progress_count)
        convergence_pct = min(100, (no_progress_count / 3) * 100)

        if self.iteration_bar:
            self.iteration_bar(convergence_pct)

        # Print stats
        self._print_iteration_stats(iteration, issues_remaining, no_progress_count)

    def end_iteration(self) -> None:
        """Complete current iteration bars."""
        if self.iteration_bar:
            self.iteration_bar()

        for agent_data in self.agent_bars.values():
            agent_data["bar"]()

        self.agent_bars.clear()

    def _calculate_reduction(self) -> float:
        """Calculate issue reduction percentage."""
        if len(self.issue_history) < 2:
            return 0.0
        start = self.issue_history[0]
        current = self.issue_history[-1]
        return ((start - current) / start) * 100 if start > 0 else 0.0

    def _print_issue_history(self, iteration: int, reduction: float) -> None:
        """Print formatted issue history."""
        history_str = " → ".join(str(count) for count in self.issue_history)
        self.console.print(
            f"  Issues: {history_str}  ({reduction:.0f}% reduction)"
        )

    def _print_current_operation(self, agent: str, issue: "Issue") -> None:
        """Print current operation details."""
        file_loc = f"{issue.file_path}:{issue.line_number}" if issue.file_path else "unknown"

        # Use color coding by issue type
        color = ISSUE_TYPE_COLORS.get(issue.type.value, "white")

        self.console.print(
            f"⚙️  Processing: {issue.type.value} → {agent}\n"
            f"    File: {file_loc}\n"
            f"    Confidence: {issue.severity.value}"
        )

    def _print_iteration_stats(
        self,
        iteration: int,
        remaining: int,
        no_progress: int,
    ) -> None:
        """Print iteration statistics."""
        convergence_status = "✓ converging" if no_progress == 0 else f"⚠ {no_progress}/3 no progress"
        self.console.print(
            f"  Iteration {iteration} | {remaining} issues | {convergence_status}"
        )

    def finish(self, success: bool = True) -> None:
        """Complete all progress bars."""
        if self.iteration_bar:
            self.iteration_bar()

        for agent_data in self.agent_bars.values():
            agent_data["bar"]()

        status = "✓ All issues resolved!" if success else "⚠ Convergence limit reached"
        self.console.print(f"[{'green' if success else 'yellow'}]{status}[/]")
```

### Phase 3: Integrate with AutofixCoordinator

**File**: `crackerjack/core/autofix_coordinator.py`

```python
# Add to __init__
from crackerjack.services.ai_fix_progress import AIFixProgressManager

class AutofixCoordinator:
    def __init__(
        self,
        ...,
        enable_fancy_progress: bool = True,  # NEW parameter
    ):
        ...
        self.enable_fancy_progress = enable_fancy_progress
        self.progress_manager = AIFixProgressManager(console) if enable_fancy_progress else None

    def _apply_ai_agent_fixes(self, hook_results, stage="fast"):
        """Enhanced with progress tracking."""

        if self.progress_manager:
            self.progress_manager.start_iteration(0, len(hook_results), stage)

        iteration = 0
        while True:
            issues = self._get_iteration_issues(iteration, hook_results, stage)
            current_issue_count = len(issues)

            # Update progress
            if self.progress_manager:
                self.progress_manager.update_iteration_progress(
                    iteration,
                    current_issue_count,
                    no_progress_count,
                )

            # ... existing logic ...

            iteration += 1

        if self.progress_manager:
            self.progress_manager.finish(success=True)
```

### Phase 4: Agent-Level Progress

**File**: `crackerjack/agents/coordinator.py`

```python
# Add progress callbacks to AgentCoordinator
async def handle_issues(self, issues: list[Issue]) -> FixResult:
    """Enhanced with progress tracking."""

    issues_by_type = self._group_issues_by_type(issues)

    # Track progress for each issue type
    for issue_type, type_issues in issues_by_type.items():
        agent_name = self._select_agent_for_type(issue_type)

        if self.progress_manager:  # NEW
            self.progress_manager.update_agent_progress(
                agent_name=agent_name,
                completed=0,
                total=len(type_issues),
                current_issue=type_issues[0] if type_issues else None,
            )

        # Process issues
        for i, issue in enumerate(type_issues):
            result = await self._route_issue_to_agent(issue, agent_name)

            if self.progress_manager:  # NEW
                self.progress_manager.update_agent_progress(
                    agent_name=agent_name,
                    completed=i + 1,
                    total=len(type_issues),
                    current_issue=type_issues[i + 1] if i + 1 < len(type_issues) else None,
                )
```

---

## Usage Examples

### Enable Fancy Progress (Default)
```bash
# Automatic with --ai-fix
python -m crackerjack run --ai-fix --run-tests

# Expected output:
# ╔══════════════════════════════════════════════════════════════════╗
# ║  🤖 AI-FIX STAGE: COMPREHENSIVE                                  ║
# ║  ████████████░░░░░░░░░░░░░  Iteration 5/∞  (67% convergence)     ║
# ║  Issues: 127 → 84 → 52 → 31 → 18 → 12  (91% reduction)          ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# 🔧 RefactoringAgent  ████████████████████░░  12 issues
# 🔒 SecurityAgent     ██████████████░░░░░░░   8 issues
# ⚡ PerformanceAgent   █████████████████████  3 issues
#
# ⚙️  Processing: complexity issues → RefactoringAgent
#     File: crackerjack/services/parallel_executor.py:247
#     ETA: 00:23  |  Confidence: 0.87
```

### Disable Fancy Progress
```bash
# Fallback to simple text output
python -m crackerjack run --ai-fix --no-fancy-progress

# Expected output:
# Iteration 5: Extracted 12 issues from hook results
#   Issue 1: complexity in crackerjack/services/parallel_executor.py:247 - Function '_execute_hook' has complexity 18
#   ...
```

---

## Advanced Features

### 1. ETA Calculation
Track average time per issue to estimate completion:

```python
def _calculate_eta(self, remaining_issues: int, avg_time_per_issue: float) -> str:
    """Calculate estimated time to completion."""
    total_seconds = remaining_issues * avg_time_per_issue
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    return f"ETA: {minutes:02d}:{seconds:02d}"
```

### 2. Confidence Histogram
Show distribution of fix confidence scores:

```
Confidence Distribution:
0.9-1.0 ████████████████████  42 fixes
0.8-0.9 ████████░░░░░░░░░░░░░  28 fixes
0.7-0.8 ████░░░░░░░░░░░░░░░░░  15 fixes
<0.7    ██░░░░░░░░░░░░░░░░░░░░   7 fixes
```

### 3. Issue Type Breakdown
Show which issue types are being fixed:

```
Issue Type Distribution:
complexity        ████████████░░  12 issues
security          ██████░░░░░░░░░   8 issues
performance       ████░░░░░░░░░░░   6 issues
formatting        ██░░░░░░░░░░░░░░   3 issues
```

---

## Configuration

### settings/crackerjack.yaml
```yaml
ai_fix:
  fancy_progress: true          # Enable/disable fancy progress
  show_agent_bars: true         # Show per-agent progress
  show_eta: true                # Show estimated completion time
  show_confidence: true         # Show confidence scores
  max_agent_bars: 5             # Maximum parallel agent bars to show
```

### CLI Options
```bash
--ai-fancy-progress        # Enable fancy progress (default)
--no-ai-fancy-progress     # Disable fancy progress
--ai-show-agent-bars       # Show per-agent progress
--ai-show-eta              # Show ETA
```

---

## Benefits

### 1. Visual Feedback
- Users see exactly what's happening
- Multiple levels of granularity
- Futuristic, engaging display

### 2. Debugging Insight
- Which agents are working
- What issue types are prevalent
- Convergence progress

### 3. Performance Awareness
- ETA for completion
- Issue reduction rate
- Confidence levels

---

## Implementation Priority

### Phase 1: Core Progress (High Value)
- [x] Add alive-progress dependency
- [ ] Create AIFixProgressManager
- [ ] Integrate with AutofixCoordinator
- [ ] Basic iteration bar

### Phase 2: Agent-Level Tracking (Medium Value)
- [ ] Track agent execution
- [ ] Per-agent progress bars
- [ ] Current operation display

### Phase 3: Advanced Features (Nice-to-Have)
- [ ] ETA calculation
- [ ] Confidence histogram
- [ ] Issue type breakdown
- [ ] Configuration options

---

## Technical Notes

### Why alive-progress?

1. **Multi-bar support**: Can show multiple parallel progress bars
2. **Custom animations**: Smooth spinners, progress bars
3. **TTY handling**: Works in terminals, CI/CD
4. **Performance**: Minimal overhead
5. **Customizable**: Themes, colors, formats

### Integration Challenges

1. **Async/Await**: alive-progress is synchronous, need thread-safe updates
2. **Parallel execution**: Multiple agents working simultaneously
3. **Unknown totals**: Convergence-based iterations don't have fixed max
4. **Performance**: Must not slow down AI-fix operations

### Solutions

1. Use `manual=True` mode for explicit progress updates
2. Thread-safe progress updates via locking
3. Percentage-based progress for unknown totals
4. Minimal overhead design (update every N issues)

---

## Conclusion

The AI-fix workflow has **excellent progression points** for a rich progress display:

- ✅ **Stage level**: Fast vs Comprehensive
- ✅ **Iteration level**: Convergence tracking
- ✅ **Agent level**: 12 parallel specialized agents
- ✅ **Operation level**: Current file, issue type, confidence

The result will be a **futuristic, informative** progress display that provides both **eye candy** and **debugging insight** into the AI-fix process.

**Expected user experience**: "I can see exactly what the AI agents are doing, which issues they're fixing, and how long it will take - all in a beautiful, sci-fi interface!"
