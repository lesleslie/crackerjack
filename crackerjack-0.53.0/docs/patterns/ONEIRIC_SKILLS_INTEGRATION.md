# Oneiric Skills Metrics Integration

## Executive Summary

This document outlines the recommended integration architecture for tracking skill invocations within the Oneiric workflow system. Skills are **guided interactive workflows** that differ from Oneiric's **automated task execution**, requiring a hybrid approach that respects both systems' design philosophies.

**Key Decision**: Skills should be tracked as **correlated workflow events**, not as Oneiric workflow nodes. This maintains separation of concerns while enabling powerful cross-system analytics.

______________________________________________________________________

## Architecture Overview

### Core Principle: Separation of Concerns

```
┌─────────────────────────────────────────────────────────────────┐
│                    Crackerjack System                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────┐         ┌──────────────────────┐     │
│  │   Oneiric Workflows  │         │   Skills System       │     │
│  │   (Automated)        │         │   (Interactive)       │     │
│  │                      │         │                      │     │
│  │  - Fast hooks        │         │  - Markdown guides   │     │
│  │  - Test phases       │         │  - User interaction  │     │
│  │  - Comprehensive     │         │  - Decision points   │     │
│  │  - Publishing        │         │  - Follow-up actions │     │
│  └──────────┬───────────┘         └──────────┬───────────┘     │
│             │                                │                  │
│             │                                │                  │
│             └────────────┬───────────────────┘                  │
│                          │                                       │
│                   ┌──────▼──────┐                                │
│                   │  Correlation │                                │
│                   │   Service    │                                │
│                   │              │                                │
│                   │  - Link by   │                                │
│                   │    session   │                                │
│                   │  - Joint     │                                │
│                   │    metrics   │                                │
│                   └──────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Architecture?

**Oneiric Workflows**:

- ✅ Automated task execution with DAG dependencies
- ✅ Fast, comprehensive hooks, test phases
- ✅ Machine-triggered, deterministic execution
- ❌ Not designed for interactive user guidance

**Skills System**:

- ✅ Interactive markdown-based guidance
- ✅ User decision points and branching paths
- ✅ Context-aware follow-up suggestions
- ❌ Not automated (requires human agency)

**Correlation Layer**:

- ✅ Links both systems by session_id
- ✅ Enables cross-system analytics
- ✅ Maintains system autonomy
- ✅ Privacy-first local storage

______________________________________________________________________

## Implementation Plan

### Phase 1: Enhanced Skill Metrics (Current System - ✅ Complete)

**Status**: Already implemented in `crackerjack/skills/metrics.py`

**Capabilities**:

- Track skill invocations with timestamps
- Record workflow paths (quick, comprehensive, custom)
- Measure completion rates and durations
- Track follow-up actions and error patterns
- JSON-based local storage in `.session-buddy/`

**Data Model**:

```python
@dataclass
class SkillInvocation:
    skill_name: str
    invoked_at: str  # ISO format timestamp
    workflow_path: str | None  # e.g., "quick", "comprehensive"
    completed: bool = False
    duration_seconds: float | None = None
    follow_up_actions: list[str] = field(default_factory=list)
    error_type: str | None = None
```

**Usage**:

```python
from crackerjack.skills.metrics import track_skill

complete = track_skill("crackerjack-run", "daily")
# ... skill execution ...
complete(completed=True, follow_up_actions=["git commit"])
```

______________________________________________________________________

### Phase 2: Oneiric Workflow Event Tracking (⭐ Recommended Addition)

**Goal**: Emit Oneiric workflow events that skills can correlate with.

**Implementation**: Add workflow execution hooks to Oneiric integration.

#### 2.1 Add Workflow Event Emitter

Create `/Users/les/Projects/crackerjack/crackerjack/runtime/workflow_events.py`:

```python
"""Workflow event emission for correlation with skills metrics."""

from __future__ import annotations

import logging
import time
import typing as t
from dataclasses import dataclass, field
from datetime import datetime

if t.TYPE_CHECKING:
    from crackerjack.runtime.oneiric_workflow import OneiricWorkflowRuntime

logger = logging.getLogger(__name__)


