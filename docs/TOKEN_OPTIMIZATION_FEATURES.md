# Token Optimization Features

This document describes the comprehensive token optimization system implemented in the session-mgmt-mcp server to reduce token usage and costs while maintaining functionality.

## Overview

The token optimization system provides multiple strategies to reduce token consumption in conversation search, memory retrieval, and response generation. It includes automatic optimization, intelligent chunking, and detailed usage tracking.

## Core Components

### 1. TokenOptimizer Class (`session_mgmt_mcp/token_optimizer.py`)

The main optimization engine that provides:

- **Token Counting**: Accurate token counting using tiktoken (GPT-4 encoding)
- **Multiple Optimization Strategies**: 5 different approaches to reduce token usage
- **Response Chunking**: Automatic splitting of large responses
- **Usage Tracking**: Comprehensive metrics and cost estimation
- **Cache Management**: Temporary storage for chunked responses

#### Optimization Strategies

1. **`truncate_old`**: Prioritizes recent conversations and truncates older content
1. **`summarize_content`**: Auto-summarizes long conversations while preserving key information
1. **`prioritize_recent`**: Scores conversations by recency, relevance, and technical content
1. **`filter_duplicates`**: Removes duplicate or very similar conversations
1. **`chunk_response`**: Splits large result sets into manageable chunks

### 2. MCP Tool Integration

Enhanced existing tools with token optimization:

#### Enhanced `reflect_on_past` Tool

New parameters:

- `optimize_tokens: bool = True` - Enable/disable optimization
- `max_tokens: int = 4000` - Maximum token limit for response

Features:

- Automatic optimization strategy selection
- Token savings reporting (e.g., "⚡ Token optimization: 30% saved")
- Usage tracking for analytics

#### New MCP Tools

1. **`get_cached_chunk`** - Retrieve paginated chunks from large result sets
1. **`get_token_usage_stats`** - View token usage metrics and cost savings
1. **`optimize_memory_usage`** - Consolidate old conversations to free memory

### 3. Status Reporting

The `status` tool now includes token optimization information:

```
⚡ Token Optimization:
• get_cached_chunk - Retrieve chunked response data
• get_token_usage_stats - Token usage and savings metrics
• optimize_memory_usage - Consolidate old conversations
• Built-in response chunking and truncation
• Last 24h savings: $0.0125 USD, 1,250 tokens
• Active cached chunks: 3
```

## Usage Examples

### Basic Optimization

```python
# Search with automatic optimization
result = await reflect_on_past(
    query="Python functions",
    optimize_tokens=True,  # Enable optimization
    max_tokens=2000,  # Token limit
)
```

### Chunked Responses

When responses are large, they're automatically chunked:

```python
# First request returns chunk 1 + cache_key
result = await reflect_on_past(query="large dataset", max_tokens=500)

# Retrieve additional chunks
chunk2 = await get_cached_chunk("cache_key_123", 2)
chunk3 = await get_cached_chunk("cache_key_123", 3)
```

### Usage Analytics

```python
# View token usage and savings
stats = await get_token_usage_stats(hours=24)
# Shows: requests, tokens used, optimizations applied, estimated cost savings
```

### Memory Optimization

```python
# Consolidate old conversations
result = await optimize_memory_usage(
    strategy="aggressive",  # Options: auto, aggressive, conservative
    max_age_days=30,  # Consolidate conversations older than 30 days
    dry_run=True,  # Preview changes without applying
)
```

## Token Savings Strategies

### 1. Content Truncation

- **Smart Truncation**: Preserves sentence boundaries when possible
- **Age-Based Priority**: Recent conversations get higher priority
- **Minimum Retention**: Always keeps at least 3 recent conversations

### 2. Content Summarization

- **Extractive Summarization**: Selects most important sentences
- **Template-Based**: Uses patterns to create structured summaries
- **Technical Content Preservation**: Prioritizes code, errors, and solutions

### 3. Response Chunking

- **Automatic Chunking**: Splits responses exceeding token limits
- **Intelligent Caching**: 1-hour cache with automatic cleanup
- **Pagination Support**: Easy navigation through large result sets

### 4. Duplicate Filtering

- **Content Hashing**: Identifies similar conversations
- **Normalized Comparison**: Handles whitespace and formatting differences
- **Preservation Logic**: Keeps most recent of duplicate conversations

### 5. Priority Scoring

Conversations are scored based on:

- **Recency** (0-0.5 points): Newer conversations score higher
- **Relevance** (0-0.3 points): Semantic similarity to query
- **Technical Content** (0-0.2 points): Presence of code, errors, functions
- **Length Penalty** (0 to -0.2 points): Very long content gets penalty

