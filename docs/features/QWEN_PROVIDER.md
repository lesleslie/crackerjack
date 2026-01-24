# Qwen AI Provider for Crackerjack

## Overview

Crackerjack supports **Qwen** as an alternative AI provider for code fixing, in addition to the default Claude provider. Qwen provides:

- **Cost efficiency**: Significantly lower cost than Claude for similar quality
- **Code specialization**: Qwen Coder models are fine-tuned for programming tasks
- **OpenAI-compatible API**: Seamless integration using standard OpenAI SDK
- **Multiple model options**: Choose from qwen-turbo, qwen-plus, qwen-coder-plus, or qwen-max

## Quick Start

### Method 1: Environment Variables (Recommended)

```bash
# Set Qwen API key
export QWEN_API_KEY="sk-your-qwen-api-key-here"

# Optional: Customize model and endpoint
export QWEN_MODEL="qwen-coder-plus"  # Default: qwen-coder-plus
export QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"  # Default

# Run crackerjack with Qwen
python -m crackerjack run --ai-fix --ai-provider qwen
```

### Method 2: Configuration File

Create or update `settings/local.yaml`:

```yaml
ai:
  ai_provider: qwen
  autofix: true
```

Then set the API key via environment variable:

```bash
export QWEN_API_KEY="sk-your-qwen-api-key-here"
python -m crackerjack run --ai-fix
```

## Available Models

| Model | Use Case | Speed | Cost |
|-------|----------|-------|------|
| **qwen-coder-plus** | Code fixing (recommended) | Fast | Low |
| qwen-turbo | Simple fixes | Fastest | Lowest |
| qwen-plus | General tasks | Medium | Medium |
| qwen-max | Complex issues | Slowest | High |

**Recommendation**: Use `qwen-coder-plus` for code fixing tasks (default).

## Configuration Options

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QWEN_API_KEY` | Yes | - | Your Qwen API key |
| `QWEN_MODEL` | No | `qwen-coder-plus` | Model to use |
| `QWEN_BASE_URL` | No | `https://dashscope.aliyuncs.com/compatible-mode/v1` | API endpoint |

### Settings File

In `settings/local.yaml` or `settings/crackerjack.yaml`:

```yaml
ai:
  ai_provider: qwen  # Switch to Qwen
  autofix: true
  max_iterations: 5
```

## Switching Between Providers

### Switch from Claude to Qwen

```bash
# Method 1: Command-line flag
python -m crackerjack run --ai-fix --ai-provider qwen

# Method 2: Configuration file
# Set ai_provider: qwen in settings/local.yaml

# Method 3: Environment variable (temporary)
export AI_PROVIDER=qwen
python -m crackerjack run --ai-fix
```

### Switch from Qwen back to Claude

```bash
# Method 1: Command-line flag
python -m crackerjack run --ai-fix --ai-provider claude

# Method 2: Configuration file
# Set ai_provider: claude in settings/local.yaml (or remove the field)
```

## Getting a Qwen API Key

