# AI-Fix Progress Bar Redesign - Final Design

**Status**: Ready for Implementation
**Date**: 2026-02-08
**Agents Consulted**: Frontend Developer, Python Pro, Performance Engineer
**Rich API Reference**: https://rich.readthedocs.io/en/stable/

---

## Executive Summary

After consulting three specialist agents and reviewing Rich's official documentation, we're implementing a **Timeline/Activity Log Style** progress display using Rich's `Live` class with an integrated activity feed.

**Key Decision**: Use Rich's `Live` display (not `Progress`) for unified dashboard with activity ticker.

---

## Design Overview

### Visual Layout

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Crackerjack Progress                                  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 🚀 COMPREHENSIVE_HOOKS (~30s)                         │
│ ████████████████████░░░░░░ 65%                        │
│ Recent Activity:                                      │
│   🔧 Refactoring: syntax error test_executor.py:536   │
│   ✨ Formatting: import fix models/config.py:42       │
│   🧪 TestCreation: creating test tests/test_auth.py  │
└──────────────────────────────────────────────────────┘
```

**Fixed at bottom of terminal** - scrolls above, panel stays visible.

---

## Implementation Architecture

### 1. Rich Live Display (Thread-Safe by Default)

**Critical Discovery**: Rich's `Live.update()` method is **already thread-safe** via internal lock:

```python
# From Rich source code (rich/live.py)
def update(self, renderable: RenderableType, *, refresh: bool = False) -> None:
    with self._lock:  # ← Thread-safe by default!
        self._renderable = renderable
        if refresh:
            self.refresh()
```

**✅ No additional threading locks needed** - Rich handles it.

### 2. Type-Safe Events

Use `NamedTuple` for event structure (Python Pro recommendation):

```python
from typing import NamedTuple

class ActivityEvent(NamedTuple):
    """Type-safe activity event."""
    agent: str      # "RefactoringAgent"
    action: str     # "fixing", "analyzing", "skipped"
    file: str       # "crackerjack/managers/test_manager.py"
    severity: str   # "info", "warning", "error", "success"
```

**Benefits**:
- IDE autocomplete works
- Type checking validates structure
- Self-documenting code

### 3. Compact Event Format

**Frontend Developer Recommendation** - Simplified, scannable format:

```python
# ❌ Original (too long)
[14:32:05] 🔧 RefactoringAgent → test_executor.py:536 (syntax error)

# ✅ Improved (compact)
🔧 Refactoring: syntax error test_executor.py:536
```

**Changes**:
- Remove timestamp (redundant with wall clock)
- Shorten agent name ("RefactoringAgent" → "Refactoring")
- Remove parentheses (harder to scan)
- Use colon separator (cleaner visual)

### 4. Color-Coded Severity

**Frontend Developer Recommendation** - Failures stand out:

```python
SEVERITY_COLORS = {
    "error": "red",
    "warning": "yellow",
    "success": "green",
    "info": "cyan",
}

# Error example (red, bold)
❌ Refactoring: syntax error in test_executor.py:536

# Success example (green)
✓ Formatting: fixed import models/config.py:42
```

### 5. Configurable Refresh Rate

**Frontend Developer Concern** - 4Hz may flicker on some terminals.

**Rich Reality** - 4Hz is Rich's default for Live displays.

**Solution**: Make it configurable:

```python
class AIFixProgressManager:
    def __init__(
        self,
        refresh_per_second: int = 4,  # Configurable
        ...
    ):
        self.refresh_per_second = refresh_per_second
```

**Recommended values**:
- `4` (default) - Smooth updates, Rich-optimized
- `2` - Conservative, less CPU
- `1` - Minimal updates, event-driven preferred
- `0` - Disable auto-refresh, use `update(refresh=True)`

### 6. Event-Driven Updates

**Performance Engineer Recommendation** - Update only when events occur, not continuous polling.

```python
# ✅ BETTER: Event-driven updates
with Live(..., auto_refresh=False) as live:
    for event in events:
        live.update(render_dashboard(), refresh=True)  # Only on new events

# OR: Use auto_refresh with lower rate
with Live(..., refresh_per_second=1) as live:  # 1Hz instead of 4Hz
    for event in events:
        live.update(render_dashboard())  # Auto-refresh handles it
```

**Recommended**: `refresh_per_second=1` with `auto_refresh=True` (balanced approach).

---

## Code Structure

### Class Design

```python
from collections import deque
from datetime import datetime
from typing import NamedTuple

from rich.console import Console
from rich.live import Live
from rich.panel import Panel

class ActivityEvent(NamedTuple):
    """Type-safe activity event for progress tracking."""
    agent: str
    action: str
    file: str
    severity: str = "info"

