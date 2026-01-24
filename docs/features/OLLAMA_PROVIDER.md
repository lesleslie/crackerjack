# Ollama Provider for Crackerjack

## Overview

[Ollama](https://ollama.com/) enables **local execution** of AI models for crackerjack's code fixing features, providing:

- **Zero cost**: No API fees, run on your own hardware
- **Complete privacy**: Code never leaves your machine
- **Offline capability**: Works without internet connection
- **Open-source models**: Qwen2.5-Coder, DeepSeek-Coder, and more

## Quick Start

### Step 1: Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
ollama serve
```

### Step 2: Pull Qwen Model

```bash
# Download Qwen 2.5 Coder (7B parameters)
ollama pull qwen2.5-coder:7b

# Or use larger model (14B parameters, more RAM)
ollama pull qwen2.5-coder:14b
```

### Step 3: Configure Crackerjack

```bash
# Set provider to ollama
export AI_PROVIDER=ollama

# Run crackerjack
python -m crackerjack run --ai-fix
```

## Configuration Options

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AI_PROVIDER` | Yes | - | Must be set to `ollama` |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | No | `qwen2.5-coder:7b` | Model to use |
| `OLLAMA_TIMEOUT` | No | `300` | Request timeout in seconds |

### Settings File

`settings/local.yaml`:

```yaml
ai:
  ai_provider: ollama

ollama_base_url: http://localhost:11434
ollama_model: qwen2.5-coder:7b
ollama_timeout: 300
```

## Available Models

| Model | Parameters | RAM Required | Speed | Quality |
|-------|-----------|--------------|-------|----------|
| **qwen2.5-coder:7b** | 7B | ~8GB | Fast | Good for most fixes |
| qwen2.5-coder:14b | 14B | ~16GB | Medium | Better for complex issues |
| qwen2.5:7b | 7B | ~8GB | Fast | General purpose |
| qwen2.5:14b | 14B | ~16GB | Medium | General purpose |
| deepseek-coder:6.7b | 6.7B | ~8GB | Fast | Code completion focused |

**Recommendation**: Use `qwen2.5-coder:7b` for code fixing tasks.

## Model Installation

```bash
# List available models
ollama list

# Pull a model
ollama pull qwen2.5-coder:7b

# Show model info
ollama show qwen2.5-coder:7b
```

## Usage Examples

### Basic Usage

```bash
# Start Ollama (if not running)
ollama serve

# Set provider
export AI_PROVIDER=ollama

# Run crackerjack
python -m crackerjack run --ai-fix
```

### With Specific Model

```bash
export AI_PROVIDER=ollama
export OLLAMA_MODEL=qwen2.5-coder:14b
python -m crackerjack run --ai-fix
```

### With Tests

```bash
export AI_PROVIDER=ollama
python -m crackerjack run --ai-fix --run-tests
```

### Interactive Selection

```bash
# Launch interactive menu
python -m crackerjack run --select-provider

# Select "Ollama (Local)" from menu
# Follow prompts to test connection
# Settings saved automatically
```

## Architecture

### Local Execution Flow

```
┌─────────────────────┐
│  Crackerjack Hooks    │
│  (code quality checks) │
└──────────┬──────────────┘
           │
           ↓
┌─────────────────────┐
│  AI Code Fixer        │
│  (OllamaCodeFixer)   │
└──────────┬──────────────┘
           │
           ↓
┌─────────────────────┐
│  Ollama API          │
│  (localhost:11434)  │
└──────────┬──────────────┘
           │
           ↓
┌─────────────────────┐
│  Local Model         │
│  (qwen2.5-coder:7b)  │
└─────────────────────┘
```

### No API Transmission

- ✅ Code stays on your machine
- ✅ No network calls to external services
- ✅ Works in air-gapped environments
- ✅ Suitable for sensitive codebases

## Performance

### Typical Performance

| Hardware | Model | Time per Fix | Quality |
|----------|-------|--------------|---------|
| M1/M2 MacBook (8 cores) | qwen2.5-coder:7b | ~30s | Good |
| M1/M2 MacBook (16GB RAM) | qwen2.5-coder:14b | ~45s | Better |
| Desktop (32GB RAM) | qwen2.5-coder:14b | ~40s | Better |

**Note**: Local models are typically 2-3x slower than cloud APIs, but offer better privacy and zero cost.

### Optimization Tips

1. **Use smaller models** for simple fixes (7B)
1. **Use larger models** only for complex issues (14B)
1. **Ensure sufficient RAM** (model size × 2)
1. **Use SSD** for model storage (faster loading)

## Troubleshooting

### Ollama Not Running

**Problem**: `Connection refused` error

**Solution**:

```bash
# Check if Ollama is running
ps aux | grep ollama

# Start Ollama if not running
ollama serve
```

### Model Not Found

**Problem**: `model not found` error

**Solution**:

```bash
# List available models
ollama list

# Pull the model
ollama pull qwen2.5-coder:7b
```

### Slow Performance

**Problem**: Fixes taking too long

**Solutions**:

1. Use smaller model (7B instead of 14B)
1. Check available RAM: `vm_stat` (macOS) or `free -h` (Linux)
1. Close other applications
1. Ensure model is in memory (first call loads model)

### Out of Memory

**Problem**: `Out of memory` error

**Solutions**:

1. Use smaller model
1. Reduce max_tokens in settings
1. Close other applications
1. Add more RAM to system

## Comparison: Ollama vs Cloud Providers

| Feature | Ollama | Claude | Qwen |
|---------|--------|-------|------|
| **Cost** | Free (after hardware) | High | Low |
| **Privacy** | 100% local | Cloud processing | Cloud processing |
| **Speed** | Medium | Fast | Fast |
| **Quality** | Good | Best | Good |
| **Reliability** | Depends on hardware | High | High |
| **Setup** | Install Ollama | API key | API key |
| **Offline** | Yes | No | No |

## Best Practices

### 1. Model Selection

- **Simple formatting issues**: qwen2.5:7b (faster)
- **Code logic fixes**: qwen2.5-coder:7b (recommended)
- **Complex refactoring**: qwen2.5-coder:14b (better quality)

### 2. Resource Management

- Keep Ollama running: `ollama serve &`
- Monitor RAM usage: `activity monitor` or `htop`
- Unload unused models: `ollama stop <model>`

### 3. Testing

- Test with small codebase first
- Monitor quality of fixes
- Adjust confidence threshold if needed
- Have backup plan (cloud provider)

### 4. Production Use

- Use dedicated machine if possible
- Ensure stable power (desktop, not laptop)
- Monitor for overheating
- Set up automatic restart of Ollama service

## Integration with CI/CD

### GitHub Actions

```yaml
name: Crackerjack with Ollama

on: [push, pull_request]

jobs:
  code-fixing:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Install Ollama
        run: |
          curl -fsSL https://ollama.com/install.sh | sh
          ollama serve &
          ollama pull qwen2.5-coder:7b

      - name: Install Python
        uses: actions/setup-python@v3
        with:
          python-version: '3.13'

      - name: Install crackerjack
        run: |
          pip install crackerjack

      - name: Run crackerjack with Ollama
        env:
          AI_PROVIDER: ollama
          OLLAMA_MODEL: qwen2.5-coder:7b
        run: |
          python -m crackerjack run --ai-fix
```

### Local Development

```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Run crackerjack
export AI_PROVIDER=ollama
python -m crackerjack run --ai-fix
```

## FAQ

### Q: Can I use Ollama and cloud providers together?

A: Yes! You can switch between providers using:

```bash
# Use Ollama for local development
python -m crackerjack run --ai-fix --ai-provider ollama

# Use Claude for production
python -m crackerjack run --ai-fix --ai-provider claude
```

### Q: How much RAM do I need?

A: As a rule of thumb:

- 7B model: 8GB RAM minimum, 16GB recommended
- 14B model: 16GB RAM minimum, 32GB recommended
- Plus RAM for your OS and other applications

### Q: Can I use GPU acceleration?

A: Yes! Ollama supports GPU acceleration:

```bash
# Check GPU support
ollama ls --show-gpu-support

# Run with GPU
CUDA_VISIBLE_DEVICES=0 ollama serve
```

### Q: What if Ollama doesn't support a model I need?

A: You have three options:

1. Use a different provider (Claude or Qwen)
1. Check if Ollama has added the model: `ollama list`
1. Request the model on Ollama's GitHub

### Q: Is Ollama suitable for team use?

A: For team use, consider:

- **Central server**: Run Ollama on shared server
- **Multiple users**: Configure clients to point to server: `OLLAMA_BASE_URL=http://server:11434`
- **Resource management**: Monitor server load and RAM
- **Alternative**: Use cloud provider for better performance

## Advanced Configuration

### Custom Ollama Endpoint

```yaml
# settings/local.yaml
ai:
  ai_provider: ollama

ollama_base_url: http://ollama-server:11434
ollama_model: qwen2.5-coder:7b
ollama_timeout: 600  # Longer timeout for large models
```

### Model Parameters

```python
# In crackerjack/adapters/ai/ollama.py
# Can customize num_ctx for larger context windows

class OllamaCodeFixerSettings(BaseCodeFixerSettings):
    num_ctx: int = Field(
        default=4096,  # Increase for larger context
        ge=1024,
        le=32768,
    )
```

## Migration from Cloud Provider

### Step 1: Test Ollama

```bash
# Install and test Ollama
ollama serve
ollama pull qwen2.5-coder:7b

# Test with small task
export AI_PROVIDER=ollama
python -m crackerjack run --ai-fix --changed-only
```

### Step 2: Compare Quality

Run same codebase with both providers:

```bash
# Ollama
export AI_PROVIDER=ollama
python -m crackerjack run --ai-fix

# Claude
export AI_PROVIDER=claude
python -m crackerjack run --ai-fix

# Compare results
diff <ollama_fixes> <claude_fixes>
```

### Step 3: Switch to Ollama

```bash
# Set default in settings/local.yaml
ai:
  ai_provider: ollama

# Or environment variable
export AI_PROVIDER=ollama
```

## Related Documentation

- [Qwen Provider Documentation](QWEN_PROVIDER.md)
- [Provider Architecture Documentation](PROVIDER_ARCHITECTURE.md)
- [Configuration Reference](../reference/CONFIGURATION.md)

## Support

- Ollama Issues: https://github.com/ollama/ollama/issues
- Crackerjack Issues: https://github.com/yourusername/crackerjack/issues
- Model Issues: Check model's repository on GitHub

## Changelog

### Version 0.50.0 (2025-01-23)

- ✅ Added Ollama provider support
- ✅ Local model execution (zero API costs)
- ✅ Interactive provider selection CLI
- ✅ Unified provider architecture
- ✅ Provider registry system
