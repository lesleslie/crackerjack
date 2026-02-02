"""Architectural compliance tests to prevent protocol-based design drift.

These tests enforce crackerjack's protocol-based architecture by ensuring:
1. Only protocol types are imported from crackerjack.models.protocols
2. Constructor injection is used for dependencies
3. No global singletons in production code
4. Proper protocol usage throughout the codebase

Run with: pytest tests/test_architectural_compliance.py -v
"""

import ast
from pathlib import Path

import pytest


class ImportProtocolVisitor(ast.NodeVisitor):
    """AST visitor to detect non-protocol imports from crackerjack modules."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.violations: list[str] = []
        self.protocol_imports: set[str] = set()
        self.concrete_imports: set[str] = set()

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit import statements to check for protocol violations."""
        if node.module and node.module.startswith("crackerjack"):
            # Track protocol imports
            if node.module == "crackerjack.models.protocols":
                for alias in node.names:
                    self.protocol_imports.add(alias.name)

            # Check for concrete class imports from other crackerjack modules
            elif not node.module.endswith(".protocols"):
                for alias in node.names:
                    import_name = alias.name
                    # Allow TYPE_CHECKING imports (for type hints only)
                    if not self._is_in_type_checking_block(node):
                        # Check if it's a concrete class import (not a protocol)
                        if import_name[0].isupper() and not import_name.endswith(
                            "Protocol"
                        ):
                            # Check if exception is allowed
                            if not self._is_exception_allowed(import_name):
                                self.concrete_imports.add(import_name)
                                violation = (
                                    f"{self.file_path}:{node.lineno}: "
                                    f"Direct import of concrete class '{import_name}' "
                                    f"from '{node.module}'. "
                                    f"Use protocol from models.protocols instead."
                                )
                                self.violations.append(violation)

        self.generic_visit(node)

    def _is_in_type_checking_block(self, node: ast.ImportFrom) -> bool:
        """Check if import is inside a TYPE_CHECKING block."""
        # This is a simplified check - in production, would need more sophisticated
        # analysis to detect TYPE_CHECKING guards
        return False

    def _allowed_exceptions(self) -> set[str]:
        """Return allowed concrete class imports.

        These are exceptions where concrete classes are acceptable:
        - Test fixtures
        - Protocol implementations
        - Data models/DTOs
        - Exceptions
        - Configuration classes
        - Factory implementations
        - Domain models (agents, issues, etc.)
        - Adapter implementations (factories need to import concrete classes)
        """
        return {
            "BaseModel",
            "BaseSettings",
            "Field",
            "HTTPException",
            "CrackerjackError",
            "PluginBase",
            "PluginMetadata",
            "PluginType",
            "HookStage",
            "Issue",
            "FixResult",
            "IssueType",
            "IssueSeverity",
            "AgentContext",
            "QAResult",
            "HookResult",
            "ChangelogEntry",
            "ExecutionRequest",
            "ExecutionResult",
            "SmartAgentResult",
            "TaskDescription",
            "TaskContext",
            # Configuration and data transfer objects
            "CrackerjackSettings",
            "RuntimeHealthSnapshot",
            # Factory implementations (allowed in constructors)
            "DefaultAdapterFactory",
            # Agent system domain models
            "SubAgent",
            # Tracking and debugging (concrete implementations acceptable)
            "AgentTracker",
            "CrackerjackCache",
            "AIAgentDebugger",
            "NoOpDebugger",
            # Adapter implementations (factories need these)
            # Allow all *Adapter classes
            # Allow ExecutionContext
        }

    def _is_adapter_class(self, class_name: str) -> bool:
        """Check if class name is an adapter implementation."""
        return (
            class_name.endswith("Adapter")
            or class_name.endswith("Fixer")
            or "CodeFixer" in class_name
        )

    def _is_exception_allowed(self, import_name: str) -> bool:
        """Check if import should be allowed as exception."""
        # Check standard exceptions
        if import_name in self._allowed_exceptions():
            return True

        # Allow adapter classes (factories need them)
        if self._is_adapter_class(import_name):
            return True

        # Allow ExecutionContext
        if import_name == "ExecutionContext":
            return True

        return False


class SingletonPatternVisitor(ast.NodeVisitor):
    """AST visitor to detect global singleton patterns."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.violations: list[str] = []
        self.has_singleton = False

    def visit_Assign(self, node: ast.Assign) -> None:
        """Check for module-level singleton assignments."""
        # Look for patterns like: _instance = ClassName()
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.id.startswith("_") and isinstance(
                    node.value, ast.Call
                ):
                    # Potential singleton instance
                    violation = (
                        f"{self.file_path}:{node.lineno}: "
                        f"Module-level singleton detected: '{target.id}'. "
                        f"Use constructor injection instead."
                    )
                    self.violations.append(violation)
                    self.has_singleton = True

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check for singleton getter functions."""
        # Look for patterns like: def get_singleton() -> SingletonType:
        if node.name.startswith("get_") and node.returns:
            # Check if function name matches pattern "get_*"
            # and returns a singleton type
            if isinstance(node.returns, ast.Name):
                return_type = node.returns.id
                if (
                    "Registry" in return_type
                    or "Manager" in return_type
                    or "Service" in return_type
                ):
                    violation = (
                        f"{self.file_path}:{node.lineno}: "
                        f"Singleton getter function detected: '{node.name}'. "
                        f"Use constructor injection instead."
                    )
                    self.violations.append(violation)

        self.generic_visit(node)


