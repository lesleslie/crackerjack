"""Adaptive Learning System for Agent Selection.

Learns from execution results to improve agent selection over time through
success tracking, capability refinement, and performance optimization.
"""

import asyncio
import json
import logging
import typing as t
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .agent_registry import AgentCapability, RegisteredAgent
from .agent_selector import AgentScore, TaskDescription


@dataclass
class ExecutionRecord:
    """Record of an agent execution."""

    timestamp: datetime
    agent_name: str
    agent_source: str
    task_description: str
    task_capabilities: list[str]
    success: bool
    execution_time: float
    confidence_score: float
    final_score: float
    error_message: str | None = None
    task_hash: str | None = None  # For grouping similar tasks


@dataclass
class AgentPerformanceMetrics:
    """Performance metrics for an agent."""

    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    average_execution_time: float = 0.0
    average_confidence: float = 0.0
    success_rate: float = 0.0
    capability_success_rates: dict[str, float] = field(default_factory=dict)
    recent_performance_trend: float = 0.0  # -1 to 1, negative = declining
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class LearningInsight:
    """A learning insight discovered from execution data."""

    insight_type: str  # "capability_strength", "task_pattern", "failure_pattern"
    agent_name: str
    confidence: float  # 0-1
    description: str
    supporting_evidence: dict[str, t.Any]
    discovered_at: datetime = field(default_factory=datetime.now)