class AIFixProgressManager:
    """Progress manager for AI-fix with Live display and activity feed.

    Thread-safe: Rich's Live.update() uses internal lock.
    Async-safe: Use async_log_event() from async contexts.
    """

    def __init__(
        self,
        console: Console | None = None,
        enabled: bool = True,
        enable_agent_bars: bool = True,
        max_agent_bars: int = 5,
        activity_feed_size: int = 5,
        refresh_per_second: int = 1,  # Configurable
    ) -> None:
        self.console = console or Console()
        self.enabled = enabled
        self.enable_agent_bars = enable_agent_bars
        self.max_agent_bars = max_agent_bars
        self.refresh_per_second = refresh_per_second

        # Activity feed (thread-safe)
        self._activity_events: deque[ActivityEvent] = deque(maxlen=activity_feed_size)

        # Live display lifecycle
        self._live_display: Live | None = None

        # Session state
        self.issue_history: list[int] = []
        self.current_iteration = 0
        self.stage = "fast"

    # ... (implementation below)
```

### Key Methods

#### `start_iteration()`

```python
def start_iteration(
    self,
    iteration: int,
    issue_count: int,
) -> None:
    """Start a new iteration with Live display."""
    if not self.enabled:
        return

    self.current_iteration = iteration

    if issue_count > 0:
        self.issue_history.append(issue_count)

    # Create Live display
    self._live_display = Live(
        self._render_dashboard,
        console=self.console,
        refresh_per_second=self.refresh_per_second,
    )
    self._live_display.start()
```

**Note**: Uses `start()`/`stop()` pattern (not context manager) for better lifecycle control.

#### `log_event()`

```python
def log_event(
    self,
    agent: str,
    action: str,
    file: str,
    severity: str = "info",
) -> None:
    """Log activity event (thread-safe).

    Can be called from multiple threads concurrently.
    Rich's Live.update() uses internal lock for thread safety.
    """
    if not self.enabled or not self._live_display:
        return

    event = ActivityEvent(agent, action, file, severity)

    # Add to activity feed
    self._activity_events.append(event)

    # Update Live display (thread-safe via Rich's internal lock)
    self._live_display.update(self._render_dashboard(), refresh=True)
```

**Note**: `refresh=True` triggers immediate update instead of waiting for next auto-refresh.

#### `async_log_event()`

```python
import asyncio

