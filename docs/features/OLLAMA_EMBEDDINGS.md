# Ollama Embeddings Integration

## Overview

Crackerjack now supports **Ollama** as an embedding backend, providing high-quality local embeddings on all platforms including macOS x86_64 where onnxruntime is not available.

## Problem Solved

**onnxruntime** stopped supporting macOS x86_64 after version 1.19.2, and that version doesn't have Python 3.13 wheels. This made it impossible to use modern ONNX-based embeddings on macOS Intel machines.

**Solution**: Ollama provides platform-agnostic embeddings via a local HTTP API, working seamlessly across all platforms and Python versions.

## Backend Options

Crackerjack's `EmbeddingService` supports three backends:

### 1. **onnxruntime** (Production)
- **Best for**: Production environments where available
- **Requirements**: onnxruntime package, Python 3.8-3.12 (for macOS x86_64)
- **Model**: Sentence Transformers models (e.g., `all-MiniLM-L6-v2`)
- **Performance**: Fast, CPU-based inference

### 2. **ollama** (Cross-platform Alternative)
- **Best for**: macOS x86_64, ARM64, Linux, Windows - anywhere onnxruntime isn't available
- **Requirements**: Ollama service running locally
- **Model**: Any Ollama embedding model (e.g., `nomic-embed-text`, `mxbai-embed-large`)
- **Performance**: Fast, local HTTP API
- **Setup**: See Ollama installation below

### 3. **fallback** (Last Resort)
- **Best for**: Development, testing, when no other backend is available
- **Requirements**: None
- **Method**: Hash-based embeddings (deterministic but not semantic)
- **Performance**: Instant, but no semantic similarity

## Auto-Detection Behavior

When `embedding_backend` is set to `"auto"` (default), the system follows this priority order:

```python
1. Try onnxruntime if available
2. Fall back to Ollama if service is running
3. Use hash-based fallback as last resort
```

## Configuration

### Via Python Code

```python
from crackerjack.models.semantic_models import SemanticConfig
from crackerjack.services.ai.embeddings import EmbeddingService

# Auto-detect (recommended)
config = SemanticConfig(embedding_backend="auto")

# Force specific backend
config = SemanticConfig(
    embedding_backend="ollama",
    embedding_model="nomic-embed-text",  # Ollama model
    ollama_base_url="http://localhost:11434"  # Default Ollama URL
)

service = EmbeddingService(config)
```

### Via Settings File

Add to `settings/crackerjack.yaml` or `settings/local.yaml`:

```yaml
semantic:
  embedding_backend: auto  # or "onnxruntime", "ollama", "fallback"
  embedding_model: nomic-embed-text  # Model name for your backend
  ollama_base_url: http://localhost:11434  # Ollama service URL
```

## Ollama Installation

### macOS (x86_64 and ARM64)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull an embedding model
ollama pull nomic-embed-text

# Verify it's running
curl http://localhost:11434/api/tags
```

### Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text
```

### Recommended Ollama Models

| Model | Dimensions | Size | Use Case |
|-------|------------|------|----------|
| `nomic-embed-text` | 768 | ~274MB | General purpose (recommended) |
| `mxbai-embed-large` | 1024 | ~670MB | Higher quality, larger |
| `all-minilm` | 384 | ~130MB | Fast, lightweight |

## Usage Examples

### Basic Usage

```python
from crackerjack.services.ai.embeddings import EmbeddingService
from crackerjack.models.semantic_models import SemanticConfig

# Auto-detect backend
config = SemanticConfig(embedding_backend="auto")
service = EmbeddingService(config)

# Check which backend is being used
info = service.get_model_info()
print(f"Backend: {info['backend']}")
print(f"Model: {info['model_name']}")
print(f"Loaded: {info['loaded']}")

# Generate embeddings
text = "Your code snippet here"
embedding = service.generate_embedding(text)
print(f"Embedding dimension: {len(embedding)}")
```

### Batch Embeddings

```python
texts = [
    "First code snippet",
    "Second code snippet",
    "Third code snippet"
]

embeddings = service.generate_embeddings_batch(texts)
print(f"Generated {len(embeddings)} embeddings")
```

### Similarity Calculation

```python
# Calculate cosine similarity between two embeddings
similarity = service.calculate_similarity(embedding1, embedding2)
print(f"Similarity: {similarity:.2%}")  # e.g., "Similarity: 87.45%"
```

## Troubleshooting

### Ollama Not Detected

**Problem**: System falls back to hash-based embeddings even though Ollama is installed.

**Solution**:
1. Verify Ollama is running: `curl http://localhost:11434/api/tags`
2. Check the service is accessible: `ollama list`
3. Review logs for connection errors

### 404 Error from Ollama

**Problem**: `HTTP Error 404: Not Found` when generating embeddings.

**Solution**:
1. Pull the embedding model: `ollama pull nomic-embed-text`
2. Verify model is available: `ollama list`
3. Check the model name matches in your config

### Wrong Embedding Dimension

**Problem**: Embedding dimensions don't match between different runs.

**Solution**:
- Ollama models have varying dimensions (check with `ollama list`)
- Configure `embedding_dimension` in `SemanticConfig` to match your model
- Use `get_model_info()` to see the actual dimension being used

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EmbeddingService                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  _determine_backend()                                         │
│       │                                                       │
│       ├── onnxruntime? ──Yes──> Use ONNX Runtime            │
│       │       No                                              │
│       ├── ollama running? ──Yes──> Use Ollama API           │
│       │       No                                              │
│       └──> Use fallback (hash-based)                         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Performance Comparison

| Backend | Initialization | First Embedding | Batch (10) | Quality |
|---------|---------------|-----------------|------------|---------|
| onnxruntime | ~2s | ~50ms | ~200ms | ★★★★★ |
| ollama | ~0s (lazy) | ~100ms | ~800ms | ★★★★☆ |
| fallback | ~0s | ~1ms | ~5ms | ★☆☆☆☆ |

## Migration Guide

### From ONNX Runtime to Ollama

1. **Install Ollama**:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull nomic-embed-text
   ```

2. **Update Configuration**:
   ```python
   # Before
   config = SemanticConfig(
       embedding_backend="onnxruntime",
       embedding_model="all-MiniLM-L6-v2"
   )

   # After
   config = SemanticConfig(
       embedding_backend="ollama",
       embedding_model="nomic-embed-text"
   )
   ```

3. **No Code Changes Required**: The API is identical across backends

## See Also

- [Ollama Documentation](https://ollama.com/)
- [Ollama Models Library](https://ollama.com/search)
- [Semantic Models Reference](../reference/SEMANTIC_MODELS.md)
