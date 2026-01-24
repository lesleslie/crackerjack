# Provider Architecture - Unified AI Provider System

## Overview

Crackerjack's AI provider system uses a **unified architecture** that eliminates code duplication, ensures consistent security validation, and makes it easy to add new providers.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Crackerjack CLI                        │
│                   (crackerjack/__main__.py)                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ├─→ --select-provider flag
                           │
                           ↓
                  ┌──────────────────────┐
                  │  Provider Registry   │
                  │ (provider factory)   │
                  └──────────┬───────────┘
                             │
                             ├─→ ProviderID.CLAUDE
                             ├─→ ProviderID.QWEN
                             └─→ ProviderID.OLLAMA
                             │
                    ┌────────┴─────────────────┐
                    │  BaseCodeFixer         │
                    │  (abstract base class) │
                    └────────┬─────────────────┘
                             │
             ┌───────────────┼───────────────┐
             │               │               │
        ┌────▼─────┐   ┌────▼─────┐   ┌──▼────────┐
        │  Claude  │   │   Qwen    │   │  Ollama   │
        │CodeFixer │   │CodeFixer  │   │CodeFixer  │
        └────┬─────┘   └────┬─────┘   └──┬────────┘
             │               │               │
             └───────────────┴───────────────┘
                           │
                           ↓
                  ┌──────────────────────┐
                  │  Security Validation  │
                  │  (enforced in base)  │
                  └───────────────────────┘
```

## Core Components

### 1. BaseCodeFixer (Abstract Base Class)

**File**: `/Users/les/Projects/crackerjack/crackerjack/adapters/ai/base.py`

**Purpose**: Defines the template method pattern for all AI providers.

**Key Methods**:

| Method | Type | Purpose |
|--------|------|---------|
| `init()` | Public | Async lifecycle initialization |
| `fix_code_issue()` | Public | Main entry point for fixing code |
| `_initialize_client()` | Abstract | Provider-specific client creation |
| `_call_provider_api()` | Abstract | Provider-specific API call |
| `_extract_content_from_response()` | Abstract | Provider-specific response parsing |
| `_validate_provider_specific_settings()` | Abstract | Provider-specific settings validation |

**Template Methods** (implemented in base class):

| Method | Purpose |
|--------|---------|
| `_fix_code_issue_with_retry()` | Retry logic with exponential backoff |
| `_ensure_client()` | Lazy client initialization with thread-safety |
| `_parse_fix_response()` | Response parsing and security validation |
| `_validate_ai_generated_code()` | **MANDATORY** security checks |
| `_check_dangerous_patterns()` | Detect eval, exec, etc. |
| `_validate_ast_security()` | Parse AST and check imports |
| `_sanitize_error_message()` | Remove sensitive data from errors |
| `_sanitize_prompt_input()` | Prevent prompt injection |
| `_build_fix_prompt()` | Generate standardized prompt |
| `_validate_fix_quality()` | Check confidence thresholds |

### 2. Provider-Specific Implementations

#### ClaudeCodeFixer

**File**: `/Users/les/Projects/crackerjack/crackerjack/adapters/ai/claude.py`

**Lines of Code**: ~150 (down from ~507 before refactoring)

**Key Features**:

- Uses Anthropic's Messages API
- Response format: `response.content[0].text`
- API key format: `sk-ant-...`

**Unique Implementation**:

```python
async def _call_provider_api(self, client, prompt):
    return await client.messages.create(
        model=self._settings.model,
        max_tokens=self._settings.max_tokens,
        temperature=self._settings.temperature,
        messages=[{"role": "user", "content": prompt}],
    )

def _extract_content_from_response(self, response):
    return response.content[0].text
```

#### QwenCodeFixer

**File**: `/Users/les/Projects/crackerjack/crackerjack/adapters/ai/qwen.py`

**Lines of Code**: ~140 (down from ~508 before refactoring)

**Key Features**:

- Uses Qwen's OpenAI-compatible API
- Response format: `response.choices[0].message.content`
- API key format: Variable (no prefix check)

**Unique Implementation**:

```python
async def _call_provider_api(self, client, prompt):
    return await client.chat.completions.create(
        model=self._settings.model,
        max_tokens=self._settings.max_tokens,
        temperature=self._settings.temperature,
        messages=[{"role": "user", "content": prompt}],
    )

