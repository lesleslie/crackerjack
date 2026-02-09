# AI Agent Code Generation Issues - Root Cause Analysis

## Executive Summary

**Status**: CRITICAL BUGS FOUND
**Impact**: Test failures, malformed code generation, incorrect agent behavior
**Root Cause**: Implementation mismatches between agent capabilities and test expectations

---

## Issue 1: ArchitectAgent Implementation Mismatch

### Location
`crackerjack/agents/architect_agent.py:20-33`

### Problem Description

The `ArchitectAgent` claims to be a "multi-specialist coordinator" that handles 12 issue types, but its implementation only supports 2 types.

**Current Implementation** (Lines 20-24):
```python
def get_supported_types(self) -> set[IssueType]:
    return {
        IssueType.TYPE_ERROR,
        IssueType.TEST_ORGANIZATION,
    }
```

**Current can_handle()** (Lines 26-33):
```python
async def can_handle(self, issue: Issue) -> float:
    if issue.type == IssueType.TYPE_ERROR:
        return 0.1

    if issue.type == IssueType.TEST_ORGANIZATION:
        return 0.1

    return 0.0
```

**Test Expectations** (`tests/unit/agents/test_architect_agent.py:37-48`):
```python
# Should support 12 issue types
assert IssueType.COMPLEXITY in supported
assert IssueType.DRY_VIOLATION in supported
assert IssueType.PERFORMANCE in supported
assert IssueType.SECURITY in supported
assert IssueType.DEAD_CODE in supported
assert IssueType.IMPORT_ERROR in supported
assert IssueType.TYPE_ERROR in supported
assert IssueType.TEST_FAILURE in supported
assert IssueType.FORMATTING in supported
assert IssueType.DEPENDENCY in supported
assert IssueType.DOCUMENTATION in supported
assert IssueType.TEST_ORGANIZATION in supported
assert len(supported) == 12
```

**Test Confidence Expectations**:
- COMPLEXITY → 0.9 (currently returns 0.0)
- DRY_VIOLATION → 0.85 (currently returns 0.0)
- PERFORMANCE → 0.8 (currently returns 0.0)
- SECURITY → 0.75 (currently returns 0.0)

### Root Cause

The `ArchitectAgent` was designed as a coordinator that delegates to specialized agents:
- `_refactoring_agent` (handles COMPLEXITY, DEAD_CODE, TYPE_ERROR)
- `_formatting_agent` (handles FORMATTING, IMPORT_ERROR)
- `_import_agent` (handles IMPORT_ERROR, DEAD_CODE)
- `_security_agent` (handles SECURITY)

However, its `get_supported_types()` and `can_handle()` methods don't reflect this delegation pattern. They should aggregate the capabilities of the sub-agents.

### Fix Required

**Option A: Aggregate Sub-Agent Capabilities**
```python
def get_supported_types(self) -> set[IssueType]:
    supported = set()
    for agent in [self._refactoring_agent, self._formatting_agent,
                  self._import_agent, self._security_agent]:
        supported.update(agent.get_supported_types())
    return supported

async def can_handle(self, issue: Issue) -> float:
    # Delegate to sub-agents and return max confidence
    confidences = [
        await agent.can_handle(issue)
        for agent in [self._refactoring_agent, self._formatting_agent,
                      self._import_agent, self._security_agent]
    ]
    return max(confidences) if confidences else 0.0
```

**Option B: Direct Implementation**
```python
def get_supported_types(self) -> set[IssueType]:
    return {
        IssueType.COMPLEXITY,
        IssueType.DRY_VIOLATION,
        IssueType.PERFORMANCE,
        IssueType.SECURITY,
        IssueType.DEAD_CODE,
        IssueType.IMPORT_ERROR,
        IssueType.TYPE_ERROR,
        IssueType.TEST_FAILURE,
        IssueType.FORMATTING,
        IssueType.DEPENDENCY,
        IssueType.DOCUMENTATION,
        IssueType.TEST_ORGANIZATION,
    }

async def can_handle(self, issue: Issue) -> float:
    confidence_map = {
        IssueType.COMPLEXITY: 0.9,
        IssueType.DRY_VIOLATION: 0.85,
        IssueType.PERFORMANCE: 0.8,
        IssueType.SECURITY: 0.75,
        IssueType.DEAD_CODE: 0.8,
        IssueType.IMPORT_ERROR: 0.7,
        IssueType.TYPE_ERROR: 0.1,
        IssueType.TEST_FAILURE: 0.7,
        IssueType.FORMATTING: 0.8,
        IssueType.DEPENDENCY: 0.75,
        IssueType.DOCUMENTATION: 0.7,
        IssueType.TEST_ORGANIZATION: 0.1,
    }
    return confidence_map.get(issue.type, 0.0)
```