@dataclass
class WorkflowEvent:
    """Event emitted during Oneiric workflow execution."""

    event_type: str  # "workflow_started", "node_started", "node_completed", "workflow_completed"
    workflow_id: str  # e.g., "crackerjack"
    node_id: str | None = None  # e.g., "fast_hooks", "tests"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: str | None = None  # Correlation with skills
    metadata: dict[str, t.Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_type": self.event_type,
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }


class WorkflowEventTracker:
    """Track Oneiric workflow execution events for correlation."""

    def __init__(self, session_id: str | None = None) -> None:
        """Initialize workflow event tracker.

        Args:
            session_id: Optional session ID for correlation with skills
        """
        self.session_id = session_id
        self.events: list[WorkflowEvent] = []
        self._workflow_start_time: float | None = None
        self._node_start_times: dict[str, float] = {}

    def workflow_started(self, workflow_id: str, metadata: dict[str, t.Any] | None = None) -> None:
        """Record workflow execution start."""
        self._workflow_start_time = time.time()
        event = WorkflowEvent(
            event_type="workflow_started",
            workflow_id=workflow_id,
            session_id=self.session_id,
            metadata=metadata or {},
        )
        self.events.append(event)
        logger.debug(f"Workflow started: {workflow_id}")

    def node_started(self, node_id: str, metadata: dict[str, t.Any] | None = None) -> None:
        """Record workflow node execution start."""
        self._node_start_times[node_id] = time.time()
        event = WorkflowEvent(
            event_type="node_started",
            workflow_id="crackerjack",  # Crackerjack has one main workflow
            node_id=node_id,
            session_id=self.session_id,
            metadata=metadata or {},
        )
        self.events.append(event)
        logger.debug(f"Node started: {node_id}")

    def node_completed(
        self,
        node_id: str,
        success: bool = True,
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Record workflow node execution completion."""
        start_time = self._node_start_times.pop(node_id, None)
        duration = None
        if start_time:
            duration = time.time() - start_time

        event_metadata = metadata or {}
        if duration:
            event_metadata["duration_seconds"] = duration
        event_metadata["success"] = success

        event = WorkflowEvent(
            event_type="node_completed",
            workflow_id="crackerjack",
            node_id=node_id,
            session_id=self.session_id,
            metadata=event_metadata,
        )
        self.events.append(event)
        logger.debug(f"Node completed: {node_id} (duration: {duration:.2f}s)")

    def workflow_completed(self, success: bool = True, metadata: dict[str, t.Any] | None = None) -> None:
        """Record workflow execution completion."""
        duration = None
        if self._workflow_start_time:
            duration = time.time() - self._workflow_start_time

        event_metadata = metadata or {}
        if duration:
            event_metadata["duration_seconds"] = duration
        event_metadata["success"] = success

        event = WorkflowEvent(
            event_type="workflow_completed",
            workflow_id="crackerjack",
            session_id=self.session_id,
            metadata=event_metadata,
        )
        self.events.append(event)
        logger.debug(f"Workflow completed (duration: {duration:.2f}s)")

    def get_events(self) -> list[dict[str, t.Any]]:
        """Get all events as dictionaries."""
        return [event.to_dict() for event in self.events]

    def get_node_duration(self, node_id: str) -> float | None:
        """Get duration for a specific node."""
        for event in reversed(self.events):
            if event.event_type == "node_completed" and event.node_id == node_id:
                return event.metadata.get("duration_seconds")
        return None
```

#### 2.2 Integrate Event Tracker into Oneiric Workflow

Modify `/Users/les/Projects/crackerjack/crackerjack/runtime/oneiric_workflow.py`:

```python
# Add to imports
from crackerjack.runtime.workflow_events import WorkflowEventTracker

# Add to OneiricWorkflowRuntime class
@dataclass(frozen=True)
class OneiricWorkflowRuntime:
    resolver: Resolver
    lifecycle: LifecycleManager
    orchestrator: RuntimeOrchestrator
    event_tracker: WorkflowEventTracker | None = None  # Add this

    # ... existing properties ...

# Update build_oneiric_runtime function
def build_oneiric_runtime(session_id: str | None = None) -> OneiricWorkflowRuntime:
    # ... existing setup code ...

    event_tracker = WorkflowEventTracker(session_id=session_id)

    orchestrator = RuntimeOrchestrator(
        oneiric_settings,
        resolver,
        lifecycle,
        secrets=_build_secrets_hook(oneiric_settings, lifecycle),
        health_path=None,
    )
    return OneiricWorkflowRuntime(
        resolver=resolver,
        lifecycle=lifecycle,
        orchestrator=orchestrator,
        event_tracker=event_tracker,  # Add event tracker
    )
```

#### 2.3 Add Event Hooks to Task Execution

Modify `_PhaseTask` class to emit events:

```python
class _PhaseTask:
    def __init__(
        self,
        name: str,
        runner: t.Callable[[], t.Any],
        event_tracker: WorkflowEventTracker | None = None,  # Add this
    ) -> None:
        self._name = name
        self._runner = runner
        self._event_tracker = event_tracker  # Store tracker

    async def run(self, payload: dict[str, t.Any] | None = None) -> t.Any:
        if self._event_tracker:
            self._event_tracker.node_started(self._name)

        try:
            result = self._runner()
            if inspect.isawaitable(result):
                result = await result

            if result is False:
                msg = f"workflow-task-failed: {self._name}"
                raise RuntimeError(msg)

            if self._event_tracker:
                self._event_tracker.node_completed(self._name, success=True)

            return result
        except Exception as e:
            if self._event_tracker:
                self._event_tracker.node_completed(
                    self._name,
                    success=False,
                    metadata={"error_type": type(e).__name__, "error_message": str(e)},
                )
            raise
```

#### 2.4 Update Task Registration

Update `_register_tasks` function:

```python
def _register_tasks(
    runtime: OneiricWorkflowRuntime,
    phases: PhaseCoordinator,
    options: t.Any,
) -> None:
    event_tracker = runtime.event_tracker

    task_factories = {
        "config_cleanup": lambda: _PhaseTask(
            "config_cleanup",
            lambda: phases.run_config_cleanup_phase(options),
            event_tracker,
        ),
        "configuration": lambda: _PhaseTask(
            "configuration",
            lambda: phases.run_configuration_phase(options),
            event_tracker,
        ),
        # ... rest of task factories with event_tracker parameter ...
    }

    # ... existing registration code ...
```

______________________________________________________________________

### Phase 3: Correlation Service (⭐ New Addition)

**Goal**: Correlate skill usage with Oneiric workflow execution patterns.

Create `/Users/les/Projects/crackerjack/crackerjack/skills/correlation.py`:

```python
"""Correlation service linking skills metrics with Oneiric workflow events."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crackerjack.skills.metrics import SkillInvocation, SkillMetrics
    from crackerjack.runtime.workflow_events import WorkflowEvent


@dataclass
class CorrelatedSession:
    """Correlated session data combining skills and workflow events."""

    session_id: str
    start_time: str
    end_time: str | None = None
    skill_invocations: list[dict[str, object]] = field(default_factory=list)
    workflow_events: list[dict[str, object]] = field(default_factory=list)

    # Computed metrics
    total_skill_duration: float = 0.0
    total_workflow_duration: float = 0.0
    skills_completed: int = 0
    workflow_nodes_completed: int = 0

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "skill_invocations": self.skill_invocations,
            "workflow_events": self.workflow_events,
            "total_skill_duration": self.total_skill_duration,
            "total_workflow_duration": self.total_workflow_duration,
            "skills_completed": self.skills_completed,
            "workflow_nodes_completed": self.workflow_nodes_completed,
        }