def _extract_content_from_response(self, response):
    return response.choices[0].message.content
```

#### OllamaCodeFixer

**File**: `/Users/les/Projects/crackerjack/crackerjack/adapters/ai/ollama.py`

**Lines of Code**: ~150

**Key Features**:

- Uses Ollama's OpenAI-compatible API
- No API key required (local execution)
- Response format: `response.choices[0].message.content`

**Unique Implementation**:

```python
async def _initialize_client(self):
    client = openai.AsyncOpenAI(
        base_url=self._settings.base_url + "/v1",
        api_key="ollama",  # Required by client but ignored by Ollama
        timeout=self._settings.timeout,
    )
```

### 3. Provider Registry

**File**: `/Users/les/Projects/crackerjack/crackerjack/adapters/ai/registry.py`

**Purpose**: Central registry of all providers with metadata and factory functions.

**Key Components**:

#### ProviderID Enum

```python
class ProviderID(str, Enum):
    CLAUDE = "claude"
    QWEN = "qwen"
    OLLAMA = "ollama"
```

#### ProviderInfo Dataclass

```python
@dataclass(frozen=True)
class ProviderInfo:
    id: ProviderID
    name: str
    description: str
    requires_api_key: bool
    default_model: str
    setup_url: str
    cost_tier: str  # "free", "low", "medium", "high"
```

#### ProviderFactory

```python
class ProviderFactory:
    @staticmethod
    def create_provider(provider_id, settings=None) -> BaseCodeFixer:
        """Factory method to create provider instances."""

    @staticmethod
    def get_provider_info(provider_id) -> ProviderInfo:
        """Get metadata about a provider."""

    @staticmethod
    def list_providers() -> list[ProviderInfo]:
        """List all available providers."""
```

## Security Validation Flow

All providers **MUST** enforce identical security checks:

```
┌─────────────────────────────────────────────────────────┐
│  AI Response (from any provider)                        │
└──────────────────────┬──────────────────────────────────┘
                           │
                           ↓
                  ┌──────────────────────┐
                  │  Parse JSON Response  │
                  └──────────┬───────────┘
                             │
                             ↓
                  ┌──────────────────────┐
                  │ _validate_ai_generated_code()  │
                  │  (MANDATORY for all providers)  │
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                    │
        ┌───▼────┐   ┌────────▼────────┐   ┌─────▼─────┐
        │ Pattern│   │     AST        │   │   Size    │
        │ Checks│   │     Checks     │   │  Checks   │
        └───┬────┘   └────────┬────────┘   └─────┬─────┘
           │                │                   │
           └────────────────┴───────────────────┘
                           │
                           ↓
                  ┌──────────────────────┐
                  │  Validated Code      │
                  │  (safe to apply)     │
                  └──────────────────────┘