class AdaptiveLearningSystem:
    """System that learns from agent execution results."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.data_dir = data_dir or Path.home() / ".crackerjack" / "intelligence"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.execution_log_path = self.data_dir / "execution_log.jsonl"
        self.metrics_path = self.data_dir / "agent_metrics.json"
        self.insights_path = self.data_dir / "learning_insights.json"

        self._execution_records: list[ExecutionRecord] = []
        self._agent_metrics: dict[str, AgentPerformanceMetrics] = {}
        self._learning_insights: list[LearningInsight] = []

        self._load_existing_data()

    def _load_existing_data(self) -> None:
        """Load existing learning data from disk."""
        try:
            # Load execution records
            if self.execution_log_path.exists():
                with self.execution_log_path.open("r") as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            data["timestamp"] = datetime.fromisoformat(
                                data["timestamp"]
                            )
                            record = ExecutionRecord(**data)
                            self._execution_records.append(record)

                self.logger.debug(
                    f"Loaded {len(self._execution_records)} execution records"
                )

            # Load agent metrics
            if self.metrics_path.exists():
                with self.metrics_path.open("r") as f:
                    metrics_data = json.load(f)
                    for agent_name, data in metrics_data.items():
                        data["last_updated"] = datetime.fromisoformat(
                            data["last_updated"]
                        )
                        self._agent_metrics[agent_name] = AgentPerformanceMetrics(
                            **data
                        )

                self.logger.debug(
                    f"Loaded metrics for {len(self._agent_metrics)} agents"
                )

            # Load learning insights
            if self.insights_path.exists():
                with self.insights_path.open("r") as f:
                    insights_data = json.load(f)
                    for insight_data in insights_data:
                        insight_data["discovered_at"] = datetime.fromisoformat(
                            insight_data["discovered_at"]
                        )
                        insight = LearningInsight(**insight_data)
                        self._learning_insights.append(insight)

                self.logger.debug(
                    f"Loaded {len(self._learning_insights)} learning insights"
                )

        except Exception as e:
            self.logger.warning(f"Error loading existing learning data: {e}")

    async def record_execution(
        self,
        agent: RegisteredAgent,
        task: TaskDescription,
        success: bool,
        execution_time: float,
        agent_score: AgentScore,
        error_message: str | None = None,
    ) -> None:
        """Record the result of an agent execution."""
        try:
            # Create execution record
            record = ExecutionRecord(
                timestamp=datetime.now(),
                agent_name=agent.metadata.name,
                agent_source=agent.metadata.source.value,
                task_description=task.description,
                task_capabilities=[
                    cap.value for cap in self._infer_task_capabilities(task)
                ],
                success=success,
                execution_time=execution_time,
                confidence_score=agent_score.confidence_factor,
                final_score=agent_score.final_score,
                error_message=error_message,
                task_hash=self._hash_task(task),
            )

            # Add to records
            self._execution_records.append(record)

            # Update agent metrics
            await self._update_agent_metrics(record)

            # Persist to disk
            await self._persist_execution_record(record)

            # Trigger learning analysis (async)
            asyncio.create_task(self._analyze_and_learn())

            self.logger.debug(
                f"Recorded execution: {agent.metadata.name} on '{task.description[:30]}...' "
                f"({'success' if success else 'failure'})"
            )

        except Exception as e:
            self.logger.error(f"Error recording execution: {e}")

    def _infer_task_capabilities(self, task: TaskDescription) -> set[AgentCapability]:
        """Infer capabilities needed for a task (simplified version)."""
        # This could import from agent_selector, but kept simple to avoid circular imports
        capabilities = set()

        text = task.description.lower()

        if any(word in text for word in ["architect", "design", "structure"]):
            capabilities.add(AgentCapability.ARCHITECTURE)
        if any(word in text for word in ["refactor", "clean", "improve"]):
            capabilities.add(AgentCapability.REFACTORING)
        if any(word in text for word in ["test", "pytest", "coverage"]):
            capabilities.add(AgentCapability.TESTING)
        if any(word in text for word in ["security", "secure", "vulnerability"]):
            capabilities.add(AgentCapability.SECURITY)
        if any(word in text for word in ["performance", "optimize", "speed"]):
            capabilities.add(AgentCapability.PERFORMANCE)
        if any(word in text for word in ["document", "readme", "comment"]):
            capabilities.add(AgentCapability.DOCUMENTATION)
        if any(word in text for word in ["format", "style", "lint"]):
            capabilities.add(AgentCapability.FORMATTING)
        if any(word in text for word in ["debug", "fix", "error"]):
            capabilities.add(AgentCapability.DEBUGGING)

        if not capabilities:
            capabilities.add(AgentCapability.CODE_ANALYSIS)

        return capabilities

    def _hash_task(self, task: TaskDescription) -> str:
        """Create a hash for grouping similar tasks."""
        # Simple hash based on key words
        words = task.description.lower().split()
        key_words = [w for w in words if len(w) > 3][
            :10
        ]  # Take first 10 significant words
        return "_".join(sorted(key_words))

    async def _update_agent_metrics(self, record: ExecutionRecord) -> None:
        """Update metrics for an agent based on execution record."""
        agent_name = record.agent_name

        if agent_name not in self._agent_metrics:
            self._agent_metrics[agent_name] = AgentPerformanceMetrics()

        metrics = self._agent_metrics[agent_name]

        # Update basic counters
        metrics.total_executions += 1
        if record.success:
            metrics.successful_executions += 1
        else:
            metrics.failed_executions += 1

        # Update success rate
        metrics.success_rate = metrics.successful_executions / metrics.total_executions

        # Update average execution time (weighted average)
        if metrics.total_executions == 1:
            metrics.average_execution_time = record.execution_time
        else:
            # Exponential moving average with alpha=0.3
            alpha = 0.3
            metrics.average_execution_time = (
                alpha * record.execution_time
                + (1 - alpha) * metrics.average_execution_time
            )

        # Update average confidence
        if metrics.total_executions == 1:
            metrics.average_confidence = record.confidence_score
        else:
            alpha = 0.3
            metrics.average_confidence = (
                alpha * record.confidence_score
                + (1 - alpha) * metrics.average_confidence
            )

        # Update capability-specific success rates
        for capability in record.task_capabilities:
            if capability not in metrics.capability_success_rates:
                metrics.capability_success_rates[capability] = 0.0

            # Update capability success rate with weighted average
            current_rate = metrics.capability_success_rates[capability]
            success_value = 1.0 if record.success else 0.0

            # Simple moving average for capability success
            capability_executions = len(
                [
                    r
                    for r in self._execution_records[-50:]  # Last 50 records
                    if r.agent_name == agent_name and capability in r.task_capabilities
                ]
            )

            if capability_executions <= 1:
                metrics.capability_success_rates[capability] = success_value
            else:
                alpha = min(0.5, 2.0 / capability_executions)  # Adaptive learning rate
                metrics.capability_success_rates[capability] = (
                    alpha * success_value + (1 - alpha) * current_rate
                )

        # Calculate recent performance trend (last 10 executions)
        recent_records = [
            r for r in self._execution_records[-20:] if r.agent_name == agent_name
        ][-10:]  # Last 10 for this agent

        if len(recent_records) >= 5:
            # Calculate trend using linear regression (simplified)
            recent_success_rates = []
            window_size = 3

            for i in range(len(recent_records) - window_size + 1):
                window = recent_records[i : i + window_size]
                window_success_rate = sum(1 for r in window if r.success) / len(window)
                recent_success_rates.append(window_success_rate)

            if len(recent_success_rates) >= 2:
                # Simple trend: compare first half to second half
                mid = len(recent_success_rates) // 2
                first_half_avg = sum(recent_success_rates[:mid]) / max(mid, 1)
                second_half_avg = sum(recent_success_rates[mid:]) / max(
                    len(recent_success_rates) - mid, 1
                )
                metrics.recent_performance_trend = second_half_avg - first_half_avg

        metrics.last_updated = datetime.now()

        # Persist metrics
        await self._persist_agent_metrics()

    async def _persist_execution_record(self, record: ExecutionRecord) -> None:
        """Persist execution record to disk."""
        try:
            with self.execution_log_path.open("a") as f:
                data = asdict(record)
                data["timestamp"] = data["timestamp"].isoformat()
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            self.logger.error(f"Error persisting execution record: {e}")

    async def _persist_agent_metrics(self) -> None:
        """Persist agent metrics to disk."""
        try:
            metrics_data = {}
            for agent_name, metrics in self._agent_metrics.items():
                data = asdict(metrics)
                data["last_updated"] = data["last_updated"].isoformat()
                metrics_data[agent_name] = data

            with self.metrics_path.open("w") as f:
                json.dump(metrics_data, f, indent=2)

        except Exception as e:
            self.logger.error(f"Error persisting agent metrics: {e}")

    async def _persist_learning_insights(self) -> None:
        """Persist learning insights to disk."""
        try:
            insights_data = []
            for insight in self._learning_insights:
                data = asdict(insight)
                data["discovered_at"] = data["discovered_at"].isoformat()
                insights_data.append(data)

            with self.insights_path.open("w") as f:
                json.dump(insights_data, f, indent=2)

        except Exception as e:
            self.logger.error(f"Error persisting learning insights: {e}")

    async def _analyze_and_learn(self) -> None:
        """Analyze execution data and generate learning insights."""
        try:
            new_insights = []

            # Analyze capability strengths
            capability_insights = self._analyze_capability_strengths()
            new_insights.extend(capability_insights)

            # Analyze failure patterns
            failure_insights = self._analyze_failure_patterns()
            new_insights.extend(failure_insights)

            # Analyze task patterns
            task_pattern_insights = self._analyze_task_patterns()
            new_insights.extend(task_pattern_insights)

            # Add new insights (avoid duplicates)
            for insight in new_insights:
                if not self._is_duplicate_insight(insight):
                    self._learning_insights.append(insight)
                    self.logger.debug(f"New learning insight: {insight.description}")

            # Persist insights
            await self._persist_learning_insights()

        except Exception as e:
            self.logger.error(f"Error in learning analysis: {e}")

    def _analyze_capability_strengths(self) -> list[LearningInsight]:
        """Analyze which agents excel at which capabilities."""
        insights = []

        # Group records by capability
        capability_performance = defaultdict(lambda: defaultdict(list))

        for record in self._execution_records[-100:]:  # Last 100 records
            for capability in record.task_capabilities:
                capability_performance[capability][record.agent_name].append(
                    record.success
                )

        # Find agents with exceptional performance in specific capabilities
        for capability, agents in capability_performance.items():
            for agent_name, successes in agents.items():
                if len(successes) >= 3:  # Minimum sample size
                    success_rate = sum(successes) / len(successes)

                    if success_rate >= 0.9:  # High success rate
                        insight = LearningInsight(
                            insight_type="capability_strength",
                            agent_name=agent_name,
                            confidence=min(success_rate, len(successes) / 10.0),
                            description=f"{agent_name} excels at {capability} tasks (success rate: {success_rate:.1%})",
                            supporting_evidence={
                                "capability": capability,
                                "success_rate": success_rate,
                                "sample_size": len(successes),
                                "recent_performance": successes,
                            },
                        )
                        insights.append(insight)

        return insights

    def _analyze_failure_patterns(self) -> list[LearningInsight]:
        """Analyze common failure patterns."""
        insights = []

        # Group failures by agent and error patterns
        failure_patterns = defaultdict(lambda: defaultdict(int))

        for record in self._execution_records[-100:]:
            if not record.success and record.error_message:
                # Extract error pattern (simplified)
                error_type = self._categorize_error(record.error_message)
                failure_patterns[record.agent_name][error_type] += 1

        # Find significant failure patterns
        for agent_name, patterns in failure_patterns.items():
            total_failures = sum(patterns.values())
            if total_failures >= 3:  # Minimum sample size
                for error_type, count in patterns.items():
                    if count / total_failures >= 0.5:  # Common pattern
                        insight = LearningInsight(
                            insight_type="failure_pattern",
                            agent_name=agent_name,
                            confidence=count / total_failures,
                            description=f"{agent_name} commonly fails with {error_type} errors",
                            supporting_evidence={
                                "error_type": error_type,
                                "occurrence_rate": count / total_failures,
                                "total_failures": total_failures,
                                "pattern_count": count,
                            },
                        )
                        insights.append(insight)

        return insights

    def _analyze_task_patterns(self) -> list[LearningInsight]:
        """Analyze task patterns and agent preferences."""
        insights = []

        # Group by task hash to find patterns
        task_performance = defaultdict(lambda: defaultdict(list))

        for record in self._execution_records[-100:]:
            if record.task_hash:
                task_performance[record.task_hash][record.agent_name].append(
                    record.success
                )

        # Find task types where specific agents consistently perform well
        for task_hash, agents in task_performance.items():
            if len(agents) > 1:  # Multiple agents tried this task type
                best_agent = None
                best_rate = 0.0

                for agent_name, successes in agents.items():
                    if len(successes) >= 2:  # Minimum attempts
                        success_rate = sum(successes) / len(successes)
                        if success_rate > best_rate:
                            best_rate = success_rate
                            best_agent = agent_name

                if best_agent and best_rate >= 0.8:
                    # Get example task description
                    example_task = next(
                        (
                            r.task_description
                            for r in self._execution_records
                            if r.task_hash == task_hash and r.agent_name == best_agent
                        ),
                        "Unknown task pattern",
                    )

                    insight = LearningInsight(
                        insight_type="task_pattern",
                        agent_name=best_agent,
                        confidence=best_rate,
                        description=f"{best_agent} is preferred for tasks like: {example_task[:100]}...",
                        supporting_evidence={
                            "task_pattern": task_hash,
                            "success_rate": best_rate,
                            "example_task": example_task,
                            "competing_agents": list(agents.keys()),
                        },
                    )
                    insights.append(insight)

        return insights

    def _categorize_error(self, error_message: str) -> str:
        """Categorize error message into type."""
        error_lower = error_message.lower()

        if "timeout" in error_lower:
            return "timeout"
        elif "import" in error_lower:
            return "import_error"
        elif "type" in error_lower:
            return "type_error"
        elif "permission" in error_lower:
            return "permission_error"
        elif "not found" in error_lower:
            return "not_found"
        elif "syntax" in error_lower:
            return "syntax_error"
        else:
            return "other"

    def _is_duplicate_insight(self, new_insight: LearningInsight) -> bool:
        """Check if insight already exists."""
        for existing in self._learning_insights:
            if (
                existing.insight_type == new_insight.insight_type
                and existing.agent_name == new_insight.agent_name
                and abs(existing.confidence - new_insight.confidence) < 0.1
            ):
                return True
        return False

    def get_agent_recommendations(
        self,
        task: TaskDescription,
        candidate_agents: list[str],
    ) -> dict[str, float]:
        """Get recommendations for agents based on learning."""
        task_capabilities = [cap.value for cap in self._infer_task_capabilities(task)]
        task_hash = self._hash_task(task)

        return {
            agent_name: min(
                self._calculate_agent_score(agent_name, task_capabilities, task_hash),
                1.0,
            )
            for agent_name in candidate_agents
        }

    def _calculate_agent_score(
        self, agent_name: str, task_capabilities: list[str], task_hash: str
    ) -> float:
        """Calculate recommendation score for a specific agent."""
        score = 0.0

        # Base score from metrics
        if agent_name in self._agent_metrics:
            metrics = self._agent_metrics[agent_name]
            score += self._calculate_metrics_score(metrics, task_capabilities)

        # Insights bonus/penalty
        score += self._calculate_insights_score(
            agent_name, task_capabilities, task_hash
        )

        return score

    def _calculate_metrics_score(
        self, metrics: "AgentMetrics", task_capabilities: list[str]
    ) -> float:
        """Calculate score based on agent metrics."""
        score = metrics.success_rate * 0.4

        # Capability-specific performance
        capability_scores = [
            metrics.capability_success_rates[capability]
            for capability in task_capabilities
            if capability in metrics.capability_success_rates
        ]

        if capability_scores:
            score += (sum(capability_scores) / len(capability_scores)) * 0.4

        # Recent trend adjustment
        if metrics.recent_performance_trend > 0:
            score += metrics.recent_performance_trend * 0.1
        elif metrics.recent_performance_trend < 0:
            score += metrics.recent_performance_trend * 0.05  # Smaller penalty

        return score

    def _calculate_insights_score(
        self, agent_name: str, task_capabilities: list[str], task_hash: str
    ) -> float:
        """Calculate score adjustment based on learning insights."""
        relevant_insights = [
            insight
            for insight in self._learning_insights
            if insight.agent_name == agent_name
        ]

        score_adjustment = 0.0
        for insight in relevant_insights:
            if insight.insight_type == "capability_strength":
                insight_capability = insight.supporting_evidence.get("capability", "")
                if insight_capability in task_capabilities:
                    score_adjustment += insight.confidence * 0.1
            elif insight.insight_type == "task_pattern":
                if insight.supporting_evidence.get("task_pattern") == task_hash:
                    score_adjustment += insight.confidence * 0.15
            elif insight.insight_type == "failure_pattern":
                score_adjustment -= insight.confidence * 0.05

        return score_adjustment

    def get_learning_summary(self) -> dict[str, t.Any]:
        """Get a summary of learning progress."""
        total_records = len(self._execution_records)

        if total_records == 0:
            return {"status": "no_data"}

        recent_records = self._execution_records[-50:]
        recent_success_rate = sum(1 for r in recent_records if r.success) / len(
            recent_records
        )

        # Agent performance summary
        agent_summary = {}
        for agent_name, metrics in self._agent_metrics.items():
            agent_summary[agent_name] = {
                "executions": metrics.total_executions,
                "success_rate": metrics.success_rate,
                "trend": metrics.recent_performance_trend,
            }

        # Insights summary
        insights_by_type = defaultdict(int)
        for insight in self._learning_insights:
            insights_by_type[insight.insight_type] += 1

        return {
            "status": "active",
            "total_executions": total_records,
            "recent_success_rate": recent_success_rate,
            "agents_tracked": len(self._agent_metrics),
            "insights_discovered": len(self._learning_insights),
            "insights_by_type": dict(insights_by_type),
            "top_performers": sorted(
                agent_summary.items(),
                key=lambda x: x[1]["success_rate"],
                reverse=True,
            )[:5],
        }


# Global learning system instance
_learning_system_instance: AdaptiveLearningSystem | None = None


async def get_learning_system() -> AdaptiveLearningSystem:
    """Get or create the global learning system."""
    global _learning_system_instance

    if _learning_system_instance is None:
        _learning_system_instance = AdaptiveLearningSystem()

    return _learning_system_instance