## Performance Characteristics

### Token Counting Performance

- **Small texts (100 chars)**: \<1ms
- **Medium texts (1,000 chars)**: \<5ms
- **Large texts (10,000 chars)**: \<50ms

### Optimization Strategy Performance

- **Truncation**: ~1ms per conversation
- **Prioritization**: ~2ms per conversation
- **Summarization**: ~10ms per conversation
- **Deduplication**: ~3ms per conversation

### Memory Usage

- **Base memory overhead**: ~5MB
- **Per 1,000 conversations**: ~2MB additional
- **Cache overhead**: ~1KB per cached chunk

## Configuration Options

### TokenOptimizer Initialization

```python
optimizer = TokenOptimizer(
    max_tokens=4000,  # Default token limit
    chunk_size=2000,  # Size of each chunk
)
```

### Retention Policies (Memory Optimization)

```python
policy = {
    "max_age_days": 365,  # Keep conversations for 1 year
    "max_conversations": 10000,  # Maximum total conversations
    "importance_threshold": 0.3,  # Minimum score to keep
    "consolidation_age_days": 30,  # Consolidate after 30 days
    "compression_ratio": 0.5,  # Target 50% size reduction
}
```

## Cost Savings

### Typical Savings by Strategy

- **Truncation**: 20-40% token reduction
- **Summarization**: 30-60% token reduction
- **Prioritization**: 15-35% token reduction
- **Deduplication**: 5-25% token reduction (depends on duplicate rate)
- **Combined**: 40-70% token reduction

### Cost Estimation

Based on GPT-4 pricing (~$0.01 per 1K tokens):

- **100 optimized requests/day**: ~$0.50-2.00 daily savings
- **1,000 optimized requests/day**: ~$5.00-20.00 daily savings
- **Annual savings**: $180-7,300 depending on usage

## Testing Coverage

### Unit Tests (`tests/unit/test_token_optimizer.py`)

- Token counting accuracy and performance
- All optimization strategies with various inputs
- Edge cases and error handling
- Cache operations and cleanup
- Usage metrics and statistics

### Integration Tests (`tests/integration/test_token_optimization_mcp.py`)

- MCP tool integration
- End-to-end optimization workflows
- Error handling and fallback behavior
- Async operation correctness

### Performance Tests (`tests/performance/test_token_optimization_performance.py`)

- Scalability with large datasets (1,000+ conversations)
- Memory usage efficiency
- Concurrent optimization performance
- Benchmarks across different dataset sizes

## Dependencies

### Required

- `tiktoken>=0.5.0` - Token counting
- `fastmcp>=2.0.0` - MCP server framework
- `duckdb>=0.9.0` - Conversation storage

### Optional (for advanced features)

- `psutil>=5.9.0` - Memory usage monitoring (testing)
- `onnxruntime` - Semantic search embeddings
- `transformers` - Text processing utilities

## Future Enhancements

### Planned Features

1. **Adaptive Optimization**: Learn from usage patterns to optimize strategy selection
1. **Real-time Cost Monitoring**: Live token usage dashboards
1. **Custom Summarization**: User-defined summary templates
1. **Compression Analytics**: Detailed breakdown of optimization effectiveness
1. **Smart Prefetching**: Predict and pre-optimize likely queries

### Integration Opportunities

- **Claude API Integration**: Direct token usage monitoring
- **Usage-based Billing**: Automatic cost tracking and alerts
- **Team Analytics**: Multi-user optimization reporting
- **CI/CD Integration**: Automated optimization in development workflows

## Security and Privacy

### Data Handling

- **No External Calls**: All optimization runs locally
- **Temporary Caching**: Chunks expire after 1 hour
- **Privacy Preservation**: No conversation data leaves the local system
- **Audit Trail**: Full logging of optimization operations

### Performance Monitoring

- **Non-intrusive**: Minimal performance impact (\<5ms overhead)
- **Optional Tracking**: Usage statistics can be disabled
- **Local Storage**: All metrics stored in local DuckDB database

______________________________________________________________________

## Quick Start

1. **Install dependencies**:

   ```bash
   uv add tiktoken
   ```

1. **Enable optimization in searches**:

   ```python
   result = await reflect_on_past("query", optimize_tokens=True)
   ```

1. **Monitor usage**:

   ```python
   stats = await get_token_usage_stats()
   ```

1. **Optimize memory**:

   ```python
   await optimize_memory_usage(dry_run=True)  # Preview first
   await optimize_memory_usage(dry_run=False)  # Apply changes
   ```

The token optimization system is designed to be transparent, efficient, and cost-effective while preserving the quality and usefulness of conversation search and memory features.
