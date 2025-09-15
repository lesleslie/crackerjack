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
    task_hash: str | None = None


@dataclass
class AgentPerformanceMetrics:
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    average_execution_time: float = 0.0
    average_confidence: float = 0.0
    success_rate: float = 0.0
    capability_success_rates: dict[str, float] = field(default_factory=dict[str, t.Any])
    recent_performance_trend: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class LearningInsight:
    insight_type: str
    agent_name: str
    confidence: float
    description: str
    supporting_evidence: dict[str, t.Any]
    discovered_at: datetime = field(default_factory=datetime.now)


class AdaptiveLearningSystem:
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
        try:
            self._load_execution_records()
            self._load_agent_metrics()
            self._load_learning_insights()
        except Exception as e:
            self.logger.warning(f"Error loading existing learning data: {e}")

    def _load_execution_records(self) -> None:
        if not self.execution_log_path.exists():
            return

        with self.execution_log_path.open("r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                    record = ExecutionRecord(**data)
                    self._execution_records.append(record)

        self.logger.debug(f"Loaded {len(self._execution_records)} execution records")

    def _load_agent_metrics(self) -> None:
        if not self.metrics_path.exists():
            return

        with self.metrics_path.open("r") as f:
            metrics_data = json.load(f)
            for agent_name, data in metrics_data.items():
                data["last_updated"] = datetime.fromisoformat(data["last_updated"])
                self._agent_metrics[agent_name] = AgentPerformanceMetrics(**data)

        self.logger.debug(f"Loaded metrics for {len(self._agent_metrics)} agents")

    def _load_learning_insights(self) -> None:
        if not self.insights_path.exists():
            return

        with self.insights_path.open("r") as f:
            insights_data = json.load(f)
            for insight_data in insights_data:
                insight_data["discovered_at"] = datetime.fromisoformat(
                    insight_data["discovered_at"]
                )
                insight = LearningInsight(**insight_data)
                self._learning_insights.append(insight)

        self.logger.debug(f"Loaded {len(self._learning_insights)} learning insights")

    async def record_execution(
        self,
        agent: RegisteredAgent,
        task: TaskDescription,
        success: bool,
        execution_time: float,
        agent_score: AgentScore,
        error_message: str | None = None,
    ) -> None:
        try:
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

            self._execution_records.append(record)

            await self._update_agent_metrics(record)

            await self._persist_execution_record(record)

            asyncio.create_task(self._analyze_and_learn())

            self.logger.debug(
                f"Recorded execution: {agent.metadata.name} on '{task.description[:30]}...' "
                f"({'success' if success else 'failure'})"
            )

        except Exception as e:
            self.logger.error(f"Error recording execution: {e}")

    def _infer_task_capabilities(self, task: TaskDescription) -> set[AgentCapability]:
        capabilities = set()
        text = task.description.lower()

        capability_keywords = {
            AgentCapability.ARCHITECTURE: ("architect", "design", "structure"),
            AgentCapability.REFACTORING: ("refactor", "clean", "improve"),
            AgentCapability.TESTING: ("test", "pytest", "coverage"),
            AgentCapability.SECURITY: ("security", "secure", "vulnerability"),
            AgentCapability.PERFORMANCE: ("performance", "optimize", "speed"),
            AgentCapability.DOCUMENTATION: ("document", "readme", "comment"),
            AgentCapability.FORMATTING: ("format", "style", "lint"),
            AgentCapability.DEBUGGING: ("debug", "fix", "error"),
        }

        for capability, keywords in capability_keywords.items():
            if any(word in text for word in keywords):
                capabilities.add(capability)

        if not capabilities:
            capabilities.add(AgentCapability.CODE_ANALYSIS)

        return capabilities

    def _hash_task(self, task: TaskDescription) -> str:
        words = task.description.lower().split()
        key_words = [w for w in words if len(w) > 3][:10]
        return "_".join(sorted(key_words))

    async def _update_agent_metrics(self, record: ExecutionRecord) -> None:
        agent_name = record.agent_name
        metrics = self._ensure_agent_metrics(agent_name)

        self._update_basic_counters(metrics, record)
        self._update_execution_averages(metrics, record)
        self._update_capability_success_rates(metrics, record, agent_name)
        self._update_performance_trend(metrics, agent_name)

        metrics.last_updated = datetime.now()
        await self._persist_agent_metrics()

    def _ensure_agent_metrics(self, agent_name: str) -> AgentPerformanceMetrics:
        if agent_name not in self._agent_metrics:
            self._agent_metrics[agent_name] = AgentPerformanceMetrics()
        return self._agent_metrics[agent_name]

    def _update_basic_counters(
        self, metrics: AgentPerformanceMetrics, record: ExecutionRecord
    ) -> None:
        metrics.total_executions += 1
        if record.success:
            metrics.successful_executions += 1
        else:
            metrics.failed_executions += 1
        metrics.success_rate = metrics.successful_executions / metrics.total_executions

    def _update_execution_averages(
        self, metrics: AgentPerformanceMetrics, record: ExecutionRecord
    ) -> None:
        if metrics.total_executions == 1:
            metrics.average_execution_time = record.execution_time
            metrics.average_confidence = record.confidence_score
        else:
            alpha = 0.3
            metrics.average_execution_time = (
                alpha * record.execution_time
                + (1 - alpha) * metrics.average_execution_time
            )
            metrics.average_confidence = (
                alpha * record.confidence_score
                + (1 - alpha) * metrics.average_confidence
            )

    def _update_capability_success_rates(
        self, metrics: AgentPerformanceMetrics, record: ExecutionRecord, agent_name: str
    ) -> None:
        success_value = 1.0 if record.success else 0.0

        for capability in record.task_capabilities:
            if capability not in metrics.capability_success_rates:
                metrics.capability_success_rates[capability] = 0.0

            current_rate = metrics.capability_success_rates[capability]
            capability_executions = len(
                [
                    r
                    for r in self._execution_records[-50:]
                    if r.agent_name == agent_name and capability in r.task_capabilities
                ]
            )

            if capability_executions <= 1:
                metrics.capability_success_rates[capability] = success_value
            else:
                alpha = min(0.5, 2.0 / capability_executions)
                metrics.capability_success_rates[capability] = (
                    alpha * success_value + (1 - alpha) * current_rate
                )

    def _update_performance_trend(
        self, metrics: AgentPerformanceMetrics, agent_name: str
    ) -> None:
        recent_records = [
            r for r in self._execution_records[-20:] if r.agent_name == agent_name
        ][-10:]

        if len(recent_records) >= 5:
            recent_success_rates = self._calculate_windowed_success_rates(
                recent_records
            )
            if len(recent_success_rates) >= 2:
                mid = len(recent_success_rates) // 2
                first_half_avg = sum(recent_success_rates[:mid]) / max(mid, 1)
                second_half_avg = sum(recent_success_rates[mid:]) / max(
                    len(recent_success_rates) - mid, 1
                )
                metrics.recent_performance_trend = second_half_avg - first_half_avg

    def _calculate_windowed_success_rates(
        self, recent_records: list[ExecutionRecord]
    ) -> list[float]:
        window_size = 3
        success_rates = []

        for i in range(len(recent_records) - window_size + 1):
            window = recent_records[i : i + window_size]
            window_success_rate = sum(1 for r in window if r.success) / len(window)
            success_rates.append(window_success_rate)

        return success_rates

    async def _persist_execution_record(self, record: ExecutionRecord) -> None:
        try:
            with self.execution_log_path.open("a") as f:
                data = asdict(record)
                data["timestamp"] = data["timestamp"].isoformat()
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            self.logger.error(f"Error persisting execution record: {e}")

    async def _persist_agent_metrics(self) -> None:
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
        try:
            new_insights = []

            capability_insights = self._analyze_capability_strengths()
            new_insights.extend(capability_insights)

            failure_insights = self._analyze_failure_patterns()
            new_insights.extend(failure_insights)

            task_pattern_insights = self._analyze_task_patterns()
            new_insights.extend(task_pattern_insights)

            for insight in new_insights:
                if not self._is_duplicate_insight(insight):
                    self._learning_insights.append(insight)
                    self.logger.debug(f"New learning insight: {insight.description}")

            await self._persist_learning_insights()

        except Exception as e:
            self.logger.error(f"Error in learning analysis: {e}")

    def _analyze_capability_strengths(self) -> list[LearningInsight]:
        capability_performance = self._group_capability_performance()
        insights = []

        for capability, agents in capability_performance.items():
            insights.extend(self._find_capability_experts(capability, agents))

        return insights

    def _group_capability_performance(self) -> dict[str, dict[str, list[bool]]]:
        def make_inner_defaultdict() -> defaultdict[str, list[bool]]:
            return defaultdict(list)

        capability_performance: dict[str, dict[str, list[bool]]] = defaultdict(
            make_inner_defaultdict
        )

        for record in self._execution_records[-100:]:
            for capability in record.task_capabilities:
                capability_performance[capability][record.agent_name].append(
                    record.success
                )

        return dict[str, t.Any](capability_performance)

    def _find_capability_experts(
        self, capability: str, agents: dict[str, list[bool]]
    ) -> list[LearningInsight]:
        insights = []

        for agent_name, successes in agents.items():
            if len(successes) >= 3:
                success_rate = sum(successes) / len(successes)

                if success_rate >= 0.9:
                    insight = LearningInsight(
                        insight_type="capability_strength",
                        agent_name=agent_name,
                        confidence=min(success_rate, len(successes) / 10.0),
                        description=f"{agent_name} excels at {capability} tasks (success rate: {success_rate: .1 %})",
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
        failure_patterns = self._group_failure_patterns()
        return self._extract_significant_failure_insights(failure_patterns)

    def _group_failure_patterns(self) -> dict[str, dict[str, int]]:
        def make_inner_defaultdict() -> defaultdict[str, int]:
            return defaultdict(int)

        failure_patterns: dict[str, dict[str, int]] = defaultdict(
            make_inner_defaultdict
        )

        for record in self._execution_records[-100:]:
            if not record.success and record.error_message:
                error_type = self._categorize_error(record.error_message)
                failure_patterns[record.agent_name][error_type] += 1

        return {
            agent_name: dict[str, t.Any](patterns)
            for agent_name, patterns in failure_patterns.items()
        }

    def _extract_significant_failure_insights(
        self, failure_patterns: dict[str, dict[str, int]]
    ) -> list[LearningInsight]:
        insights = []

        for agent_name, patterns in failure_patterns.items():
            agent_insights = self._extract_agent_failure_insights(agent_name, patterns)
            insights.extend(agent_insights)

        return insights

    def _extract_agent_failure_insights(
        self, agent_name: str, patterns: dict[str, int]
    ) -> list[LearningInsight]:
        total_failures = sum(patterns.values())
        if total_failures < 3:
            return []

        insights = []
        for error_type, count in patterns.items():
            if count / total_failures >= 0.5:
                insight = self._create_failure_insight(
                    agent_name, error_type, count, total_failures
                )
                insights.append(insight)

        return insights

    def _create_failure_insight(
        self, agent_name: str, error_type: str, count: int, total_failures: int
    ) -> LearningInsight:
        return LearningInsight(
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

    def _analyze_task_patterns(self) -> list[LearningInsight]:
        task_performance = self._group_task_performance()
        insights = []

        for task_hash, agents in task_performance.items():
            if len(agents) > 1:
                best_agent, best_rate = self._find_best_performing_agent(agents)

                if best_agent and best_rate >= 0.8:
                    insight = self._create_task_pattern_insight(
                        task_hash, best_agent, best_rate, agents
                    )
                    insights.append(insight)

        return insights

    def _group_task_performance(self) -> dict[str, dict[str, list[bool]]]:
        def make_inner_defaultdict() -> defaultdict[str, list[bool]]:
            return defaultdict(list)

        task_performance: dict[str, dict[str, list[bool]]] = defaultdict(
            make_inner_defaultdict
        )

        for record in self._execution_records[-100:]:
            if record.task_hash:
                task_performance[record.task_hash][record.agent_name].append(
                    record.success
                )

        return dict[str, t.Any](task_performance)

    def _find_best_performing_agent(
        self, agents: dict[str, list[bool]]
    ) -> tuple[str | None, float]:
        best_agent = None
        best_rate = 0.0

        for agent_name, successes in agents.items():
            if len(successes) >= 2:
                success_rate = sum(successes) / len(successes)
                if success_rate > best_rate:
                    best_rate = success_rate
                    best_agent = agent_name

        return best_agent, best_rate

    def _create_task_pattern_insight(
        self,
        task_hash: str,
        best_agent: str,
        best_rate: float,
        agents: dict[str, list[bool]],
    ) -> LearningInsight:
        example_task = next(
            (
                r.task_description
                for r in self._execution_records
                if r.task_hash == task_hash and r.agent_name == best_agent
            ),
            "Unknown task pattern",
        )

        return LearningInsight(
            insight_type="task_pattern",
            agent_name=best_agent,
            confidence=best_rate,
            description=f"{best_agent} is preferred for tasks like: {example_task[:100]}...",
            supporting_evidence={
                "task_pattern": task_hash,
                "success_rate": best_rate,
                "example_task": example_task,
                "competing_agents": list[t.Any](agents.keys()),
            },
        )

    def _categorize_error(self, error_message: str) -> str:
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

        return "other"

    def _is_duplicate_insight(self, new_insight: LearningInsight) -> bool:
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
        score = 0.0

        if agent_name in self._agent_metrics:
            metrics = self._agent_metrics[agent_name]
            score += self._calculate_metrics_score(metrics, task_capabilities)

        score += self._calculate_insights_score(
            agent_name, task_capabilities, task_hash
        )

        return score

    def _calculate_metrics_score(
        self, metrics: AgentPerformanceMetrics, task_capabilities: list[str]
    ) -> float:
        score = metrics.success_rate * 0.4

        capability_scores = [
            metrics.capability_success_rates[capability]
            for capability in task_capabilities
            if capability in metrics.capability_success_rates
        ]

        if capability_scores:
            score += (sum(capability_scores) / len(capability_scores)) * 0.4

        if metrics.recent_performance_trend > 0:
            score += metrics.recent_performance_trend * 0.1
        elif metrics.recent_performance_trend < 0:
            score += metrics.recent_performance_trend * 0.05

        return score

    def _calculate_insights_score(
        self, agent_name: str, task_capabilities: list[str], task_hash: str
    ) -> float:
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
        total_records = len(self._execution_records)

        if total_records == 0:
            return {"status": "no_data"}

        recent_records = self._execution_records[-50:]
        recent_success_rate = sum(1 for r in recent_records if r.success) / len(
            recent_records
        )

        agent_summary = {}
        for agent_name, metrics in self._agent_metrics.items():
            agent_summary[agent_name] = {
                "executions": metrics.total_executions,
                "success_rate": metrics.success_rate,
                "trend": metrics.recent_performance_trend,
            }

        insights_by_type: dict[str, int] = defaultdict(int)
        for insight in self._learning_insights:
            insights_by_type[insight.insight_type] += 1

        return {
            "status": "active",
            "total_executions": total_records,
            "recent_success_rate": recent_success_rate,
            "agents_tracked": len(self._agent_metrics),
            "insights_discovered": len(self._learning_insights),
            "insights_by_type": dict[str, t.Any](insights_by_type),
            "top_performers": sorted(
                agent_summary.items(),
                key=lambda x: x[1]["success_rate"],
                reverse=True,
            )[:5],
        }


_learning_system_instance: AdaptiveLearningSystem | None = None


async def get_learning_system() -> AdaptiveLearningSystem:
    global _learning_system_instance

    if _learning_system_instance is None:
        _learning_system_instance = AdaptiveLearningSystem()

    return _learning_system_instance
