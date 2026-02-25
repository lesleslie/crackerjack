from __future__ import annotations
import logging
import typing as t
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
if t.TYPE_CHECKING:
    from collections.abc import Callable
logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class WorkflowPattern:
    pattern_id: str
    pattern_name: str
    description: str
    frequency: int
    confidence: float
    examples: list[dict[str, t.Any]]
    semantic_tags: list[str] = field(default_factory=list)
    first_seen: datetime | None = None
    last_seen: datetime | None = None

    def to_searchable_text(self) -> str:
        parts = [f'Pattern: {self.pattern_name}', f'Description: {self.description}', f'Frequency: {self.frequency} occurrences', f'Confidence: {self.confidence:.2%}']
        if self.semantic_tags:
            parts.append(f"Tags: {', '.join(self.semantic_tags)}")
        return '. '.join(parts)

@dataclass(frozen=True)
class PracticeRecommendation:
    recommendation_type: str
    title: str
    description: str
    priority: int
    evidence: list[dict[str, t.Any]]
    actionable_steps: list[str]
    potential_impact: str
    metric_baseline: dict[str, t.Any] | None = None

    def to_searchable_text(self) -> str:
        parts = [f'Recommendation: {self.title}', f'Type: {self.recommendation_type}', f'Priority: {self.priority}/5', f'Description: {self.description}', f'Impact: {self.potential_impact}']
        if self.actionable_steps:
            steps = '; '.join(self.actionable_steps[:3])
            parts.append(f'Steps: {steps}')
        return '. '.join(parts)

@dataclass
class GitSemanticSearchConfig:
    embedding_model: str = 'sentence-transformers/all-MiniLM-L6-v2'
    chunk_size: int = 512
    embedding_dimension: int = 384
    similarity_threshold: float = 0.6
    max_results: int = 20
    auto_index: bool = True
    index_interval_hours: int = 24