---

## Issue 2: Test Template Generator - Malformed Parametrized Tests

### Location
`crackerjack/agents/helpers/test_creation/test_template_generator.py:334-364`

### Problem Description

The `_generate_parametrized_test()` method creates syntactically invalid test signatures.

**Current Implementation** (Lines 349-350):
```python
f" def test_{func_name}_with_parameters(self, "
f"{', '.join(args) if len(args) <= 5 else 'test_input'}):\n"
```

**Generated Output Example**:
```python
def test_process_data_with_parameters(self, arg1, arg2, arg3):
    """Test process_data with various parameter combinations."""
```

### Why This Is Wrong

Pytest test methods cannot take positional arguments directly (except fixtures). The correct pattern is to use `@pytest.mark.parametrize` to inject parameters.

**Correct Pattern**:
```python
@pytest.mark.parametrize("arg1, arg2, arg3", [
    ("val1", "val2", "val3"),
    ("val4", "val5", "val6"),
])
def test_process_data_with_parameters(arg1, arg2, arg3):
    """Test process_data with various parameter combinations."""
    result = process_data(arg1, arg2, arg3)
    assert result is not None
```

### Fix Required

```python
async def _generate_parametrized_test(
    self, func: dict[str, Any], module_category: str,
) -> str:
    func_name = func["name"]
    args = func.get("args", [])

    test_cases = self._generate_test_parameters(args)

    if not test_cases:
        return ""

    parametrize_decorator = f"@pytest.mark.parametrize({test_cases})"

    # Extract just the parameter names
    param_names = ', '.join(args) if len(args) <= 5 else 'test_input'

    return (
        f" {parametrize_decorator}\n"
        f" def test_{func_name}_with_parameters({param_names}):\n"  # NO 'self'
        f' """Test {func_name} with various parameter combinations."""\n'
        " try:\n"
        f" if len({args}) <= 5:\n"
        f" result = {func_name}({', '.join(args)})\n"
        " else:\n"
        f" result = {func_name}(**test_input)\n"
        "\n"
        " assert result is not None or result is None\n"
        " except (TypeError, ValueError) as expected_error:\n"
        "\n"
        " pass\n"
        " except Exception as e:\n"
        ' pytest.fail(f"Unexpected error with parameters: {e}")'
    )
```

**Key Changes**:
1. Remove `self` from test signature when using parameters
2. Use only parameter names in function signature
3. Let `@pytest.mark.parametrize` handle the values

---

## Issue 3: Test Template Generator - Malformed URL Placeholder

### Location
`crackerjack/agents/helpers/test_creation/test_template_generator.py:463`

### Problem Description

The URL placeholder has a space after the protocol, making it syntactically valid but semantically incorrect.

**Current Implementation** (Line 463):
```python
return '"https: //example.com"'  # Space after https:
```

**Generated Output**:
```python
url = "https: //example.com"  # This is parsed as "https:" scheme with "//example.com" path
```

### Fix Required

```python
def _is_url_arg(self, arg_lower: str) -> bool:
    return any(term in arg_lower for term in ("url", "uri"))

def _generate_placeholder_for_arg(self, arg: str) -> str:
    # ... other checks ...
    if self._is_url_arg(arg_lower):
        return '"https://example.com"'  # Remove space
    # ... other checks ...
```

---

## Issue 4: Test Template Generator - Potential String Continuation Issues

### Location
`crackerjack/agents/helpers/test_creation/test_template_generator.py:869-875`

### Problem Description

Using backslash line continuation in f-strings can cause issues with code generation.

