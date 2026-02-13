# Protocol-Based Design

Crackerjack uses **protocol-based dependency injection** for loose coupling and easy testing.

## Key Principles

- **Constructor Injection**: All dependencies via `__init__`
- **Protocol Imports**: Import from `models/protocols.py`, never concrete classes
- **Lifecycle Management**: Proper cleanup patterns

## Example

```python
# ✅ Correct - Protocol imports
from crackerjack.models.protocols import Console, TestManagerProtocol

def __init__(
    self,
    console: Console,
    test_manager: TestManagerProtocol,
) -> None:
    self.console = console
    self.test_manager = test_manager

# ❌ Wrong - Direct class imports
from crackerjack.managers.test_manager import TestManager
from rich.console import Console as RichConsole
```

## See Also

- [CLAUDE.md](../README.md#architecture) - Complete architecture guidelines
- [Protocol Definitions](../api/reference.md#protocols)