def check_file_for_violations(file_path: Path) -> list[str]:
    """Check a single file for architectural violations."""
    violations: list[str] = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=str(file_path))

        # Check for import protocol violations
        import_visitor = ImportProtocolVisitor(file_path)
        import_visitor.visit(tree)
        violations.extend(import_visitor.violations)

        # Check for singleton patterns (skip test files)
        if "test" not in str(file_path):
            singleton_visitor = SingletonPatternVisitor(file_path)
            singleton_visitor.visit(tree)
            violations.extend(singleton_visitor.violations)

    except SyntaxError:
        # Skip files with syntax errors (will be caught by other tests)
        pass

    return violations


@pytest.mark.parametrize(
    "file_path",
    [
        pytest.param(file, id=str(file))
        for file in Path("crackerjack").rglob("*.py")
        if "__pycache__" not in str(file)
    ],
)
def test_architectural_compliance(file_path: Path) -> None:
    """Test that all crackerjack modules follow protocol-based architecture."""
    violations = check_file_for_violations(file_path)

    # Allow certain files to have violations (test files, __init__.py files, etc.)
    if _is_exemption_allowed(file_path):
        return

    if violations:
        pytest.fail(
            f"Architectural violations found in {file_path}:\n"
            + "\n".join(violations)
        )


def test_protocols_file_complete() -> None:
    """Test that all protocols referenced in code are defined."""
    protocols_file = Path("crackerjack/models/protocols.py")

    with open(protocols_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse protocols from the file
    tree = ast.parse(content)
    defined_protocols = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and node.name.endswith("Protocol")
    }

    # Check for common required protocols
    required_protocols = {
        "AdapterProtocol",
        "AdapterFactoryProtocol",
        "AgentCoordinatorProtocol",
        "AgentTrackerProtocol",
        "DebuggerProtocol",
        "PluginRegistryProtocol",
        "AgentRegistryProtocol",
    }

    missing_protocols = required_protocols - defined_protocols

    if missing_protocols:
        pytest.fail(
            f"Missing required protocols in models/protocols.py: {missing_protocols}"
        )


def test_no_direct_class_instantiation_in_managers() -> None:
    """Test that manager classes use constructor injection for dependencies."""
    manager_files = list(Path("crackerjack/managers").rglob("*.py"))
    violations: list[str] = []

    for file_path in manager_files:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check __init__ method
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                        # Look for direct instantiation in __init__
                        for subnode in ast.walk(item):
                            if isinstance(subnode, ast.Call):
                                if isinstance(subnode.func, ast.Name):
                                    # Direct instantiation: ClassName()
                                    if subnode.func.id[0].isupper():
                                        violations.append(
                                            f"{file_path}:{subnode.lineno}: "
                                            f"Direct instantiation of '{subnode.func.id}' "
                                            f"in {node.name}.__init__. "
                                            f"Use constructor injection instead."
                                        )

    if violations:
        pytest.fail(
            "Direct class instantiation found in managers:\n"
            + "\n".join(violations)
        )


def _is_exemption_allowed(file_path: Path) -> bool:
    """Check if file is exempt from architectural compliance checks.

    Exemptions:
    - Test files
    - __init__.py files (for module organization)
    - conftest.py files
    - Adapter implementations (they import concrete base classes by design)
    - CLI handlers (allowed for now, gradual migration)
    - MCP tools (allowed for now, gradual migration)
    - Agent helpers (allowed for now, gradual migration)
    - Pattern services (utility modules, low priority)
    """
    parts = file_path.parts
    path_str = str(file_path)

    # Test files
    if "test" in parts:
        return True

    # Module organization
    if file_path.name == "__init__.py" or file_path.name == "conftest.py":
        return True

    # Allowed directories for gradual migration
    exempt_patterns = [
        "adapters",  # Adapter implementations
        "cli/handlers",  # CLI handlers
        "mcp/tools",  # MCP tool implementations
        "agents/helpers",  # Agent helper utilities
        "services/patterns",  # Pattern detection utilities
        "services/memory_optimizer",
        "services/bounded_status_operations",
        "services/secure_path_utils",
        "services/config_service",
        "services/input_validator",
        "services/unified_config",
        "services/coverage_ratchet",
        "services/quality",
        "services/ai",
    ]

    if any(pattern in path_str for pattern in exempt_patterns):
        return True

    if ".pytest_cache" in parts:
        return True

    return False


def test_critical_files_compliance() -> None:
    """Test critical files for strict architectural compliance."""
    critical_files = [
        Path("crackerjack/server.py"),
        Path("crackerjack/agents/coordinator.py"),
        Path("crackerjack/adapters/factory.py"),
        Path("crackerjack/plugins/loader.py"),
        Path("crackerjack/plugins/managers.py"),
    ]

    for file_path in critical_files:
        if not file_path.exists():
            continue

        violations = check_file_for_violations(file_path)

        if violations:
            pytest.fail(
                f"Critical file {file_path} has architectural violations:\n"
                + "\n".join(violations)
            )


if __name__ == "__main__":
    # Run tests on specific file
    import sys

    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
        violations = check_file_for_violations(file_path)
        if violations:
            print(f"❌ Violations in {file_path}:")
            for violation in violations:
                print(f"  {violation}")
            sys.exit(1)
        else:
            print(f"✅ {file_path} is compliant")
            sys.exit(0)
