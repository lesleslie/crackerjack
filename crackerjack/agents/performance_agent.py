import time
import typing as t
from pathlib import Path

from .base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)
from .helpers.performance.performance_ast_analyzer import PerformanceASTAnalyzer
from .helpers.performance.performance_pattern_detector import PerformancePatternDetector
from .helpers.performance.performance_recommender import PerformanceRecommender
from .semantic_helpers import (
    SemanticInsight,
    create_semantic_enhancer,
    get_session_enhanced_recommendations,
)


class PerformanceAgent(SubAgent):
    """Agent for detecting and fixing performance issues.

    Enhanced with semantic context to detect performance patterns across
    the codebase and find similar bottlenecks that may not be immediately visible.
    """

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.semantic_enhancer = create_semantic_enhancer(context.project_path)
        self.semantic_insights: dict[str, SemanticInsight] = {}
        self.performance_metrics: dict[str, t.Any] = {}

        # Initialize helper modules
        self._pattern_detector = PerformancePatternDetector(context)
        self._ast_analyzer = PerformanceASTAnalyzer(context)
        self._recommender = PerformanceRecommender(context)

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.PERFORMANCE}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type != IssueType.PERFORMANCE:
            return 0.0

        confidence = 0.85
        message_lower = issue.message.lower()

        if any(
            pattern in message_lower
            for pattern in (
                "nested loop",
                "o(n²)",
                "string concatenation",
                "list[t.Any] concatenation",
                "inefficient",
                "complexity",
            )
        ):
            confidence = 0.9

        return confidence

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Analyzing performance issue: {issue.message}")
        start_time = time.time()

        validation_result = self._validate_performance_issue(issue)
        if validation_result:
            return validation_result

        if issue.file_path is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided for performance issue"],
            )

        file_path = Path(issue.file_path)

        try:
            result = await self._process_performance_optimization(file_path)

            analysis_time = time.time() - start_time
            self.performance_metrics[str(file_path)] = {
                "analysis_duration": analysis_time,
                "optimizations_applied": result.fixes_applied,
                "timestamp": time.time(),
            }

            if result.success and result.fixes_applied:
                stats_summary = self._generate_optimization_summary()
                result.recommendations = result.recommendations + [stats_summary]

            return result
        except Exception as e:
            return self._create_performance_error_result(e)

    @staticmethod
    def _validate_performance_issue(issue: Issue) -> FixResult | None:
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path specified for performance issue"],
            )

        file_path = Path(issue.file_path)
        if not file_path.exists():
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"File not found: {file_path}"],
            )

        return None

    async def _process_performance_optimization(self, file_path: Path) -> FixResult:
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {file_path}"],
            )

        # Detect traditional performance issues using helper
        performance_issues = self._pattern_detector.detect_performance_issues(
            content, file_path
        )

        # Enhance with semantic performance pattern detection
        semantic_issues = await self._detect_semantic_performance_issues(
            content, file_path
        )
        performance_issues.extend(semantic_issues)

        if not performance_issues:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=["No performance issues detected"],
            )

        return await self._apply_and_save_optimizations(
            file_path,
            content,
            performance_issues,
        )

    async def _apply_and_save_optimizations(
        self,
        file_path: Path,
        content: str,
        issues: list[dict[str, t.Any]],
    ) -> FixResult:
        # Delegate to recommender helper
        optimized_content = self._recommender.apply_performance_optimizations(
            content, issues
        )

        if optimized_content == content:
            return self._create_no_optimization_result()

        success = self.context.write_file_content(file_path, optimized_content)
        if not success:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to write optimized file: {file_path}"],
            )

        # Get summary from recommender
        stats_summary = self._recommender.generate_optimization_summary()

        return FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=[
                f"Optimized {len(issues)} performance issues",
                "Applied algorithmic improvements",
                stats_summary,
            ],
            files_modified=[str(file_path)],
            recommendations=await self._generate_enhanced_recommendations(issues),
        )

    @staticmethod
    def _create_no_optimization_result() -> FixResult:
        return FixResult(
            success=False,
            confidence=0.6,
            remaining_issues=["Could not automatically optimize performance"],
            recommendations=[
                "Manual optimization required",
                "Consider algorithm complexity improvements",
                "Review data structure choices",
                "Profile code execution for bottlenecks",
            ],
        )

    @staticmethod
    def _create_performance_error_result(error: Exception) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Error processing file: {error}"],
        )

    async def _detect_semantic_performance_issues(
        self, content: str, file_path: Path
    ) -> list[dict[str, t.Any]]:
        """Detect performance issues using semantic analysis of similar code patterns."""
        issues = []

        try:
            # Delegate to AST analyzer helper
            critical_functions = (
                self._ast_analyzer.extract_performance_critical_functions(content)
            )

            for func in critical_functions:
                if (
                    func["estimated_complexity"] > 2
                ):  # Focus on potentially complex functions
                    # Search for similar performance patterns
                    insight = await self.semantic_enhancer.find_similar_patterns(
                        f"performance {func['signature']} {func['body_sample']}",
                        current_file=file_path,
                        min_similarity=0.6,
                        max_results=8,
                    )

                    if insight.total_matches > 1:
                        # Delegate analysis to AST analyzer helper
                        analysis = self._ast_analyzer.analyze_performance_patterns(
                            insight, func
                        )
                        if analysis["issues_found"]:
                            issues.append(
                                {
                                    "type": "semantic_performance_pattern",
                                    "function": func,
                                    "similar_patterns": insight.related_patterns,
                                    "performance_analysis": analysis,
                                    "confidence_score": insight.high_confidence_matches
                                    / max(insight.total_matches, 1),
                                    "suggestion": analysis["optimization_suggestion"],
                                }
                            )

                            # Store insight for recommendation enhancement
                            self.semantic_insights[func["name"]] = insight

        except Exception as e:
            self.log(f"Warning: Semantic performance analysis failed: {e}")

        return issues

    def _generate_optimization_summary(self) -> str:
        """Generate a summary of optimization results."""
        total_files = len(self.performance_metrics)
        total_optimizations = sum(
            metrics.get("optimizations_applied", 0)
            for metrics in self.performance_metrics.values()
        )

        total_time = sum(
            metrics.get("analysis_duration", 0)
            for metrics in self.performance_metrics.values()
        )

        return (
            f"Performance optimization summary: "
            f"{total_optimizations} optimizations applied across {total_files} files "
            f"in {total_time:.2f}s total"
        )

    async def _generate_enhanced_recommendations(
        self, issues: list[dict[str, t.Any]]
    ) -> list[str]:
        """Generate enhanced recommendations including semantic insights."""
        recommendations = ["Test performance improvements with benchmarks"]

        # Add semantic insights
        semantic_issues = [
            issue for issue in issues if issue["type"] == "semantic_performance_pattern"
        ]
        if semantic_issues:
            recommendations.append(
                f"Semantic analysis found {len(semantic_issues)} similar performance patterns "
                "across codebase - consider applying optimizations consistently"
            )

            # Store insights for session continuity
            for issue in semantic_issues:
                if "semantic_insight" in issue:
                    await self.semantic_enhancer.store_insight_to_session(
                        issue["semantic_insight"], "PerformanceAgent"
                    )

        # Enhance with session-stored insights
        recommendations = await get_session_enhanced_recommendations(
            recommendations, "PerformanceAgent", self.context.project_path
        )

        # Add insights from stored semantic analysis
        for func_name, insight in self.semantic_insights.items():
            if insight.high_confidence_matches > 0:
                enhanced_recs = self.semantic_enhancer.enhance_recommendations(
                    [],  # Start with empty list to get just semantic recommendations
                    insight,
                )
                recommendations.extend(enhanced_recs)

                # Log semantic context for debugging
                summary = self.semantic_enhancer.get_semantic_context_summary(insight)
                self.log(f"Performance semantic context for {func_name}: {summary}")

        return recommendations


agent_registry.register(PerformanceAgent)
