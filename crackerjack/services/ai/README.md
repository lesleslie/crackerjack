> Crackerjack Docs: [Main](../../../README.md) | [CLAUDE.md](../../../docs/guides/CLAUDE.md) | [Services](../README.md) | AI Services

# AI Services

AI provider integrations and service abstractions for intelligent code analysis, optimization, and contextual assistance.

## Overview

The AI services package provides intelligent automation capabilities powered by Claude and other AI providers. These services enhance crackerjack's ability to understand code context, generate intelligent recommendations, optimize workflows, and provide predictive analytics.

## Services

- **`contextual_ai_assistant.py`** - Context-aware AI recommendations based on project analysis
- **`intelligent_commit.py`** - AI-powered commit message generation
- **`embeddings.py`** - Vector embeddings for semantic code analysis
- **`predictive_analytics.py`** - Predictive quality trend analysis and forecasting
- **`advanced_optimizer.py`** - AI-driven code and workflow optimization

## Features

### Contextual AI Assistant

Analyzes your project context to provide intelligent, prioritized recommendations:

- **Project Analysis** - Detects project type, size, languages, and configuration
- **Smart Recommendations** - Prioritized suggestions based on current project state
- **Action Commands** - Executable commands to implement recommendations
- **Confidence Scoring** - AI confidence levels for each recommendation
- **Context Caching** - Caches project analysis for performance

### Intelligent Commit Messages

Generates meaningful commit messages from code changes:

- **Change Analysis** - Analyzes git diff to understand modifications
- **Semantic Understanding** - Recognizes refactoring, features, fixes, etc.
- **Convention Following** - Follows project commit message patterns
- **Multi-file Support** - Handles complex multi-file commits

### Embeddings & Semantic Search

Vector-based code analysis for semantic understanding:

- **Code Vectorization** - Converts code to semantic vectors
- **Similarity Detection** - Finds semantically similar code patterns
- **Intelligent Grouping** - Groups related functionality
- **Search Enhancement** - Improves code search beyond text matching

### Predictive Analytics

Forecasts quality trends and potential issues:

- **Coverage Trends** - Predicts coverage trajectory
- **Quality Degradation** - Detects early warning signs
- **Resource Forecasting** - Predicts resource needs
- **Risk Assessment** - Identifies high-risk code areas

### Advanced Optimizer

AI-driven optimization strategies:

- **Performance Analysis** - Identifies optimization opportunities
- **Resource Management** - Optimizes memory and CPU usage
- **Workflow Tuning** - Optimizes development workflow efficiency
- **Pattern Learning** - Learns from successful optimizations

## Usage Examples

### Contextual AI Assistant

```python
from crackerjack.services.ai import ContextualAIAssistant
from acb.depends import depends

assistant = depends.get(ContextualAIAssistant)

# Get top 5 recommendations for current project
recommendations = assistant.get_contextual_recommendations(max_recommendations=5)

for rec in recommendations:
    print(f"[{rec.priority}] {rec.title}")
    print(f"  {rec.description}")
    if rec.action_command:
        print(f"  Run: {rec.action_command}")
    print(f"  Confidence: {rec.confidence:.0%}")
```

### Intelligent Commit Messages

```python
from crackerjack.services.ai import IntelligentCommitService
from acb.depends import depends

commit_service = depends.get(IntelligentCommitService)

# Generate commit message from staged changes
message = await commit_service.generate_commit_message()

# Or analyze specific files
message = await commit_service.generate_commit_message(
    files=["src/main.py", "tests/test_main.py"]
)

print(f"Suggested commit message:\n{message}")
```

### Embeddings for Code Analysis

```python
from crackerjack.services.ai import EmbeddingService
from acb.depends import depends

embedding_service = depends.get(EmbeddingService)

# Generate embedding for code snippet
code = """
def calculate_total(items):
    return sum(item.price for item in items)
"""

embedding = await embedding_service.embed_code(code)

# Find similar code
similar_snippets = await embedding_service.find_similar_code(embedding, threshold=0.85)
```

### Predictive Analytics

```python
from crackerjack.services.ai import PredictiveAnalytics
from acb.depends import depends

analytics = depends.get(PredictiveAnalytics)

# Predict coverage trend
prediction = await analytics.predict_coverage_trend(
    historical_data=[19.6, 20.1, 20.8, 21.6], days_ahead=30
)

print(f"Predicted coverage in 30 days: {prediction.coverage:.1%}")
print(f"Confidence: {prediction.confidence:.0%}")
print(f"Trend: {prediction.trend}")  # 'improving', 'stable', 'degrading'
```