class GitSemanticSearch:

    def __init__(self, repo_path: str, config: GitSemanticSearchConfig | None=None, git_collector_factory: Callable[..., t.Any] | None=None, akosha_integration_factory: Callable[..., t.Any] | None=None) -> None:
        from pathlib import Path
        self.repo_path = Path(repo_path).resolve()
        self.config = config or GitSemanticSearchConfig()
        if not (self.repo_path / '.git').exists():
            raise ValueError(f'Not a git repository: {self.repo_path}')
        self._git_collector: t.Any | None = None
        self._akosha_integration: t.Any | None = None
        self._indexed_days: int = 0
        self._git_collector_factory = git_collector_factory
        self._akosha_integration_factory = akosha_integration_factory
        logger.info(f'GitSemanticSearch initialized for {self.repo_path}')

    def _get_git_collector(self) -> t.Any:
        if self._git_collector is None:
            from crackerjack.memory.git_metrics_collector import GitMetricsCollector
            from crackerjack.services.subprocess import get_subprocess_executor
            executor = get_subprocess_executor()
            if self._git_collector_factory:
                self._git_collector = self._git_collector_factory(self.repo_path, executor)
            else:
                self._git_collector = GitMetricsCollector(repo_path=self.repo_path, executor=executor)
        return self._git_collector

    def _get_akosha_integration(self) -> t.Any:
        if self._akosha_integration is None:
            from crackerjack.integration.akosha_integration import create_akosha_git_integration
            if self._akosha_integration_factory:
                self._akosha_integration = self._akosha_integration_factory(repo_path=self.repo_path)
            else:
                self._akosha_integration = create_akosha_git_integration(repo_path=self.repo_path, backend='auto')
        return self._akosha_integration

    async def search_git_history(self, query: str, limit: int=10, days_back: int=30) -> dict[str, t.Any]:
        try:
            await self._ensure_index(days_back)
            akosha = self._get_akosha_integration()
            events = await akosha.search_git_history(query=query, limit=limit)
            results = [{'commit_hash': evt.commit_hash, 'message': evt.message, 'author': evt.author_name, 'timestamp': evt.timestamp.isoformat(), 'event_type': evt.event_type, 'semantic_tags': evt.semantic_tags, 'metadata': evt.metadata} for evt in events]
            return {'success': True, 'query': query, 'results_count': len(results), 'days_searched': days_back, 'repository': str(self.repo_path), 'results': results}
        except Exception as e:
            logger.error(f'Failed to search git history: {e}')
            return {'success': False, 'error': str(e), 'query': query, 'results': []}

    async def find_workflow_patterns(self, pattern_description: str, days_back: int=90, min_frequency: int=3) -> dict[str, t.Any]:
        try:
            await self._ensure_index(days_back)
            akosha = self._get_akosha_integration()
            events = await akosha.search_git_history(query=pattern_description, limit=100)
            if not events:
                return {'success': True, 'patterns': [], 'message': 'No matching commits found for pattern description'}
            patterns = self._analyze_patterns(events=events, pattern_description=pattern_description, min_frequency=min_frequency)
            formatted_patterns = [{'pattern_id': p.pattern_id, 'pattern_name': p.pattern_name, 'description': p.description, 'frequency': p.frequency, 'confidence': p.confidence, 'semantic_tags': p.semantic_tags, 'first_seen': p.first_seen.isoformat() if p.first_seen else None, 'last_seen': p.last_seen.isoformat() if p.last_seen else None, 'example_count': len(p.examples), 'examples': p.examples[:3]} for p in patterns]
            return {'success': True, 'pattern_description': pattern_description, 'patterns_found': len(formatted_patterns), 'days_analyzed': days_back, 'min_frequency': min_frequency, 'patterns': formatted_patterns}
        except Exception as e:
            logger.error(f'Failed to find workflow patterns: {e}')
            return {'success': False, 'error': str(e), 'patterns': []}

    async def recommend_git_practices(self, focus_area: str='general', days_back: int=60) -> dict[str, t.Any]:
        try:
            collector = self._get_git_collector()
            dashboard = collector.get_velocity_dashboard(days_back=days_back)
            recommendations = self._generate_recommendations(dashboard=dashboard, focus_area=focus_area, days_back=days_back)
            formatted_recommendations = [{'type': r.recommendation_type, 'title': r.title, 'description': r.description, 'priority': r.priority, 'potential_impact': r.potential_impact, 'actionable_steps': r.actionable_steps, 'evidence_count': len(r.evidence), 'metric_baseline': r.metric_baseline} for r in recommendations]
            formatted_recommendations.sort(key=operator.itemgetter("priority"), reverse=True)
            return {'success': True, 'focus_area': focus_area, 'days_analyzed': days_back, 'recommendations_count': len(formatted_recommendations), 'repository': str(self.repo_path), 'recommendations': formatted_recommendations}
        except Exception as e:
            logger.error(f'Failed to recommend git practices: {e}')
            return {'success': False, 'error': str(e), 'recommendations': []}

    async def _ensure_index(self, days_back: int) -> None:
        try:
            akosha = self._get_akosha_integration()
            await akosha.initialize()
            if self.config.auto_index and days_back > self._indexed_days:
                indexed = await akosha.index_repository_history(days_back=days_back)
                self._indexed_days = days_back
                logger.info(f'Indexed {indexed} commits for semantic search')
        except Exception as e:
            logger.warning(f'Failed to ensure index: {e}')

    def _analyze_patterns(self, events: list[t.Any], pattern_description: str, min_frequency: int) -> list[WorkflowPattern]:
        patterns: list[WorkflowPattern] = []
        if not events:
            return patterns
        semantic_groups = self._cluster_by_semantics(events)
        for group_id, group_events in semantic_groups.items():
            if len(group_events) < min_frequency:
                continue
            pattern = self._create_pattern_from_cluster(group_id=group_id, events=group_events, pattern_description=pattern_description)
            if pattern:
                patterns.append(pattern)
        patterns.sort(key=lambda p: (p.frequency, p.confidence), reverse=True)
        return patterns[:10]

    def _cluster_by_semantics(self, events: list[t.Any]) -> dict[str, list[t.Any]]:
        groups: dict[str, list[t.Any]] = {}
        for event in events:
            conv_type = event.metadata.get('conventional_type', 'other')
            cluster_key = f'type:{conv_type}'
            if cluster_key not in groups:
                groups[cluster_key] = []
            groups[cluster_key].append(event)
        return groups

    def _create_pattern_from_cluster(self, group_id: str, events: list[t.Any], pattern_description: str) -> WorkflowPattern | None:
        if not events:
            return None
        freq = len(events)
        timestamps = [e.timestamp if hasattr(e, 'timestamp') else datetime.now() for e in events]
        first_seen = min(timestamps) if timestamps else None
        last_seen = max(timestamps) if timestamps else None
        all_tags: list[str] = []
        for e in events:
            if hasattr(e, 'semantic_tags'):
                all_tags.extend(e.semantic_tags)
        tag_counter = Counter(all_tags)
        top_tags = [tag for tag, _ in tag_counter.most_common(5)]
        pattern_name = group_id.replace('type:', '').title() + ' Pattern'
        if pattern_name == 'Other Pattern':
            pattern_name = 'Recurring Activity Pattern'
        examples = [{'commit_hash': e.commit_hash, 'message': e.message, 'author': e.author_name, 'timestamp': e.timestamp.isoformat() if hasattr(e, 'timestamp') else None} for e in events[:5]]
        confidence = min(freq / 10.0, 1.0)
        return WorkflowPattern(pattern_id=f'pattern-{group_id}-{freq}', pattern_name=pattern_name, description=f'Recurring {pattern_name} detected in repository history', frequency=freq, confidence=confidence, examples=examples, semantic_tags=top_tags, first_seen=first_seen, last_seen=last_seen)

    def _generate_recommendations(self, dashboard: t.Any, focus_area: str, days_back: int) -> list[PracticeRecommendation]:
        recommendations: list[PracticeRecommendation] = []
        commit_metrics = dashboard.commit_metrics
        merge_metrics = dashboard.merge_metrics
        if commit_metrics.conventional_compliance_rate < 0.7:
            recommendations.append(PracticeRecommendation(recommendation_type='commit_quality', title='Improve Conventional Commit Adoption', description=f'Only {commit_metrics.conventional_compliance_rate:.1%} of commits follow conventional commit format. Standardizing commit messages improves searchability and automation.', priority=4, evidence=[], actionable_steps=['Add commitlint or commitizen to project', 'Create commit message template in CONTRIBUTING.md', 'Enable commit message hook for validation', 'Train team on conventional commits format'], potential_impact='Improved changelog generation, better semantic search, easier release automation', metric_baseline={'current_compliance': f'{commit_metrics.conventional_compliance_rate:.1%}', 'target_compliance': '80%'}))
        if merge_metrics.conflict_rate > 0.2:
            recommendations.append(PracticeRecommendation(recommendation_type='workflow', title='Reduce Merge Conflicts', description=f'Merge conflict rate is {merge_metrics.conflict_rate:.1%}, indicating potential workflow issues. Frequent conflicts slow development and increase risk.', priority=5, evidence=[{'conflict_rate': f'{merge_metrics.conflict_rate:.1%}', 'total_conflicts': merge_metrics.total_conflicts}], actionable_steps=['Implement trunk-based development or short-lived branches', 'Require pull request reviews before merge', 'Use feature flags instead of long-lived branches', 'Improve communication about concurrent changes', 'Consider smaller, more frequent integrations'], potential_impact='Faster integration, reduced risk, improved team velocity', metric_baseline={'current_conflict_rate': f'{merge_metrics.conflict_rate:.1%}', 'target_conflict_rate': '10%'}))
        if commit_metrics.breaking_changes > 3:
            recommendations.append(PracticeRecommendation(recommendation_type='quality', title='Reduce Breaking Changes', description=f'{commit_metrics.breaking_changes} breaking changes detected in {days_back} days. Breaking changes increase integration cost and risk.', priority=3, evidence=[{'breaking_changes': commit_metrics.breaking_changes, 'period_days': days_back}], actionable_steps=['Use semantic versioning for API changes', 'Implement deprecation warnings before removal', 'Design APIs with extension points', 'Document breaking changes thoroughly', 'Consider backward compatibility by default'], potential_impact='Smoother upgrades, better developer experience, reduced integration risk', metric_baseline={'breaking_changes': commit_metrics.breaking_changes, 'target_rate': '<3 per period'}))
        if commit_metrics.avg_commits_per_day < 5 and focus_area in ('general', 'velocity'):
            recommendations.append(PracticeRecommendation(recommendation_type='velocity', title='Increase Development Velocity', description=f'Average of {commit_metrics.avg_commits_per_day:.1f} commits/day may indicate bottlenecks or oversized commits.', priority=2, evidence=[{'avg_commits_per_day': f'{commit_metrics.avg_commits_per_day:.1f}', 'total_commits': commit_metrics.total_commits}], actionable_steps=['Break work into smaller, atomic commits', 'Review CI/CD pipeline for bottlenecks', 'Enable more frequent integration', 'Consider pair programming for faster feedback'], potential_impact='Faster feedback loops, easier code review, reduced integration risk', metric_baseline={'current_velocity': f'{commit_metrics.avg_commits_per_day:.1f}/day', 'target_velocity': '5-10/day'}))
        if focus_area == 'branching':
            branch_metrics = dashboard.branch_metrics
            if branch_metrics.most_switched_branch:
                recommendations.append(PracticeRecommendation(recommendation_type='branching', title='Optimize Branch Strategy', description=f"Branch '{branch_metrics.most_switched_branch}' has highest switching frequency. Consider reviewing branching strategy.", priority=3, evidence=[{'total_branches': branch_metrics.total_branches, 'active_branches': branch_metrics.active_branches}], actionable_steps=['Consider trunk-based development', 'Implement feature branch lifetime limits', 'Automate branch cleanup', 'Document branching strategy in team guidelines'], potential_impact='Simplified workflow, reduced context switching, faster delivery', metric_baseline={'total_branches': branch_metrics.total_branches, 'active_branches': branch_metrics.active_branches}))
        return recommendations

    def close(self) -> None:
        if self._git_collector:
            self._git_collector.close()

def create_git_semantic_search(repo_path: str, config: GitSemanticSearchConfig | None=None) -> GitSemanticSearch:
    return GitSemanticSearch(repo_path=repo_path, config=config)