1. Visit [Alibaba Cloud DashScope](https://dashscope.aliyun.com/)
1. Create an account or sign in
1. Navigate to API Keys
1. Create a new API key
1. Set the `QWEN_API_KEY` environment variable

## Usage Examples

### Basic Usage

```bash
# Set API key
export QWEN_API_KEY="sk-your-key"

# Run with default settings
python -m crackerjack run --ai-fix
```

### With Specific Model

```bash
export QWEN_API_KEY="sk-your-key"
export QWEN_MODEL="qwen-max"
python -m crackerjack run --ai-fix --ai-provider qwen
```

### With Tests

```bash
export QWEN_API_KEY="sk-your-key"
python -m crackerjack run --ai-fix --run-tests --ai-provider qwen
```

### Parallel Execution

```bash
export QWEN_API_KEY="sk-your-key"
python -m crackerjack run --ai-fix --parallel-phases --test-workers 4 --ai-provider qwen
```

## Architecture

### Provider Selection Pattern

Crackerjack uses a **provider selection pattern** that allows dynamic switching between AI providers:

```
┌─────────────────────┐
│   AI Provider Config │
│  (claude or qwen)   │
└──────────┬──────────┘
           │
           ├─→ ClaudeCodeFixer (Anthropic SDK)
           │   └─→ ClaudeCodeBridge
           │
           └─→ QwenCodeFixer (OpenAI SDK)
               └─→ QwenCodeBridge
```

### Security Validation

Both providers implement **identical security validation**:

- Dangerous pattern detection (eval, exec, etc.)
- AST-based import scanning
- Code size limits
- Prompt injection prevention
- Error message sanitization

**Key Point**: Qwen-generated code goes through the same security checks as Claude-generated code.

### Response Parsing

| Provider | SDK | Response Access |
|----------|-----|-----------------|
| Claude | Anthropic | `response.content[0].text` |
| Qwen | OpenAI | `response.choices[0].message.content` |

Both providers use the same JSON response format for fixes.

## Troubleshooting

### API Key Issues

**Problem**: `Authentication failed` error

**Solution**:

- Verify `QWEN_API_KEY` is set correctly
- Check the API key is valid and active
- Ensure the key has sufficient permissions

### Import Errors

**Problem**: `Cannot import QwenCodeFixer`

**Solution**:

- Ensure `openai` package is installed: `uv pip install openai`
- Verify crackerjack is up to date: `uv sync`

### Model Not Found

**Problem**: `Model not found` error

**Solution**:

- Verify the model name is correct
- Check the model is available in your region
- Try the default: `qwen-coder-plus`

### Slow Response Times

**Problem**: Qwen is slower than expected

**Solution**:

- Switch to a faster model (e.g., `qwen-turbo`)
- Check your network connection to the API endpoint
- Consider using `qwen-coder-plus` for best balance of speed and quality

## Performance Comparison

Typical performance for fixing 10 code issues:

| Provider | Model | Time | Cost (relative) |
|----------|-------|------|-----------------|
| Claude | claude-sonnet-4-5 | ~60s | 1.0x (baseline) |
| Qwen | qwen-coder-plus | ~45s | ~0.1x |
| Qwen | qwen-turbo | ~30s | ~0.05x |
| Qwen | qwen-max | ~90s | ~0.3x |

**Note**: Actual performance varies based on issue complexity and network conditions.

## Best Practices

### 1. Use Environment Variables for API Keys

❌ **Don't** hardcode API keys in config files:

```yaml
# RISKY: API key in config file
ai:
  ai_provider: qwen
  qwen_api_key: sk-your-key  # DON'T DO THIS
```

✅ **Do** use environment variables:

```bash
# SAFE: API key in environment
export QWEN_API_KEY="sk-your-key"
```

### 2. Choose the Right Model

- **Simple formatting issues**: `qwen-turbo` (fastest)
- **Code logic fixes**: `qwen-coder-plus` (recommended)
- **Complex refactoring**: `qwen-max` (highest quality)

### 3. Test Before Full Migration

```bash
# Test on a small subset first
export QWEN_API_KEY="sk-your-key"
python -m crackerjack run --ai-fix --ai-provider qwen --run-tests

# If successful, run on full codebase
python -m crackerjack run --ai-fix --ai-provider qwen
```

### 4. Monitor Quality

- Review Qwen-generated fixes before committing
- Compare quality with Claude fixes
- Adjust confidence threshold if needed

## Migration from Claude

### Step 1: Test Qwen

```bash
export QWEN_API_KEY="sk-your-key"
python -m crackerjack run --ai-fix --ai-provider qwen --run-tests
```

### Step 2: Review Results

Check the quality of Qwen-generated fixes. If satisfactory, proceed.

### Step 3: Update Configuration

```yaml
# In settings/local.yaml
ai:
  ai_provider: qwen
```

### Step 4: Remove Claude Dependency (Optional)

If you're fully migrating to Qwen and no longer need Claude:

```bash
# Remove anthropic dependency (optional)
uv pip remove anthropic
```

**Note**: This is optional. You can keep both providers installed and switch between them as needed.

## FAQ

### Q: Is Qwen as good as Claude for code fixing?

A: For most code fixing tasks, `qwen-coder-plus` provides comparable quality to Claude at significantly lower cost. For complex architectural issues, Claude may still have an edge.

### Q: Can I use both providers simultaneously?

A: No, you must choose one provider per run. However, you can easily switch between providers using the `--ai-provider` flag.

### Q: Do I need to change my code to use Qwen?

A: No, the interface is identical. Just set the provider selection and API key.

### Q: What about other crackerjack features?

A: All crackerjack features work with both providers:

- Quality gates (ruff, pytest, etc.)
- Parallel execution
- Test running
- MCP server
- All hooks and adapters

### Q: Is my code sent to Alibaba Cloud?

A: Yes, when using Qwen, code snippets are sent to Alibaba's DashScope API for processing. Review their [privacy policy](https://www.alibabacloud.com/help/en/privacy-policy) for details.

## Related Documentation

- [Configuration Reference](../reference/CONFIGURATION.md)
- [AI Fixing Documentation](../AI_FIX_EXPECTED_BEHAVIOR.md)

## Support

For issues or questions:

1. Check the [troubleshooting section](#troubleshooting)
1. Review [test integration script](../../test_qwen_integration.py)
1. Open an issue on GitHub

## Changelog

### Version 0.49.9 (2025-01-23)

- ✅ Initial Qwen provider support
- ✅ Provider selection via `ai_provider` setting
- ✅ QwenCodeFixer adapter with full security validation
- ✅ QwenCodeBridge for agent consultation
- ✅ Configuration examples and documentation