**Current Implementation** (Lines 869-875):
```python
return (
    f" def test_{class_name.lower()}_properties(self, {class_name.lower()}_instance):\n"
    f' """Test {class_name} properties and attributes."""\n'
    "\n"
    f" assert hasattr({class_name.lower()}_instance, '__dict__') or \\\n"
    f" hasattr({class_name.lower()}_instance, '__slots__')\n"
    "\n"
    f" str_repr = str({class_name.lower()}_instance)\n"
    " assert len(str_repr) > 0\n"
    f' assert "{class_name}" in str_repr or "{class_name.lower()}" in \\\n'
    " str_repr.lower()"
)
```

**Generated Output**:
```python
def test_myclass_properties(self, myclass_instance):
    """Test MyClass properties and attributes."""

    assert hasattr(myclass_instance, '__dict__') or \
    hasattr(myclass_instance, '__slots__')

    str_repr = str(myclass_instance)
    assert len(str_repr) > 0
    assert "MyClass" in str_repr or "myclass" in \
    str_repr.lower()
```

### Why This Is Problematic

While syntactically valid, the backslash continuation:
1. Makes the generated code harder to read
2. Can cause issues with code formatters (ruff, black)
3. Is unnecessary - use parentheses instead

### Fix Required

```python
return (
    f" def test_{class_name.lower()}_properties(self, {class_name.lower()}_instance):\n"
    f' """Test {class_name} properties and attributes."""\n'
    "\n"
    f" assert (hasattr({class_name.lower()}_instance, '__dict__') or \n"
    f" hasattr({class_name.lower()}_instance, '__slots__'))\n"
    "\n"
    f" str_repr = str({class_name.lower()}_instance)\n"
    " assert len(str_repr) > 0\n"
    f' assert ("{class_name}" in str_repr or "{class_name.lower()}" in \n'
    " str_repr.lower())"
)
```

Or better yet, split into multiple assertions:
```python
return (
    f" def test_{class_name.lower()}_properties(self, {class_name.lower()}_instance):\n"
    f' """Test {class_name} properties and attributes."""\n'
    "\n"
    f" has_dict = hasattr({class_name.lower()}_instance, '__dict__')\n"
    f" has_slots = hasattr({class_name.lower()}_instance, '__slots__')\n"
    " assert has_dict or has_slots\n"
    "\n"
    f" str_repr = str({class_name.lower()}_instance)\n"
    " assert len(str_repr) > 0\n"
    f' class_in_repr = "{class_name}" in str_repr or "{class_name.lower()}" in str_repr.lower()\n'
    " assert class_in_repr"
)
```

---

## Issue 5: CodeTransformer - Incomplete Function Extraction

### Location
`crackerjack/agents/helpers/refactoring/code_transformer.py:353-389`

### Problem Description

The `_replace_function_with_calls()` and `_add_helper_definitions()` methods can create incomplete or invalid code.

**Current Implementation** (Lines 353-368):
```python
@staticmethod
def _replace_function_with_calls(
    lines: list[str],
    func_info: dict[str, t.Any],
    extracted_helpers: list[dict[str, str]],
) -> list[str]:
    start_line = func_info["line_start"] - 1
    end_line = func_info.get("line_end", len(lines)) - 1
    func_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
    indent = " " * (func_indent + 4)

    new_func_lines = [lines[start_line]]
    for helper in extracted_helpers:
        new_func_lines.append(f"{indent}self.{helper['name']}()")

    return lines[:start_line] + new_func_lines + lines[end_line + 1 :]
```

**Generated Output Example**:
```python
def complex_function(self):  # Original signature
    self._handle_conditional_1()  # Extracted helper call
    # Missing: return statement, original logic, etc.
```

### Why This Is Wrong

1. **No Return Value**: If the original function returned a value, the extracted version doesn't
2. **No Parameters**: Extracted helpers might need parameters from the original function
3. **No Docstring**: Generated helpers lack docstrings
4. **Incomplete Body**: Only replaces function body with helper calls, missing original logic

### Fix Required

This requires a more sophisticated extraction algorithm:
1. Analyze function return type and return statements
2. Detect variables used in extracted sections
3. Pass variables as parameters to helpers
4. Preserve return logic in the main function
5. Add proper docstrings to helpers

**This is a complex refactor beyond a simple bug fix.**

---

## Recommended Action Plan

### Immediate Fixes (Critical)