class SkillsWorkflowCorrelator:
    """Correlate skills metrics with Oneiric workflow execution."""

    def __init__(
        self,
        skills_file: Path | None = None,
        workflow_events_file: Path | None = None,
    ) -> None:
        """Initialize correlator.

        Args:
            skills_file: Path to skills metrics JSON file
            workflow_events_file: Path to workflow events JSON file
        """
        if skills_file is None:
            skills_file = Path.cwd() / ".session-buddy" / "skill_metrics.json"
        if workflow_events_file is None:
            workflow_events_file = (
                Path.cwd() / ".session-buddy" / "workflow_events.json"
            )

        self.skills_file = skills_file
        self.workflow_events_file = workflow_events_file
        self.sessions: dict[str, CorrelatedSession] = {}

    def correlate_by_session(
        self,
        skill_invocations: list[SkillInvocation],
        workflow_events: list[WorkflowEvent],
    ) -> dict[str, CorrelatedSession]:
        """Correlate skills and workflow events by session ID.

        Args:
            skill_invocations: List of skill invocations
            workflow_events: List of workflow events

        Returns:
            Dictionary mapping session IDs to correlated sessions
        """
        # Group skill invocations by session
        skills_by_session: dict[str, list[SkillInvocation]] = {}
        for invocation in skill_invocations:
            # Extract session_id from skill metadata (if available)
            session_id = self._extract_session_id(invocation)
            if session_id not in skills_by_session:
                skills_by_session[session_id] = []
            skills_by_session[session_id].append(invocation)

        # Group workflow events by session
        events_by_session: dict[str, list[WorkflowEvent]] = {}
        for event in workflow_events:
            session_id = event.session_id or "unknown"
            if session_id not in events_by_session:
                events_by_session[session_id] = []
            events_by_session[session_id].append(event)

        # Build correlated sessions
        all_session_ids = set(skills_by_session.keys()) | set(events_by_session.keys())

        for session_id in all_session_ids:
            skill_invocations_list = skills_by_session.get(session_id, [])
            workflow_events_list = events_by_session.get(session_id, [])

            session = CorrelatedSession(
                session_id=session_id,
                start_time=self._get_earliest_timestamp(
                    skill_invocations_list, workflow_events_list
                ),
                end_time=self._get_latest_timestamp(
                    skill_invocations_list, workflow_events_list
                ),
            )

            # Add skill invocations
            for invocation in skill_invocations_list:
                session.skill_invocations.append(invocation.to_dict())
                if invocation.completed:
                    session.skills_completed += 1
                if invocation.duration_seconds:
                    session.total_skill_duration += invocation.duration_seconds

            # Add workflow events
            for event in workflow_events_list:
                session.workflow_events.append(event.to_dict())
                if event.event_type == "node_completed":
                    session.workflow_nodes_completed += 1
                if event.event_type == "workflow_completed":
                    duration = event.metadata.get("duration_seconds")
                    if duration:
                        session.total_workflow_duration += duration

            self.sessions[session_id] = session

        return self.sessions

    def get_session_summary(self, session_id: str) -> dict[str, object] | None:
        """Get summary for a specific session.

        Args:
            session_id: Session ID to summarize

        Returns:
            Session summary dict or None if not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "skills_used": len(session.skill_invocations),
            "workflow_nodes_executed": session.workflow_nodes_completed,
            "total_skill_duration": session.total_skill_duration,
            "total_workflow_duration": session.total_workflow_duration,
            "skill_completion_rate": (
                session.skills_completed / len(session.skill_invocations) * 100
                if session.skill_invocations
                else 0
            ),
        }

    def generate_correlation_report(self) -> str:
        """Generate human-readable correlation report.

        Returns:
            Formatted report string
        """
        if not self.sessions:
            return "No correlated sessions found."

        lines = [
            "=" * 60,
            "Skills-Workflow Correlation Report",
            "=" * 60,
            "",
            f"Total Sessions: {len(self.sessions)}",
            "",
        ]

        for session_id, session in sorted(
            self.sessions.items(), key=lambda x: x[1].start_time, reverse=True
        ):
            lines.extend([
                f"Session: {session_id}",
                f"  Skills Used: {len(session.skill_invocations)}",
                f"  Skills Completed: {session.skills_completed}",
                f"  Workflow Nodes: {session.workflow_nodes_completed}",
                f"  Skill Duration: {session.total_skill_duration:.1f}s",
                f"  Workflow Duration: {session.total_workflow_duration:.1f}s",
                "",
            ])

        lines.append("=" * 60)
        return "\n".join(lines)

    def export_correlated_data(self, output_file: Path) -> None:
        """Export correlated data to JSON file.

        Args:
            output_file: Path to output JSON file
        """
        data = {
            "sessions": {
                session_id: session.to_dict()
                for session_id, session in self.sessions.items()
            },
            "exported_at": datetime.now().isoformat(),
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(data, indent=2))

    def _extract_session_id(self, invocation: SkillInvocation) -> str:
        """Extract session ID from skill invocation.

        Args:
            invocation: Skill invocation

        Returns:
            Session ID (or "unknown" if not found)
        """
        # Skills could store session_id in metadata if needed
        # For now, use skill_name + invoked_at as proxy
        return f"{invocation.skill_name}-{invocation.invoked_at[:10]}"

    def _get_earliest_timestamp(
        self,
        skill_invocations: list[SkillInvocation],
        workflow_events: list[WorkflowEvent],
    ) -> str:
        """Get earliest timestamp from skills and events.

        Args:
            skill_invocations: List of skill invocations
            workflow_events: List of workflow events

        Returns:
            Earliest ISO format timestamp
        """
        timestamps = []

        for invocation in skill_invocations:
            timestamps.append(invocation.invoked_at)

        for event in workflow_events:
            timestamps.append(event.timestamp)

        return min(timestamps) if timestamps else datetime.now().isoformat()

    def _get_latest_timestamp(
        self,
        skill_invocations: list[SkillInvocation],
        workflow_events: list[WorkflowEvent],
    ) -> str | None:
        """Get latest timestamp from skills and events.

        Args:
            skill_invocations: List of skill invocations
            workflow_events: List of workflow events

        Returns:
            Latest ISO format timestamp or None
        """
        timestamps = []

        for invocation in skill_invocations:
            timestamps.append(invocation.invoked_at)

        for event in workflow_events:
            timestamps.append(event.timestamp)

        return max(timestamps) if timestamps else None
```

______________________________________________________________________

### Phase 4: Session Integration (⭐ Integration Point)

**Goal**: Wire everything together in `SessionCoordinator`.

Modify `/Users/les/Projects/crackerjack/crackerjack/core/session_coordinator.py`:

```python
# Add to imports
from crackerjack.runtime.workflow_events import WorkflowEventTracker
from crackerjack.skills.correlation import SkillsWorkflowCorrelator

# Add to SessionCoordinator.__init__
class SessionCoordinator:
    def __init__(
        self,
        console: ConsoleInterface | None = None,
        pkg_path: Path | None = None,
        web_job_id: str | None = None,
    ) -> None:
        # ... existing initialization ...

        # Add workflow event tracker
        self.workflow_events: WorkflowEventTracker | None = None
        self.skills_correlator: SkillsWorkflowCorrelator | None = None

    def initialize_workflow_tracking(self) -> None:
        """Initialize workflow event tracking with session ID."""
        self.workflow_events = WorkflowEventTracker(session_id=self.session_id)
        self.skills_correlator = SkillsWorkflowCorrelator()
        logger.debug(f"Workflow tracking initialized for session: {self.session_id}")

    def get_correlation_report(self) -> str:
        """Generate correlation report for current session.

        Returns:
            Formatted correlation report string
        """
        if self.skills_correlator is None:
            return "Correlation tracking not initialized."

        return self.skills_correlator.generate_correlation_report()
```

______________________________________________________________________

## Best Practices

### 1. Workflow Correlation

**DO**:

- ✅ Use `session_id` as the primary correlation key
- ✅ Store both skill invocations and workflow events locally
- ✅ Generate correlation reports on-demand
- ✅ Maintain privacy-first approach (all local storage)

**DON'T**:

- ❌ Mix skill logic into Oneiric workflow DAGs
- ❌ Make Oneiric dependent on skills system
- ❌ Store PII in metrics or events
- ❌ Auto-upload correlation data to external services

### 2. Event Emission

**DO**:

- ✅ Emit events at workflow/node start and completion
- ✅ Include duration metadata for performance analysis
- ✅ Track success/failure status for all events
- ✅ Use ISO format timestamps for consistency

**DON'T**:

- ❌ Emit events for every internal operation (too noisy)
- ❌ Include sensitive data in event metadata
- ❌ Block workflow execution on event emission failures

### 3. Skills Tracking

**DO**:

- ✅ Track skill invocations with context manager pattern
- ✅ Record workflow paths chosen by users
- ✅ Capture follow-up actions for behavior analysis
- ✅ Aggregate metrics for reporting

**DON'T**:

- ❌ Track individual keystrokes or interactions (too invasive)
- ❌ Store skill markdown content in metrics (redundant)
- ❌ Track users across projects without explicit consent

### 4. Performance Considerations

**DO**:

- ✅ Use in-memory event tracking during execution
- ✌ Persist to disk at session end (batch writes)
- ✅ Keep correlation queries fast with proper indexing
- ✅ Use lazy evaluation for report generation

**DON'T**:

- ❌ Emit events on hot loops (>100Hz)
- ❌ Synchronous file I/O during workflow execution
- ❌ Load entire history into memory for correlation

______________________________________________________________________

## Usage Examples

### Example 1: Track Skill with Workflow Correlation

```python
from crackerjack.skills.metrics import track_skill
from crackerjack.core.session_coordinator import SessionCoordinator

# Initialize session with workflow tracking
coordinator = SessionCoordinator()
coordinator.initialize_workflow_tracking()

# Track skill usage (correlated by session_id)
complete = track_skill("crackerjack-run", "comprehensive")

# ... skill execution ...

complete(completed=True, follow_up_actions=["git commit"])

# Generate correlation report
report = coordinator.get_correlation_report()
print(report)
```

### Example 2: Correlate Skills with Oneiric Workflow Execution

```python
from crackerjack.skills.correlation import SkillsWorkflowCorrelator
from crackerjack.skills.metrics import get_tracker
from crackerjack.runtime.workflow_events import WorkflowEventTracker

# Get skill metrics
skills_tracker = get_tracker()
skill_invocations = skills_tracker._invocations

# Get workflow events
workflow_tracker = WorkflowEventTracker(session_id="abc123")
# ... workflow execution ...
workflow_events = workflow_tracker.events

# Correlate by session
correlator = SkillsWorkflowCorrelator()
sessions = correlator.correlate_by_session(skill_invocations, workflow_events)

# Generate report
print(correlator.generate_correlation_report())

# Export correlated data
correlator.export_correlated_data(Path(".session-buddy/correlated_session.json"))
```

### Example 3: Analyze Skill-Workflow Patterns

```python
from crackerjack.skills.correlation import SkillsWorkflowCorrelator

correlator = SkillsWorkflowCorrelator()
sessions = correlator.correlate_by_session(skill_invocations, workflow_events)

# Find patterns
for session_id, session in sessions.items():
    skill_duration = session.total_skill_duration
    workflow_duration = session.total_workflow_duration

    if skill_duration > workflow_duration * 2:
        print(f"Session {session_id}: Interactive work dominated automated execution")
        print(f"  Skills: {skill_duration:.1f}s vs Workflow: {workflow_duration:.1f}s")
```

______________________________________________________________________

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    User executes skill                           │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              Skill Metrics Tracker                               │
│                                                                  │
│  track_skill("crackerjack-run", "comprehensive")                │
│  ├─ Creates SkillInvocation with timestamp                      │
│  ├─ Returns completer function                                  │
│  └─ Waits for skill completion                                  │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              Oneiric Workflow Execution                          │
│                                                                  │
│  SessionCoordinator.initialize_workflow_tracking()              │
│  ├─ Creates WorkflowEventTracker with session_id                │
│  ├─ workflow_events.workflow_started("crackerjack")             │
│  ├─ workflow_events.node_started("fast_hooks")                  │
│  ├─ workflow_events.node_completed("fast_hooks")                │
│  ├─ ... (more nodes) ...                                        │
│  └─ workflow_events.workflow_completed()                        │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              Skill Completion                                    │
│                                                                  │
│  complete(completed=True, follow_up_actions=[...])              │
│  ├─ Calculates duration                                         │
│  ├─ Updates skill invocation                                    │
│  └─ Persists to skill_metrics.json                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              Correlation Service                                 │
│                                                                  │
│  SkillsWorkflowCorrelator.correlate_by_session()                │
│  ├─ Groups skill invocations by session_id                      │
│  ├─ Groups workflow events by session_id                        │
│  ├─ Computes correlated metrics                                 │
│  └─ Generates correlation reports                               │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              Analytics & Reporting                               │
│                                                                  │
│  generate_correlation_report()                                  │
│  ├─ Skills used per session                                     │
│  ├─ Workflow nodes executed                                     │
│  ├─ Duration analysis                                           │
│  └─ Pattern detection                                           │
└─────────────────────────────────────────────────────────────────┘
```

______________________________________________________________________

## FAQ

### Q: Why not track skills as Oneiric workflow nodes?

**A**: Skills are **interactive** while Oneiric workflows are **automated**. Oneiric DAG nodes are designed for deterministic task execution with clear dependencies. Skills involve user decision points, branching paths, and follow-up actions that don't fit the DAG model.

### Q: Should skill metrics use Oneiric's storage system?

**A**: No. Skills metrics are **domain-specific data** (skill usage, user choices) while Oneiric stores **workflow execution state**. Keeping them separate maintains clean boundaries and makes each system independently testable.

### Q: How do we correlate skill usage with Oneiric workflow execution?

**A**: Via **session_id correlation**. Both systems tag their events with a session_id, enabling post-hoc correlation without runtime dependencies. The `SkillsWorkflowCorrelator` service joins the data streams.

### Q: What if I want real-time correlation during execution?

**A**: Add a `publish_event` callback to both `SkillMetricsTracker` and `WorkflowEventTracker` that pushes events to a shared message bus (e.g., in-memory queue, local pub/sub). This enables real-time analytics without tight coupling.

### Q: Should we migrate to Oneiric's state management?

**A**: Not necessary. Skills metrics are **analytics data** (immutable events) while Oneiric state is **execution state** (mutable, transactional). JSON files are perfect for immutable event logs. Oneiric state management is overkill for this use case.

______________________________________________________________________

## Summary

### Recommended Integration Architecture

1. **Skills System**: Track skill invocations with existing `SkillMetricsTracker` (✅ complete)
1. **Oneiric Workflows**: Emit events via `WorkflowEventTracker` (⭐ new)
1. **Correlation**: Join via `SkillsWorkflowCorrelator` by session_id (⭐ new)
1. **Storage**: Separate JSON files, correlated on-demand (privacy-first)

### Key Principles

- ✅ **Separation of Concerns**: Skills (interactive) vs. Oneiric (automated)
- ✅ **Loose Coupling**: Correlation via session_id, not runtime dependencies
- ✅ **Privacy-First**: All local storage, no PII
- ✅ **Performance**: In-memory tracking, batch persistence
- ✅ **Autonomy**: Each system works independently

### Implementation Priority

1. **Phase 1**: Skill metrics tracking (✅ complete)
1. **Phase 2**: Oneiric workflow event tracking (⭐ implement next)
1. **Phase 3**: Correlation service (⭐ implement next)
1. **Phase 4**: SessionCoordinator integration (⭐ final step)

### Files to Create/Modify

**Create**:

- `/Users/les/Projects/crackerjack/crackerjack/runtime/workflow_events.py`
- `/Users/les/Projects/crackerjack/crackerjack/skills/correlation.py`

**Modify**:

- `/Users/les/Projects/crackerjack/crackerjack/runtime/oneiric_workflow.py`
- `/Users/les/Projects/crackerjack/crackerjack/core/session_coordinator.py`

**No Changes Needed**:

- `/Users/les/Projects/crackerjack/crackerjack/skills/metrics.py` (already complete)

______________________________________________________________________

## Next Steps

1. **Review this architecture** and confirm alignment with your goals
1. **Implement Phase 2** (workflow event tracking) in `oneiric_workflow.py`
1. **Implement Phase 3** (correlation service) in `skills/correlation.py`
1. **Integrate Phase 4** in `SessionCoordinator` for end-to-end tracking
1. **Test correlation** with sample skill invocations and workflow runs
1. **Generate reports** to validate data quality and insights

This architecture maintains clean separation between interactive skills and automated workflows while enabling powerful cross-system analytics through session-based correlation.