```

### Security Checks (Identical for All Providers)

1. **Dangerous Pattern Detection**

   - `eval()` calls
   - `exec()` calls
   - `__import__()` calls
   - `subprocess(..., shell=True)`
   - `os.system()` calls
   - `pickle.loads/unpickle()`
   - `yaml.load(..., Loader=yaml.Loader)`

1. **AST Security Scanning**

   - Parse code into AST
   - Scan for dangerous imports (`os`, `subprocess`, `sys`)
   - Validate syntax

1. **Code Size Limits**

   - Maximum: 10MB (configurable)
   - Prevents DoS via excessive code size

1. **Prompt Injection Prevention**

   - Filter "ignore previous" patterns
   - Filter "system:/assistant:/user:" patterns
   - Filter "you are now/act as" patterns
   - Replace \`\`\` with ''' to prevent markdown injection

1. **Error Message Sanitization**

   - Remove Unix paths: `/[\w\-./ ]+/` → `<path>/`
   - Remove Windows paths: `[A-Z]:\\[\w\-\\ ]+\\` → `<path>\\`
   - Remove API keys: `sk-[a-zA-Z0-9]{20,}` → `<api-key>`
   - Remove secrets: `["'][\w\-]{32,}["']` → `<secret>`

## Adding a New Provider

To add a new provider (e.g., OpenAI, Mistral):

### Step 1: Create Settings Class

**File**: `/Users/les/Projects/crackerjack/crackerjack/adapters/ai/openai.py`

```python
"""OpenAI AI provider for code fixing."""

import logging
import typing as t
from uuid import UUID

from pydantic import Field, SecretStr

from crackerjack.adapters.ai.base import BaseCodeFixer, BaseCodeFixerSettings
from crackerjack.models.adapter_metadata import AdapterStatus

MODULE_ID = UUID("12345678-1234-1234-1234-123456789abc")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)


class OpenAICodeFixerSettings(BaseCodeFixerSettings):
    """OpenAI-specific settings."""
    openai_api_key: SecretStr = Field(
        ...,
        description="OpenAI API key from environment variable OPENAI_API_KEY",
    )
    model: str = Field(
        default="gpt-4o",
        description="OpenAI model to use for code fixing",
    )


class OpenAICodeFixer(BaseCodeFixer):
    """OpenAI AI code fixer implementation."""

    def __init__(self, settings: OpenAICodeFixerSettings | None = None) -> None:
        super().__init__(settings)

    async def _initialize_client(self) -> t.Any:
        """Initialize OpenAI client."""
        import openai

        assert isinstance(self._settings, OpenAICodeFixerSettings)
        api_key = self._settings.openai_api_key.get_secret_value()

        client = openai.AsyncOpenAI(api_key=api_key)
        logger.debug("OpenAI API client initialized")
        return client

    async def _call_provider_api(self, client: t.Any, prompt: str) -> t.Any:
        """Call OpenAI Chat Completions API."""
        assert isinstance(self._settings, OpenAICodeFixerSettings)
        return await client.chat.completions.create(
            model=self._settings.model,
            messages=[{"role": "user", "content": prompt}],
        )

    def _extract_content_from_response(self, response: t.Any) -> str:
        """Extract content from OpenAI response."""
        return response.choices[0].message.content

    def _validate_provider_specific_settings(self) -> None:
        """Validate OpenAI API key."""
        if not self._settings:
            msg = "OpenAICodeFixerSettings not provided"
            raise RuntimeError(msg)

        assert isinstance(self._settings, OpenAICodeFixerSettings)
        key = self._settings.openai_api_key.get_secret_value()
        if not key.startswith("sk-"):
            msg = f"Invalid OpenAI API key format: {key[:10]}..."
            raise ValueError(msg)
```

**Total**: ~50 lines of code for a new provider!

### Step 2: Register Provider

**File**: `/Users/les/Projects/crackerjack/crackerjack/adapters/ai/registry.py`

Add to `ProviderID` enum:

```python
class ProviderID(str, Enum):
    CLAUDE = "claude"
    QWEN = "qwen"
    OLLAMA = "ollama"
    OPENAI = "openai"  # ADD THIS
```

Add to `PROVIDER_INFO` dict:

```python
PROVIDER_INFO: dict[ProviderID, ProviderInfo] = {
    # ... existing providers ...
    ProviderID.OPENAI: ProviderInfo(
        id=ProviderID.OPENAI,
        name="OpenAI",
        description="State-of-the-art GPT models, excellent reasoning",
        requires_api_key=True,
        default_model="gpt-4o",
        setup_url="https://platform.openai.com/docs/quickstart",
        cost_tier="high",
    ),
}
```

Add to `ProviderFactory.create_provider()`:

```python
# Import
from crackerjack.adapters.ai.openai import OpenAICodeFixer, OpenAICodeFixerSettings

# Add to create_provider method
if provider_id == ProviderID.OPENAI:
    if settings is None:
        settings = OpenAICodeFixerSettings()
    return OpenAICodeFixer(settings)
```

### Step 3: Update Settings

**File**: `/Users/les/Projects/crackerjack/crackerjack/config/settings.py`

```python
class AISettings(Settings):
    ai_provider: t.Literal["claude", "qwen", "ollama", "openai"] = "claude"
```

### Step 4: Update Exports

**File**: `/Users/les/Projects/crackerjack/crackerjack/adapters/ai/__init__.py`

```python
from .openai import OpenAICodeFixer, OpenAICodeFixerSettings

__all__ = [
    # ... existing exports ...
    "OpenAICodeFixer",
    "OpenAICodeFixerSettings",
]
```

**Total**: 4 files, ~50 lines of new code = **~200 lines total** for a complete new provider!

## Design Patterns Used

### 1. Template Method Pattern

**Purpose**: Define algorithm skeleton in base class, override specific steps in subclasses.

**Implementation**:

- Base class defines `_fix_code_issue_with_retry()`
- Subclasses override `_call_provider_api()` and `_extract_content_from_response()`
- All providers inherit security validation

**Benefits**:

- Eliminates code duplication
- Ensures consistent behavior
- Easy to add new providers

### 2. Factory Pattern

**Purpose**: Create provider instances without specifying concrete classes.

**Implementation**:

- `ProviderFactory.create_provider(id, settings)`
- Returns `BaseCodeFixer` (not concrete classes)
- Caller doesn't need to know which class

**Benefits**:

- Decouples caller from implementation
- Easy to add new providers
- Centralized provider metadata

### 3. Strategy Pattern

**Purpose**: Different algorithms for different providers.

**Implementation**:

- `_call_provider_api()` = strategy
- Each provider implements different API call
- Base class orchestrates the flow

**Benefits**:

- Provider-specific logic isolated
- Easy to test individual providers
- Clear separation of concerns

## Configuration Flow

```
User Request
      │
      ↓
┌─────────────────────┐
│ CLI (--select-provider)│
└──────────┬──────────┘
           │
           ↓
    ┌────────────────┐
    │ ProviderFactory  │
    │ .create_provider│
    └────────┬─────────┘
             │
             ├─→ ClaudeCodeFixer
             ├─→ QwenCodeFixer
             └─→ OllamaCodeFixer
             │
             ↓
    ┌────────────────┐
    │  BaseCodeFixer  │
    │  (inherits all)  │
    └────────┬─────────┘
             │
             ↓
    ┌────────────────┐
    │  fix_code_issue()│
    └────────┬─────────┘
             │
             ↓
    ┌────────────────┐
    │  Validated Code  │
    └────────────────┘
```

## Benefits of Unified Architecture

### 1. Reduced Code Duplication

**Before**:

- ClaudeCodeFixer: ~507 lines
- QwenCodeFixer: ~508 lines
- **Total**: ~1,015 lines with ~400 lines duplicated

**After**:

- BaseCodeFixer: ~500 lines (shared)
- ClaudeCodeFixer: ~150 lines
- QwenCodeFixer: ~140 lines
- OllamaCodeFixer: ~150 lines
- **Total**: ~940 lines with **zero duplication**

**Savings**: ~400 lines of duplicated code eliminated!

### 2. Consistent Security

All providers **MUST** implement `_validate_ai_generated_code()` which includes:

- ✅ Dangerous pattern detection
- ✅ AST security scanning
- ✅ Code size limits
- ✅ Prompt injection prevention
- ✅ Error message sanitization

**Enforced in**: BaseCodeFixer, cannot be bypassed.

### 3. Easy Testing

```python
# Test all providers with same code
from crackerjack.adapters.ai.registry import ProviderFactory

providers = ["claude", "qwen", "ollama"]
for provider_id in providers:
    provider = ProviderFactory.create_provider(provider_id)
    # Test provider
    assert await provider.fix_code_issue(...) is not None
```

### 4. Type Safety

```python
from crackerjack.adapters.ai.base import BaseCodeFixer

def use_provider(fixer: BaseCodeFixer) -> None:
    """Works with any provider instance."""
    # Type-safe
    # All providers have fix_code_issue()
    pass
```

## Migration Guide

### For Existing Code

**No changes required!** All existing code continues to work:

```python
from crackerjack.adapters.ai import ClaudeCodeFixer, ClaudeCodeFixerSettings

# Still works exactly the same
settings = ClaudeCodeFixerSettings(anthropic_api_key="...")
fixer = ClaudeCodeFixer(settings)
await fixer.fix_code_issue(...)
```

### For New Code

**Use factory for dynamic provider selection**:

```python
from crackerjack.adapters.ai.registry import ProviderFactory, ProviderID

# Select provider at runtime
provider_id = ProviderID.OLLAMA if offline else ProviderID.CLAUDE
fixer = ProviderFactory.create_provider(provider_id)
await fixer.fix_code_issue(...)
```

## Performance Characteristics

### Memory Overhead

- **Base class**: ~500 lines (loaded once)
- **Per-instance overhead**: Minimal (just settings reference)
- **No runtime penalty**: All methods are direct calls (not indirected)

### Startup Time

- **Before**: Same for all providers
- **After**: Same (lazy loading of provider-specific imports)

### Execution Speed

- **Identical**: All providers use same retry logic, validation
- **Difference**: Only in API call/response parsing (negligible)

## Testing Strategy

### Unit Tests

```python
# Test base class security validation
def test_base_security_validation():
    from crackerjack.adapters.ai.base import BaseCodeFixer, BaseCodeFixerSettings

    class MockProvider(BaseCodeFixer):
        async def _initialize_client(self): ...
        async def _call_provider_api(self, client, prompt): ...
        def _extract_content_from_response(self, response): ...
        def _validate_provider_specific_settings(self): ...

    # Test dangerous pattern detection
    provider = MockProvider(BaseCodeFixerSettings())
    is_valid, msg = provider._check_dangerous_patterns("eval(x)")
    assert not is_valid  # Should reject

# Test provider factory
def test_provider_factory():
    from crackerjack.adapters.ai.registry import ProviderFactory, ProviderID

    provider = ProviderFactory.create_provider(ProviderID.QWEN)
    assert isinstance(provider, QwenCodeFixer)  # Type-safe
```

### Integration Tests

```python
# Test all providers with same test case
async def test_all_providers():
    from crackerjack.adapters.ai.registry import ProviderFactory, ProviderID

    code = "def broken():\n    return 1/0"

    for provider_id in [ProviderID.CLAUDE, ProviderID.QWEN, ProviderID.OLLAMA]:
        provider = ProviderFactory.create_provider(provider_id)
        result = await provider.fix_code_issue(
            file_path="test.py",
            issue_description="Fix division by zero",
            code_context=code,
            fix_type="runtime"
        )
        assert result["success"] is True
```

## Best Practices

### 1. Use Base Classes

**When** implementing new providers:

- Always inherit from `BaseCodeFixer`
- Always inherit settings from `BaseCodeFixerSettings`
- Use abstract methods for provider-specific logic

**Don't**:

- Copy code from existing providers (use base class instead)
- Skip security validation (enforced in base class)
- Implement `fix_code_issue()` directly (use template method)

### 2. Use Factory Pattern

**When** creating provider instances:

- Use `ProviderFactory.create_provider()`
- Pass `ProviderID` enum (not strings)
- Let factory handle defaults

**Don't**:

- Import concrete classes directly (unless testing)
- Hardcode provider names (use ProviderID enum)
- Create instances with `new ClassName()` (use factory)

### 3. Document Provider-Specific Behavior

**In provider docstring**, document:

- API endpoint being used
- Response format
- Authentication method
- Any limitations or quirks

**Example**:

```python
class QwenCodeFixer(BaseCodeFixer):
    """Qwen AI code fixer using Alibaba DashScope API.

    API Documentation: https://help.aliyun.com/zh/dashscope/
    Response Format: OpenAI-compatible (response.choices[0].message.content)
    Authentication: API key via QWEN_API_KEY environment variable

    Limitations:
    - Requires internet connection
    - Rate limits apply (see Dashscope docs)
    """
```

## Related Documentation

- [Ollama Provider Documentation](OLLAMA_PROVIDER.md)
- [Qwen Provider Documentation](QWEN_PROVIDER.md)
- [Configuration Reference](../reference/CONFIGURATION.md)

## Glossary

| Term | Definition |
|------|------------|
| **BaseCodeFixer** | Abstract base class defining the provider interface |
| **Template Method** | Design pattern where base class defines algorithm, subclasses override steps |
| **ProviderID** | Enum of all available provider identifiers |
| **ProviderInfo** | Dataclass containing provider metadata |
| **ProviderFactory** | Factory class for creating provider instances |
| **Security Validation** | Mandatory checks applied to all providers |
| **AST Security** | Abstract Syntax Tree parsing for dangerous imports |
| **Settings Class** | Pydantic BaseModel subclass for provider configuration |