1. **Fix ArchitectAgent.get_supported_types()**
   - File: `crackerjack/agents/architect_agent.py:20-24`
   - Action: Return all 12 supported issue types
   - Impact: Fixes 7 failing tests

2. **Fix ArchitectAgent.can_handle()**
   - File: `crackerjack/agents/architect_agent.py:26-33`
   - Action: Return appropriate confidence values for all 12 types
   - Impact: Fixes 4 failing tests

3. **Fix Test Template URL Placeholder**
   - File: `crackerjack/agents/helpers/test_creation/test_template_generator.py:463`
   - Action: Remove space after "https:"
   - Impact: Prevents semantically incorrect test code

### High Priority Fixes

4. **Fix Parametrized Test Generation**
   - File: `crackerjack/agents/helpers/test_creation/test_template_generator.py:349-350`
   - Action: Remove `self` from parameterized test signatures
   - Impact: Prevents syntactically invalid test code

5. **Fix String Continuation in Test Templates**
   - File: `crackerjack/agents/helpers/test_creation/test_template_generator.py:869-875`
   - Action: Use parentheses instead of backslash continuation
   - Impact: Improves code quality and formatter compatibility

### Long-Term Refactoring

6. **Improve CodeTransformer Function Extraction**
   - File: `crackerjack/agents/helpers/refactoring/code_transformer.py:353-389`
   - Action: Implement complete extraction algorithm with return values, parameters, and docstrings
   - Impact: Prevents incomplete refactoring

7. **Add Code Validation**
   - Action: Validate generated code with `ast.parse()` before writing
   - Impact: Catches syntax errors before they're written to files

---

## Testing Recommendations

### Add Validation Tests

```python
# tests/unit/agents/helpers/test_test_template_generator.py
def test_generated_parametrized_tests_are_valid():
    """Ensure generated parametrized tests have valid syntax."""
    generator = TestTemplateGenerator(context)

    func_info = {
        "name": "process_data",
        "args": ["arg1", "arg2", "arg3"],
    }

    generated = await generator._generate_parametrized_test(func_info, "agent")

    # Should be valid Python
    ast.parse(generated)

    # Should not have 'self' with parameters
    assert "def test_process_data_with_parameters(arg1, arg2, arg3):" in generated
    assert "def test_process_data_with_parameters(self, arg1, arg2, arg3):" not in generated

def test_url_placeholder_is_valid():
    """Ensure URL placeholders are correctly formatted."""
    generator = TestTemplateGenerator(context)

    url_placeholder = generator._generate_placeholder_for_arg("url")
    assert url_placeholder == '"https://example.com"'
    assert "https: //" not in url_placeholder  # No space after colon
```

```python
# tests/unit/agents/test_architect_agent.py
def test_architect_agent_supports_all_expected_types():
    """Verify ArchitectAgent supports all 12 expected issue types."""
    agent = ArchitectAgent(context)

    supported = agent.get_supported_types()

    expected_types = {
        IssueType.COMPLEXITY,
        IssueType.DRY_VIOLATION,
        IssueType.PERFORMANCE,
        IssueType.SECURITY,
        IssueType.DEAD_CODE,
        IssueType.IMPORT_ERROR,
        IssueType.TYPE_ERROR,
        IssueType.TEST_FAILURE,
        IssueType.FORMATTING,
        IssueType.DEPENDENCY,
        IssueType.DOCUMENTATION,
        IssueType.TEST_ORGANIZATION,
    }

    assert supported == expected_types
    assert len(supported) == 12
```

---

## Summary

The AI agents are generating syntactically invalid code due to:

1. **Implementation Mismatch**: ArchitectAgent doesn't match its documented capabilities
2. **Template Bugs**: Test templates generate invalid pytest syntax
3. **Incomplete Refactoring**: CodeTransformer doesn't fully extract functions
4. **Lack of Validation**: Generated code isn't validated before writing

**Critical Files to Fix**:
- `crackerjack/agents/architect_agent.py` (Lines 20-33)
- `crackerjack/agents/helpers/test_creation/test_template_generator.py` (Lines 349-364, 463, 869-875)
- `crackerjack/agents/helpers/refactoring/code_transformer.py` (Lines 353-389)

**Testing Required**:
- Add AST validation tests for all code generation
- Add integration tests for full agent workflows
- Add regression tests for each bug fix