### Advanced Optimizer

```python
from crackerjack.services.ai import AdvancedOptimizer
from acb.depends import depends

optimizer = depends.get(AdvancedOptimizer)

# Analyze and optimize workflow
optimization = await optimizer.optimize_workflow()

for suggestion in optimization.suggestions:
    print(f"Optimization: {suggestion.title}")
    print(f"  Impact: {suggestion.impact}")
    print(f"  Effort: {suggestion.effort}")
    print(f"  ROI: {suggestion.roi:.1f}x")
```

## Architecture

### AI Provider Integration

All AI services follow the provider abstraction pattern:

```python
from acb.depends import depends, Inject
from crackerjack.models.protocols import Console


class AIServiceBase:
    @depends.inject
    def __init__(
        self,
        console: Inject[Console] = None,
    ) -> None:
        self.console = console
        self.provider = self._get_ai_provider()

    def _get_ai_provider(self):
        # Returns configured AI provider (Claude, OpenAI, etc.)
        pass
```

### Context-Aware Design

AI services analyze project context to provide relevant recommendations:

1. **Project Detection** - Identifies project type, dependencies, and configuration
1. **State Analysis** - Analyzes current quality metrics and trends
1. **Pattern Recognition** - Recognizes code patterns and anti-patterns
1. **Recommendation Generation** - Generates prioritized, actionable recommendations
1. **Confidence Scoring** - Assigns confidence levels to recommendations

## Configuration

AI services are configured through ACB Settings:

```yaml
# settings/crackerjack.yaml
ai_enabled: true
ai_provider: "claude"  # claude, openai, local
ai_model: "claude-3-sonnet"
ai_context_cache_ttl: 3600  # seconds

# Contextual assistant settings
ai_max_recommendations: 5
ai_min_confidence: 0.7

# Embeddings settings
embedding_model: "text-embedding-3-small"
embedding_dimension: 1536
```

## Integration with Agent System

AI services integrate with crackerjack's 12 specialized agents:

- **RefactoringAgent** - Uses AI for intelligent refactoring suggestions
- **SemanticAgent** - Leverages embeddings for semantic analysis
- **EnhancedProactiveAgent** - Uses predictive analytics for prevention
- **ArchitectAgent** - Uses AI for architectural recommendations

See [Intelligence](../../intelligence/README.md) for agent system details.

## Security & Privacy

### Data Handling

- **No Code Upload** - Code analysis happens locally when possible
- **Privacy-First** - Sensitive data filtered before AI processing
- **Opt-In Required** - AI features require explicit enablement
- **Cache Control** - Local caching of AI responses for privacy

### API Key Management

```python
# Use environment variables for API keys
import os

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Never hardcode API keys in code or configuration files
```

## Performance Considerations

### Caching Strategy

AI services implement intelligent caching:

- **Context Cache** - Project analysis cached for 1 hour by default
- **Embedding Cache** - Code embeddings cached indefinitely (invalidated on change)
- **Response Cache** - AI responses cached for identical inputs
- **TTL Configuration** - Configurable cache time-to-live

### Rate Limiting

```python
from crackerjack.services.ai import AIRateLimiter

# Automatic rate limiting to prevent API throttling
limiter = AIRateLimiter(requests_per_minute=60)
await limiter.acquire()
```

## Best Practices

1. **Enable Selectively** - Enable AI features only where valuable
1. **Monitor Usage** - Track API usage and costs
1. **Cache Aggressively** - Leverage caching to minimize API calls
1. **Validate Recommendations** - Always review AI recommendations before applying
1. **Set Confidence Thresholds** - Filter low-confidence recommendations
1. **Use Batch Operations** - Batch similar operations to reduce API calls
1. **Handle Failures Gracefully** - Implement fallbacks when AI unavailable

## Related

- [Intelligence](../../intelligence/README.md) - Agent orchestration and selection

- [Services](../README.md) - Parent services documentation

- [CLAUDE.md](../../../docs/guides/CLAUDE.md) - AI agent system overview

## Future Enhancements

- [ ] Support for additional AI providers (Gemini, local LLMs)
- [ ] Fine-tuned models for code-specific tasks
- [ ] Improved embedding models for better semantic understanding
- [ ] Real-time code analysis with streaming responses
- [ ] Multi-modal analysis (code + documentation + tests)
- [ ] Agent-to-agent communication for complex tasks
