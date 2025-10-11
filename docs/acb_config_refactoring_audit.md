# ACB Configuration Refactoring Audit

**Date:** 2025-10-11
**Author:** Gemini

## 1. Executive Summary

This report provides a comprehensive audit of the Crackerjack project's configuration system and outlines a detailed plan for refactoring it to use the `acb` (Asynchronous Component Base) framework. The current system is fragmented, with configuration logic scattered across multiple files and modules. This leads to unnecessary complexity, boilerplate code, and a lack of centralization.

By adopting `acb.config.Settings`, Crackerjack can significantly simplify its configuration management, reduce code duplication, and improve maintainability. This refactoring will also align the project more closely with the `acb` framework, enabling it to take full advantage of its features.

**Key Recommendations:**

*   **Centralize Configuration:** Create a single `CrackerjackSettings` class that extends `acb.config.Settings` to serve as the single source of truth for all configuration.
*   **Eliminate Manual Loading:** Replace the manual configuration loading and merging logic with `acb.depends.get(Config)`.
*   **Simplify Dynamic Configuration:** Refactor the `dynamic_config.py` module to leverage `acb`'s configuration management capabilities.
*   **Adopt Dependency Injection:** Use `@depends.inject` to provide configuration to services and components.

This report provides a step-by-step guide for implementing these recommendations, including code examples and a proposed migration plan.

## 2. Audit Findings

The current configuration system in Crackerjack is a mix of Pydantic models, dataclasses, and custom loading logic. This has resulted in a fragmented and overly complex system.

### 2.1. Scattered Configuration Objects

Configuration is defined in multiple places, including:

*   `crackerjack/config/global_lock_config.py`: `GlobalLockConfig` dataclass.
*   `crackerjack/models/config.py`: `WorkflowOptions` and its nested dataclasses.
*   `crackerjack/orchestration/config.py`: `OrchestrationConfig` dataclass.
*   `crackerjack/services/unified_config.py`: `CrackerjackConfig` Pydantic model.
*   `crackerjack/dynamic_config.py`: `HOOKS_REGISTRY` and `CONFIG_MODES` dictionaries.

This scattering of configuration makes it difficult to understand and manage the project's settings.

### 2.2. Manual Configuration Loading and Merging

The `OrchestrationConfig` and `UnifiedConfigurationService` classes implement custom logic for:

*   Loading configuration from YAML, TOML, and JSON files.
*   Loading configuration from environment variables.
*   Merging configuration from multiple sources.

This is redundant, as `acb` provides this functionality out of the box.

### 2.3. Complex Dynamic Configuration

The `dynamic_config.py` module is responsible for generating pre-commit configurations based on different modes. While this is a powerful feature, it is tightly coupled to the pre-commit framework. By using `acb` to manage tool configurations directly, this module can be significantly simplified.

## 3. Refactoring Plan

This section outlines a detailed plan for refactoring the configuration system to use `acb`.

### 3.1. Step 1: Create a Centralized `CrackerjackSettings` Class

The first step is to create a single `CrackerjackSettings` class that extends `acb.config.Settings`. This class will consolidate all configuration from the various scattered objects.

**File:** `crackerjack/config/settings.py`

```python
from acb.config import Settings
from pathlib import Path
import typing as t

class CleaningSettings(Settings):
    clean: bool = True
    update_docs: bool = False
    force_update_docs: bool = False
    compress_docs: bool = False
    auto_compress_docs: bool = False

class HookSettings(Settings):
    skip_hooks: bool = False
    update_precommit: bool = False
    experimental_hooks: bool = False
    enable_pyrefly: bool = False
    enable_ty: bool = False
    enable_lsp_optimization: bool = False

class TestSettings(Settings):
    test: bool = False
    benchmark: bool = False
    test_workers: int = 0
    test_timeout: int = 0

class PublishSettings(Settings):
    publish: t.Any | None = None
    bump: t.Any | None = None
    all: t.Any | None = None
    no_git_tags: bool = False
    skip_version_check: bool = False

class GitSettings(Settings):
    commit: bool = False
    create_pr: bool = False

class AISettings(Settings):
    ai_agent: bool = False
    start_mcp_server: bool = False
    max_iterations: int = 5
    autofix: bool = True
    ai_agent_autofix: bool = False

class ExecutionSettings(Settings):
    interactive: bool = False
    verbose: bool = False
    async_mode: bool = False
    no_config_updates: bool = False

class ProgressSettings(Settings):
    enabled: bool = False

class CleanupSettings(Settings):
    auto_cleanup: bool = True
    keep_debug_logs: int = 5
    keep_coverage_files: int = 10

class EnterpriseSettings(Settings):
    enabled: bool = False
    license_key: str | None = None
    organization: str | None = None

class MCPServerSettings(Settings):
    http_port: int = 8676
    http_host: str = "127.0.0.1"
    websocket_port: int = 8675
    http_enabled: bool = False

class ZubanLSPSettings(Settings):
    enabled: bool = True
    auto_start: bool = True
    port: int = 8677
    mode: str = "stdio"
    timeout: int = 30

class GlobalLockSettings(Settings):
    enabled: bool = True
    timeout_seconds: float = 600.0
    stale_lock_hours: float = 2.0
    lock_directory: Path = Path.home() / ".crackerjack" / "locks"
    session_heartbeat_interval: float = 30.0
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 5.0
    enable_lock_monitoring: bool = True

class CrackerjackSettings(Settings):
    cleaning: CleaningSettings = CleaningSettings()
    hooks: HookSettings = HookSettings()
    testing: TestSettings = TestSettings()
    publishing: PublishSettings = PublishSettings()
    git: GitSettings = GitSettings()
    ai: AISettings = AISettings()
    execution: ExecutionSettings = ExecutionSettings()
    progress: ProgressSettings = ProgressSettings()
    cleanup: CleanupSettings = CleanupSettings()
    enterprise: EnterpriseSettings = EnterpriseSettings()
    mcp_server: MCPServerSettings = MCPServerSettings()
    zuban_lsp: ZubanLSPSettings = ZubanLSPSettings()
    global_lock: GlobalLockSettings = GlobalLockSettings()
```