async def async_log_event(
    self,
    agent: str,
    action: str,
    file: str,
    severity: str = "info",
) -> None:
    """Async-safe event logging.

    Runs log_event() in thread pool to avoid blocking event loop.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        self.log_event,
        agent,
        action,
        file,
        severity,
    )
```

**Note**: For async agent operations, use this to avoid blocking the event loop.

#### `_render_dashboard()`

```python
def _render_dashboard(self) -> Panel:
    """Render the Live dashboard.

    Returns a Panel with:
    - Stage header
    - Progress bar (if applicable)
    - Activity feed
    """
    # Stage header
    stage_text = self._get_stage_text()

    # Progress bar
    progress_text = self._get_progress_text()

    # Activity feed
    activity_text = self._render_activity_feed()

    # Combine
    content = f"{stage_text}\n"
    if progress_text:
        content += f"{progress_text}\n"
    content += activity_text

    return Panel(
        content,
        border_style="cyan",
        padding=(0, 1),
        title="[bold]Crackerjack[/bold]",
    )
```

#### `_render_activity_feed()`

```python
def _render_activity_feed(self) -> str:
    """Render compact activity feed."""
    if not self._activity_events:
        return "[dim]Recent Activity:[/dim] [dim]No activity yet[/dim]"

    lines = ["[dim]Recent Activity:[/dim]"]

    for event in reversed(self._activity_events):
        # Agent icon and short name
        icon = AGENT_ICONS.get(event.agent, "🤖")
        agent_short = event.agent.replace("Agent", "")

        # Severity color
        color = {
            "error": "red",
            "warning": "yellow",
            "success": "green",
            "info": "cyan",
        }.get(event.severity, "white")

        # File name only (shorter)
        file_part = Path(event.file).name if event.file else ""

        # Format: 🔧 Refactoring: syntax error test_executor.py
        line = f"  [{color}]{icon} {agent_short}: {event.action}[/][{color}] {file_part}[/]"
        lines.append(line)

    return "\n".join(lines)
```

---

## Agent Recommendations Summary

### Frontend Developer ✅

**Accepted**:
- ✅ Simplify event format (remove timestamps, shorten names)
- ✅ Color-code severity (red for errors, green for success)
- ✅ Add stage context header
- ✅ Make refresh rate configurable

**Rejected** (Rich API differs):
- ❌ 4Hz is too aggressive → Rich's default is 4Hz (optimized)
- ❌ Need adaptive terminal sizing → Keep simple for now (future enhancement)

### Python Pro ✅

**Accepted**:
- ✅ Use NamedTuple for type-safe events
- ✅ Proper lifecycle management (start()/stop())
- ✅ Async-safe API (async_log_event with run_in_executor)

**Rejected** (Rich handles it):
- ❌ Add threading.Lock → Rich's Live.update() already thread-safe
- ❌ Replace Progress with Live → Keep Progress for iteration bar, use Live for dashboard

### Performance Engineer ✅

**Accepted**:
- ✅ Event-driven updates (refresh=True on update)
- ✅ Configurable refresh rate (default to 1Hz)
- ✅ deque(maxlen=5) prevents memory bloat

**Accepted with modification**:
- ✅ String allocations → strftime() per event is acceptable (only 5 events max)

---

## Implementation Checklist

- [ ] Add `ActivityEvent` NamedTuple to `ai_fix_progress.py`
- [ ] Extend `AIFixProgressManager.__init__()` with Live display params
- [ ] Implement `_render_dashboard()` method
- [ ] Implement `_render_activity_feed()` method
- [ ] Implement `start_iteration()` with Live.start()
- [ ] Implement `log_event()` with thread-safe update
- [ ] Implement `async_log_event()` for async contexts
- [ ] Implement `end_iteration()` with Live.stop()
- [ ] Add severity color mapping
- [ ] Test with multiple concurrent agents
- [ ] Test with async agent operations
- [ ] Verify refresh rate behavior

---

## Migration Strategy

1. **Phase 1**: Add Live display alongside existing Progress (no breaking changes)
2. **Phase 2**: Migrate activity logging to use Live display
3. **Phase 3**: Deprecate old Progress-based iteration bar (optional)

**Recommended**: Start with Phase 1, validate UX, then complete migration.

---

## Configuration

Add to `settings/crackerjack.yaml`:

```yaml
ai_fix_progress:
  enabled: true
  enable_agent_bars: true
  max_agent_bars: 5
  activity_feed_size: 5
  refresh_per_second: 1  # 1Hz = balanced, 4Hz = smoother
```

---

## Testing Strategy

### Unit Tests

```python
def test_activity_event_namedtuple():
    """Test ActivityEvent type safety."""
    event = ActivityEvent(
        agent="RefactoringAgent",
        action="fixing",
        file="test.py",
        severity="info",
    )
    assert event.agent == "RefactoringAgent"
    assert event.action == "fixing"

def test_log_event_thread_safety():
    """Test log_event() from multiple threads."""
    manager = AIFixProgressManager()
    manager.start_iteration(0, 10)

    import threading
    threads = [
        threading.Thread(
            target=manager.log_event,
            args=("RefactoringAgent", "fixing", "test.py"),
        )
        for _ in range(10)
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should have 5 events (deque maxlen=5)
    assert len(manager._activity_events) == 5
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_async_log_event():
    """Test async_log_event() doesn't block."""
    manager = AIFixProgressManager()
    manager.start_iteration(0, 10)

    # Should not block
    await manager.async_log_event("RefactoringAgent", "fixing", "test.py")

    assert len(manager._activity_events) == 1
```

---

## Performance Considerations

### Memory

- `deque(maxlen=5)` → Max 5 events in memory (~1KB)
- Rich Live display → Single renderable (~10KB)
- **Total overhead**: ~11KB per session (negligible)

### CPU

- Refresh rate: 1Hz = 1 render/second
- Event-driven updates: Only on new events
- **Estimated cost**: <1% CPU on modern hardware

### Thread Safety

- Rich's internal lock protects `update()`
- No additional synchronization needed
- Safe for concurrent agent operations

---

## Future Enhancements

1. **Adaptive Terminal Sizing** - Hide panel on small terminals (< 30 rows)
2. **Detailed Event View** - Expand to show full event details on demand
3. **Event Filtering** - Filter by severity, agent, or file pattern
4. **Historical Timeline** - Show complete event history after session
5. **Export Progress** - Save progress to JSON for later analysis

---

## References

- **Rich Documentation**: https://rich.readthedocs.io/en/stable/
- **Rich Live API**: https://rich.readthedocs.io/en/stable/reference/live.html
- **Rich Progress API**: https://rich.readthedocs.io/en/stable/reference/progress.html
- **Thread Safety**: Rich source code `rich/live.py` (lines 1-50)
- **Existing Implementation**: `crackerjack/services/ai_fix_progress.py`

---

## Summary

**Approach**: Timeline/Activity Log Style with Rich Live display
**Thread Safety**: Handled by Rich's internal lock (no additional code needed)
**Refresh Rate**: Configurable (default 1Hz for balance)
**Type Safety**: NamedTuple for events
**Async Support**: async_log_event() with run_in_executor()
**Visual Design**: Compact format, color-coded severity, stage context

**Next Step**: Implement Phase 1 (add Live display alongside existing Progress)