### 3.2. Step 2: Replace Manual Configuration Loading

Next, replace the manual configuration loading and merging logic with `acb.depends.get(Config)`. This will eliminate the need for the `OrchestrationConfig` and `UnifiedConfigurationService` classes.

**Example:**

```python
from acb.depends import depends
from acb.config import Config
from crackerjack.config.settings import CrackerjackSettings

# Get the config from acb
config = depends.get(Config)
settings = config.get_settings(CrackerjackSettings)

# Access settings
print(settings.testing.test_workers)
```

### 3.3. Step 3: Simplify Dynamic Configuration

The `dynamic_config.py` module can be simplified by using `acb` to manage tool configurations. Instead of generating a pre-commit configuration file, you can define the tool configurations in `pyproject.toml` and use `acb` to load them.

**Example `pyproject.toml`:**

```toml
[tool.crackerjack.hooks.ruff]
command = "ruff"
args = ["--fix"]

[tool.crackerjack.hooks.bandit]
command = "bandit"
args = ["-c", "pyproject.toml", "-r", "-ll"]
```

You can then load this configuration using `acb`:

```python
from acb.depends import depends
from acb.config import Config

config = depends.get(Config)
ruff_config = config.get("hooks.ruff")
```

### 3.4. Step 4: Adopt Dependency Injection

Finally, use `@depends.inject` to provide configuration to services and components.

**Example:**

```python
from acb.depends import depends
from crackerjack.config.settings import CrackerjackSettings

@depends.inject
def my_service(settings: CrackerjackSettings = depends()):
    # Use settings
    print(settings.testing.test_timeout)
```

## 4. Migration Plan

This section outlines a proposed plan for migrating to the new configuration system.

### 4.1. Phase 1: Foundational Setup (Completed)

1.  **Create `CrackerjackSettings`:** Create the `crackerjack/config/settings.py` file with the `CrackerjackSettings` class as defined in section 3.1.
2.  **Integrate `acb.config`:** In the main application entry point, initialize `acb` and load the `CrackerjackSettings`.
3.  **Provide `CrackerjackSettings`:** Make the `CrackerjackSettings` instance available via `depends.set()`.

### 4.2. Phase 2: Incremental Refactoring (Completed)

1.  **Refactor `UnifiedConfigurationService`:** Replace the logic in `UnifiedConfigurationService` to use the `CrackerjackSettings` from `acb`.
2.  **Refactor `OrchestrationConfig`:** Replace the `OrchestrationConfig` class with the `CrackerjackSettings`.
3.  **Refactor `GlobalLockConfig`:** Replace the `GlobalLockConfig` class with the `GlobalLockSettings` from `CrackerjackSettings`.
4.  **Refactor `WorkflowOptions`:** Replace the `WorkflowOptions` class with the `CrackerjackSettings`.

### 4.3. Phase 3: Dynamic Configuration (Completed)

1.  **Refactor `dynamic_config.py`:** Refactor the `dynamic_config.py` module to use `acb` to load tool configurations from `pyproject.toml`.
2.  **Update `pyproject.toml`:** Add the tool configurations to `pyproject.toml`.

### 4.4. Phase 4: Data Access (Completed)

1.  **Adopt ACB Universal Query Interface:** Refactor the data repositories in `crackerjack/data/repository.py` to use `acb`'s universal query interface.

### 4.5. Phase 5: Utilities (Completed)

1.  **Implement ACB Actions for Utilities:** Refactor the utility tools in `crackerjack/mcp/tools/utility_tools.py` to use `acb.actions`.

### 4.6. Phase 6: Event-Driven Orchestration (Completed)

1.  **Integrate `acb.events.EventBus`:** Initialize the `EventBus` in the main application entry point and make it available via `depends.set()`.
2.  **Define Event Handlers:** Create event handlers for each `WorkflowEvent` in the `PhaseCoordinator` and `SessionCoordinator`.
3.  **Refactor `WorkflowPipeline`:** Refactor the `WorkflowPipeline` to dispatch events instead of calling coordinator methods directly.
4.  **Remove Manual Event Handling:** Remove the `_run_event_driven_workflow` method and the manual event handling logic.

### 4.7. Phase 7: Adapter System (Completed)

1.  **Update Base Adapter Classes:** The `QAAdapterBase` and `BaseToolAdapter` classes have been updated to be fully `acb`-compliant.

## 5. Conclusion

By following the recommendations in this report, the Crackerjack project has significantly improved its configuration, orchestration, adapter, data access, and utility systems. This has lead to a more maintainable, scalable, and robust application. The adoption of `acb.config.Settings`, `acb.events.EventBus`, `acb.adapters.AdapterMetadata`, `acb`'s universal query interface, and `acb.actions` has not only simplified the codebase but also enabled the project to take full advantage of the `acb` framework.
