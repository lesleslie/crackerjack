"""Tests for crackerjack.fixers.test_creation.

Ported from tests/unit/agents/test_test_creation_agent.py, keeping only the
cases that exercise real AST-based scaffolding: function/class extraction
via ``ast.parse``/``ast.walk``, test-file-path/import-path derivation,
coverage-gap and module-priority analysis, and actual generated test-file
content (verified against the real generated text, not mocked). Cases
exercising ``SubAgent``/coordinator dispatch (``can_handle``,
``get_supported_types``, ``TestCreationAgent.__init__``) were dropped,
since that machinery no longer exists -- see the module docstring of
``crackerjack/fixers/test_creation.py`` for the full kept/dropped
rationale, including the pre-existing quirks/duplication preserved
verbatim (not fixed) per CLAUDE.md Rule 7.
"""

from __future__ import annotations

import ast

import pytest

from crackerjack.fixers import test_creation as tc
from crackerjack.models.issues import Issue, IssueType, Priority


def _issue(**kwargs: object) -> Issue:
    defaults: dict[str, object] = {
        "id": "tc-test",
        "type": IssueType.COVERAGE_IMPROVEMENT,
        "severity": Priority.HIGH,
        "message": "Missing tests",
    }
    defaults.update(kwargs)
    return Issue(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AST extraction (TestASTAnalyzer)
# ---------------------------------------------------------------------------


class TestExtractFunctionsFromFile:
    @pytest.mark.asyncio
    async def test_extracts_public_and_async_functions(self, tmp_path) -> None:
        module = tmp_path / "module.py"
        module.write_text(
            """
def public_function(arg1, arg2):
    pass

def _private_function():
    pass

async def async_function():
    pass

def test_something():
    pass
"""
        )

        functions = await tc.extract_functions_from_file(module)

        names = [f["name"] for f in functions]
        assert "public_function" in names
        assert "async_function" in names
        assert "_private_function" not in names
        assert "test_something" not in names

        async_func = next(f for f in functions if f["name"] == "async_function")
        assert async_func["is_async"] is True

        public_func = next(f for f in functions if f["name"] == "public_function")
        assert public_func["args"] == ["arg1", "arg2"]
        assert public_func["signature"] == "public_function(arg1, arg2)"

    @pytest.mark.asyncio
    async def test_missing_file_returns_empty(self, tmp_path) -> None:
        functions = await tc.extract_functions_from_file(tmp_path / "nope.py")

        assert functions == []

    @pytest.mark.asyncio
    async def test_unparseable_file_returns_empty(self, tmp_path) -> None:
        module = tmp_path / "broken.py"
        module.write_text("def broken(:\n")

        functions = await tc.extract_functions_from_file(module)

        assert functions == []


class TestExtractClassesFromFile:
    @pytest.mark.asyncio
    async def test_extracts_public_class_with_public_methods(self, tmp_path) -> None:
        module = tmp_path / "module.py"
        module.write_text(
            """
class PublicClass:
    def method1(self): pass
    def method2(self): pass
    def _private_method(self): pass

class _PrivateClass:
    pass
"""
        )

        classes = await tc.extract_classes_from_file(module)

        assert len(classes) == 1
        assert classes[0]["name"] == "PublicClass"
        assert "method1" in classes[0]["methods"]
        assert "method2" in classes[0]["methods"]
        assert "_private_method" not in classes[0]["methods"]


class TestASTNodeHelpers:
    def test_parse_function_nodes_finds_public_only(self) -> None:
        tree = ast.parse(
            """
def regular_function(arg1, arg2):
    pass

async def async_function():
    pass

def _private_function():
    pass
"""
        )

        functions = tc._parse_function_nodes(tree)

        assert len(functions) == 2
        assert any(f["name"] == "regular_function" for f in functions)
        assert any(f["is_async"] for f in functions)

    def test_is_valid_function_node(self) -> None:
        public = ast.parse("def public_func(): pass").body[0]
        private = ast.parse("def _private_func(): pass").body[0]
        test_fn = ast.parse("def test_something(): pass").body[0]

        assert tc._is_valid_function_node(public) is True
        assert tc._is_valid_function_node(private) is False
        assert tc._is_valid_function_node(test_fn) is False

    def test_create_function_info(self) -> None:
        tree = ast.parse(
            '''
async def process_data(input_data, config):
    """Process data with config."""
    return None
'''
        )
        node = tree.body[0]

        info = tc._create_function_info(node)

        assert info["name"] == "process_data"
        assert info["args"] == ["input_data", "config"]
        assert info["is_async"] is True
        assert info["docstring"] == "Process data with config."

    def test_get_function_signature(self) -> None:
        node = ast.parse("async def process(data, options): pass").body[0]

        signature = tc._get_function_signature(node)

        assert signature == "async process(data, options)"


# ---------------------------------------------------------------------------
# Path / import-path / skip-check helpers
# ---------------------------------------------------------------------------


class TestPathHelpers:
    @pytest.mark.asyncio
    async def test_generate_test_file_path(self, tmp_path) -> None:
        source_file = tmp_path / "crackerjack" / "services" / "config.py"
        source_file.parent.mkdir(parents=True)

        test_path = await tc.generate_test_file_path(source_file, tmp_path)

        assert test_path.name == "test_config.py"
        assert test_path.parent == tmp_path / "tests"

    @pytest.mark.asyncio
    async def test_generate_test_file_path_creates_tests_dir(self, tmp_path) -> None:
        # Preserved quirk: computing the path alone creates tests/ as a
        # side effect, even before any file is written there.
        source_file = tmp_path / "crackerjack" / "config.py"
        source_file.parent.mkdir(parents=True)
        assert not (tmp_path / "tests").exists()

        await tc.generate_test_file_path(source_file, tmp_path)

        assert (tmp_path / "tests").is_dir()

    def test_get_module_import_path(self, tmp_path) -> None:
        module_file = tmp_path / "crackerjack" / "services" / "config.py"

        import_path = tc._get_module_import_path(module_file, tmp_path)

        assert import_path == "crackerjack.services.config"

    def test_should_skip_module_for_coverage(self, tmp_path) -> None:
        assert tc.should_skip_module_for_coverage(tmp_path / "test_module.py") is True
        assert tc.should_skip_module_for_coverage(tmp_path / "__init__.py") is True
        assert tc.should_skip_module_for_coverage(tmp_path / "module.py") is False

    def test_should_skip_file_for_testing(self, tmp_path) -> None:
        assert tc.should_skip_file_for_testing(tmp_path / "test_module.py") is True
        assert tc.should_skip_file_for_testing(tmp_path / "module.py") is False

    def test_has_corresponding_test_found(self, tmp_path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_module.py").write_text("content")

        module_path = str(tmp_path / "crackerjack" / "module.py")

        assert tc.has_corresponding_test(module_path, tmp_path) is True

    def test_has_corresponding_test_not_found(self, tmp_path) -> None:
        module_path = str(tmp_path / "crackerjack" / "no_test_module.py")

        assert tc.has_corresponding_test(module_path, tmp_path) is False

    @pytest.mark.asyncio
    async def test_function_has_test_true(self, tmp_path) -> None:
        source_file = tmp_path / "crackerjack" / "module.py"
        source_file.parent.mkdir(parents=True)
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_module.py").write_text("def test_process(): pass")

        func_info = {"name": "process"}

        assert (
            await tc.function_has_test(func_info, source_file, tmp_path) is True
        )

    @pytest.mark.asyncio
    async def test_function_has_test_false(self, tmp_path) -> None:
        source_file = tmp_path / "crackerjack" / "module.py"
        source_file.parent.mkdir(parents=True)

        func_info = {"name": "process"}

        assert (
            await tc.function_has_test(func_info, source_file, tmp_path) is False
        )


class TestCategorizeModule:
    def test_categorize_module(self) -> None:
        assert tc._categorize_module("crackerjack/managers/test.py") == "manager"
        assert tc._categorize_module("crackerjack/services/test.py") == "service"
        assert tc._categorize_module("crackerjack/core/test.py") == "core"
        assert tc._categorize_module("crackerjack/agents/test.py") == "agent"
        assert tc._categorize_module("crackerjack/models/test.py") == "model"
        assert tc._categorize_module("crackerjack/executors/test.py") == "executor"
        assert tc._categorize_module("crackerjack/utils/test.py") == "utility"


# ---------------------------------------------------------------------------
# Template generation (TestTemplateGenerator) -- real generated text
# ---------------------------------------------------------------------------


class TestGenerateTestContent:
    @pytest.mark.asyncio
    async def test_generates_header_and_function_tests(self, tmp_path) -> None:
        module_file = tmp_path / "crackerjack" / "services" / "config.py"
        module_file.parent.mkdir(parents=True)
        module_file.write_text(
            """
def load_config(path):
    pass

def save_config(path, data):
    pass
"""
        )

        functions = await tc.extract_functions_from_file(module_file)
        classes = await tc.extract_classes_from_file(module_file)

        content = await tc.generate_test_content(
            module_file, functions, classes, tmp_path
        )

        assert "class TestConfig:" in content
        assert "def test_module_imports_successfully(self):" in content
        assert "import crackerjack.services.config" in content
        # service category -> async test template + asyncio import
        assert "import asyncio" in content
        assert "test_load_config_basic_functionality" in content
        assert "test_save_config_basic_functionality" in content
        # save_config has 2 args -> parametrized test generated
        assert "test_save_config_with_parameters" in content
        assert "test_load_config_error_handling" in content

    @pytest.mark.asyncio
    async def test_no_functions_or_classes_still_generates_header(
        self, tmp_path
    ) -> None:
        module_file = tmp_path / "crackerjack" / "utils" / "empty.py"
        module_file.parent.mkdir(parents=True)
        module_file.write_text("")

        content = await tc.generate_test_content(module_file, [], [], tmp_path)

        assert "class TestEmpty:" in content
        assert "test_module_imports_successfully" in content


class TestArgPlaceholderHelpers:
    def test_generate_smart_default_args_path(self) -> None:
        assert 'Path("test_file.txt")' in tc._generate_smart_default_args(
            ["file_path"]
        )

    def test_generate_smart_default_args_name(self) -> None:
        assert '"test_name"' in tc._generate_smart_default_args(["name"])

    def test_generate_smart_default_args_numeric(self) -> None:
        assert "10" in tc._generate_smart_default_args(["count"])

    def test_generate_smart_default_args_boolean(self) -> None:
        assert "True" in tc._generate_smart_default_args(["is_enabled"])

    def test_generate_smart_default_args_self_only(self) -> None:
        assert tc._generate_smart_default_args(["self"]) == ""

    def test_generate_invalid_args(self) -> None:
        assert tc._generate_invalid_args(["arg1", "arg2", "arg3"]) == "None, None, None"

    def test_generate_edge_case_args_empty(self) -> None:
        args = tc._generate_edge_case_args(["name", "data", "config"], "empty")

        assert '""' in args
        assert "[]" in args or "{}" in args

    def test_generate_edge_case_args_boundary(self) -> None:
        args = tc._generate_edge_case_args(["count", "name"], "boundary")

        assert "0" in args
        assert '"x" * 1000' in args

    def test_generate_edge_case_args_extreme(self) -> None:
        args = tc._generate_edge_case_args(["count"], "extreme")

        assert "-1" in args

    @pytest.mark.parametrize(
        ("checker", "arg", "expected"),
        [
            (tc._is_path_arg, "file_path", True),
            (tc._is_url_arg, "api_url", True),
            (tc._is_email_arg, "user_email", True),
            (tc._is_id_arg, "user_id", True),
            (tc._is_name_arg, "username", True),
            (tc._is_numeric_arg, "count", True),
            (tc._is_boolean_arg, "is_enabled", True),
            (tc._is_text_arg, "text_content", True),
            (tc._is_list_arg, "items", True),
            (tc._is_dict_arg, "config", True),
        ],
    )
    def test_arg_type_detectors(self, checker, arg, expected) -> None:
        assert checker(arg) is expected


# ---------------------------------------------------------------------------
# Coverage analysis (TestCoverageAnalyzer)
# ---------------------------------------------------------------------------


class TestParseCoverageJson:
    def test_parse_coverage_json(self, tmp_path) -> None:
        coverage_json = {
            "totals": {
                "percent_covered": 75.0,
                "num_statements": 500,
                "covered_lines": 375,
            },
            "files": {
                str(tmp_path / "low_coverage.py"): {
                    "summary": {"percent_covered": 60},
                },
            },
        }

        result = tc._parse_coverage_json(coverage_json, tmp_path)

        assert result["below_threshold"] is True
        assert result["current_coverage"] == 0.75
        assert result["missing_lines"] == 125


class TestEstimateCurrentCoverage:
    @pytest.mark.asyncio
    async def test_estimate_current_coverage(self, tmp_path) -> None:
        source_dir = tmp_path / "crackerjack"
        source_dir.mkdir()
        (source_dir / "module1.py").write_text("def foo(): pass")
        (source_dir / "module2.py").write_text("def bar(): pass")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_module1.py").write_text("def test_foo(): pass")

        coverage = await tc._estimate_current_coverage(tmp_path)

        assert isinstance(coverage, float)
        assert 0.0 <= coverage <= 0.9

    @pytest.mark.asyncio
    async def test_estimate_current_coverage_no_source(self, tmp_path) -> None:
        coverage = await tc._estimate_current_coverage(tmp_path)

        assert coverage == 0.0


class TestCalculateImprovementPotential:
    def test_high_potential(self) -> None:
        potential = tc._calculate_improvement_potential(10, 20)

        assert potential["priority"] == "high"
        assert potential["percentage_points"] > 15

    def test_medium_potential(self) -> None:
        potential = tc._calculate_improvement_potential(3, 5)

        assert potential["priority"] == "medium"

    def test_zero_potential(self) -> None:
        potential = tc._calculate_improvement_potential(0, 0)

        assert potential["priority"] == "low"
        assert potential["percentage_points"] == 0


class TestModulePriority:
    @pytest.mark.asyncio
    async def test_analyze_module_priority_base(self, tmp_path) -> None:
        module_file = tmp_path / "crackerjack" / "managers" / "hook_manager.py"
        module_file.parent.mkdir(parents=True)
        module_file.write_text(
            """
def public_function(): pass
def _private_function(): pass

class HookManager:
    def execute(self): pass
    def _internal(self): pass
"""
        )

        priority_info = await tc._analyze_module_priority(module_file, tmp_path)

        # ast.walk descends into the class body too, so `execute` (a public
        # method) is counted alongside the top-level `public_function` --
        # the base version has no notion of "top-level only".
        assert priority_info["priority_score"] > 0
        assert priority_info["function_count"] == 2
        assert priority_info["class_count"] == 1
        assert priority_info["public_function_count"] == 2
        assert priority_info["category"] == "manager"

    @pytest.mark.asyncio
    async def test_analyze_module_priority_override_recounts_top_level(
        self, tmp_path
    ) -> None:
        # The agent-level `analyze_module_priority` override independently
        # recomputes `public_function_count` via a fresh ast.parse/ast.walk
        # over top-level FunctionDef/AsyncFunctionDef nodes -- distinct from
        # (but here, coincidentally equal to) the base version's count.
        module_file = tmp_path / "crackerjack" / "services" / "svc.py"
        module_file.parent.mkdir(parents=True)
        module_file.write_text(
            """
def one(): pass
def two(): pass
async def three(): pass
def _hidden(): pass
"""
        )

        info = await tc.analyze_module_priority(module_file, tmp_path)

        assert info["public_function_count"] == 3
        assert info["category"] == "service"

    @pytest.mark.asyncio
    async def test_override_excludes_class_methods_unlike_base(self, tmp_path) -> None:
        # With a class present, the override (top-level-only, col_offset==0)
        # diverges from the base version (which counts class methods too).
        module_file = tmp_path / "crackerjack" / "managers" / "hook_manager.py"
        module_file.parent.mkdir(parents=True)
        module_file.write_text(
            """
def public_function(): pass
def _private_function(): pass

class HookManager:
    def execute(self): pass
    def _internal(self): pass
"""
        )

        base_info = await tc._analyze_module_priority(module_file, tmp_path)
        override_info = await tc.analyze_module_priority(module_file, tmp_path)

        assert base_info["public_function_count"] == 2
        assert override_info["public_function_count"] == 1


class TestAnalyzeFunctionTestability:
    @pytest.mark.asyncio
    async def test_complex_async_function_gets_high_priority(self, tmp_path) -> None:
        func_info = {
            "name": "process_data",
            "args": ["self", "data", "options", "config", "flags"],
            "is_async": True,
        }
        test_file = tmp_path / "crackerjack" / "services" / "processor.py"
        test_file.parent.mkdir(parents=True)

        result = await tc._analyze_function_testability(
            func_info, test_file, tmp_path
        )

        assert result["testing_priority"] > 0
        assert result["complexity"] == "complex"
        assert result["test_strategy"] == "async"


class TestCoverageGapAnalysis:
    @pytest.mark.asyncio
    async def test_analyze_existing_test_coverage_no_test_file(self, tmp_path) -> None:
        module_file = tmp_path / "crackerjack" / "module.py"
        module_file.parent.mkdir(parents=True)

        # coverage_analyzer version (used by the live pipeline)
        coverage_info = await tc._analyze_existing_test_coverage(module_file, tmp_path)

        assert coverage_info["has_gaps"] is True
        assert "basic" in coverage_info["missing_test_types"]

    @pytest.mark.asyncio
    async def test_analyze_existing_test_coverage_has_gaps_is_list_quirk(
        self, tmp_path
    ) -> None:
        # Preserved quirk: TestCoverageAnalyzer's `_analyze_existing_test_coverage`
        # assigns the *list* of missing test types to `has_gaps`, not a bool,
        # whenever a test file already exists.
        module_file = tmp_path / "crackerjack" / "module.py"
        module_file.parent.mkdir(parents=True)
        test_file = tmp_path / "tests" / "test_module.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("def test_basic(): pass")

        coverage_info = await tc._analyze_existing_test_coverage(module_file, tmp_path)

        assert coverage_info["has_gaps"] == coverage_info["missing_test_types"]
        assert isinstance(coverage_info["has_gaps"], list)
        assert coverage_info["has_gaps"] != []

    @pytest.mark.asyncio
    async def test_analyze_existing_test_coverage_agent_version_is_bool(
        self, tmp_path
    ) -> None:
        # The agent-level `analyze_existing_test_coverage` (no leading
        # underscore) computes a real bool, unlike the coverage_analyzer
        # version above.
        module_file = tmp_path / "crackerjack" / "module.py"
        module_file.parent.mkdir(parents=True)
        test_file = tmp_path / "tests" / "test_module.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("def test_basic(): pass")

        coverage_info = await tc.analyze_existing_test_coverage(module_file, tmp_path)

        assert coverage_info["has_gaps"] is True
        assert isinstance(coverage_info["has_gaps"], bool)

    @pytest.mark.asyncio
    async def test_identify_coverage_gaps_agent_version(self, tmp_path) -> None:
        package_dir = tmp_path / "crackerjack"
        package_dir.mkdir()
        (package_dir / "module.py").write_text("def process(): pass")

        gaps = await tc.identify_coverage_gaps(tmp_path)

        assert isinstance(gaps, list)
        assert len(gaps) == 1
        assert gaps[0]["has_gaps"] is True


# ---------------------------------------------------------------------------
# Test-creation orchestration -- verifies real files get written to disk
# ---------------------------------------------------------------------------


class TestCreateTestsForModule:
    @pytest.mark.asyncio
    async def test_creates_test_file_on_disk(self, tmp_path) -> None:
        module_file = tmp_path / "crackerjack" / "services" / "config.py"
        module_file.parent.mkdir(parents=True)
        module_file.write_text(
            """
def load_config(path):
    pass
"""
        )

        result = await tc.create_tests_for_module(str(module_file), tmp_path)

        assert result["fixes"] == [f"Created test file for {module_file}"]
        assert len(result["files"]) == 1

        test_file = tmp_path / "tests" / "test_config.py"
        assert test_file.exists()
        content = test_file.read_text()
        assert "test_load_config_basic_functionality" in content

    @pytest.mark.asyncio
    async def test_missing_module_produces_no_fixes(self, tmp_path) -> None:
        result = await tc.create_tests_for_module(
            str(tmp_path / "crackerjack" / "nope.py"), tmp_path
        )

        assert result == {"fixes": [], "files": []}

    @pytest.mark.asyncio
    async def test_module_with_no_functions_or_classes_skipped(self, tmp_path) -> None:
        module_file = tmp_path / "crackerjack" / "empty.py"
        module_file.parent.mkdir(parents=True)
        module_file.write_text("x = 1\n")

        result = await tc.create_tests_for_module(str(module_file), tmp_path)

        assert result == {"fixes": [], "files": []}


class TestCreateTestsForFile:
    @pytest.mark.asyncio
    async def test_skips_when_corresponding_test_exists(self, tmp_path) -> None:
        module_file = tmp_path / "crackerjack" / "module.py"
        module_file.parent.mkdir(parents=True)
        module_file.write_text("def process(): pass")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_module.py").write_text("existing")

        result = await tc.create_tests_for_file(str(module_file), tmp_path)

        assert result == {"fixes": [], "files": []}


class TestCreateTestForFunction:
    @pytest.mark.asyncio
    async def test_creates_new_test_file(self, tmp_path) -> None:
        source_file = tmp_path / "crackerjack" / "module.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("def process(data): pass")

        func_info = {"name": "process", "file": str(source_file), "args": ["data"]}

        result = await tc.create_test_for_function(func_info, tmp_path)

        assert len(result["files"]) == 1
        test_file = tmp_path / "tests" / "test_module.py"
        assert test_file.exists()
        assert "def test_process_basic(self):" in test_file.read_text()

    @pytest.mark.asyncio
    async def test_appends_to_existing_test_file(self, tmp_path) -> None:
        source_file = tmp_path / "crackerjack" / "module.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("def process(data): pass")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_module.py"
        test_file.write_text("# existing content\n")

        func_info = {"name": "process", "file": str(source_file), "args": ["data"]}

        result = await tc.create_test_for_function(func_info, tmp_path)

        assert result["fixes"] == ["Added test for function process"]
        content = test_file.read_text()
        assert "# existing content" in content
        assert "def test_process_basic(self):" in content


class TestFindUntestedFunctions:
    @pytest.mark.asyncio
    async def test_finds_functions_without_tests(self, tmp_path) -> None:
        package_dir = tmp_path / "crackerjack"
        package_dir.mkdir()
        (package_dir / "module.py").write_text(
            """
def tested_function(): pass
def untested_function(): pass
"""
        )
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_module.py").write_text("def test_tested_function(): pass")

        untested = await tc.find_untested_functions(tmp_path)

        names = [f["name"] for f in untested]
        assert "untested_function" in names
        assert "tested_function" not in names

    @pytest.mark.asyncio
    async def test_agent_level_find_untested_functions_in_file(self, tmp_path) -> None:
        module = tmp_path / "crackerjack" / "module.py"
        module.parent.mkdir(parents=True)
        module.write_text(
            """
def tested_function(): pass
def untested_function(): pass
"""
        )
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_module.py").write_text("def test_tested_function(): pass")

        untested = await tc.find_untested_functions_in_file(module, tmp_path)

        assert len(untested) == 1
        assert untested[0]["name"] == "untested_function"


# ---------------------------------------------------------------------------
# Coverage-driven and full-pipeline orchestration
# ---------------------------------------------------------------------------


class TestAnalyzeCoverage:
    @pytest.mark.asyncio
    async def test_analyze_coverage_from_existing_json(self, tmp_path) -> None:
        coverage_json = {
            "totals": {
                "percent_covered": 65.5,
                "num_statements": 1000,
                "covered_lines": 655,
            },
            "files": {
                str(tmp_path / "module1.py"): {"summary": {"percent_covered": 50}},
                str(tmp_path / "module2.py"): {"summary": {"percent_covered": 75}},
            },
        }
        import json

        (tmp_path / "coverage.json").write_text(json.dumps(coverage_json))

        result = await tc.analyze_coverage(tmp_path)

        assert result["below_threshold"] is True
        assert result["current_coverage"] == 0.655
        assert len(result["uncovered_modules"]) > 0

    @pytest.mark.asyncio
    async def test_analyze_coverage_no_existing_data_falls_back_to_default(
        self, tmp_path
    ) -> None:
        result = await tc.analyze_coverage(tmp_path)

        assert result["below_threshold"] is True
        assert result["current_coverage"] == 0.0

    @pytest.mark.asyncio
    async def test_run_coverage_command_stub_always_fails(self) -> None:
        # Preserved dead-stub quirk: this never actually runs coverage.
        returncode, stdout, stderr = await tc._run_coverage_command_stub()

        assert returncode == 1
        assert stdout == ""
        assert "not available" in stderr


class TestCreateTestsForIssue:
    @pytest.mark.asyncio
    async def test_full_workflow_creates_test_file_for_issue_path(
        self, tmp_path
    ) -> None:
        module_file = tmp_path / "crackerjack" / "services" / "config.py"
        module_file.parent.mkdir(parents=True)
        module_file.write_text(
            """
def load_config(path):
    pass

def save_config(path, data):
    pass
"""
        )

        issue = _issue(
            message="Missing tests for config service",
            file_path=str(module_file),
        )

        result = await tc.create_tests_for_issue(issue, tmp_path)

        assert result.fixes_applied
        assert result.files_modified
        test_file = tmp_path / "tests" / "test_config.py"
        assert test_file.exists()

    @pytest.mark.asyncio
    async def test_success_field_is_the_fixes_list_not_a_bool(self, tmp_path) -> None:
        # Preserved quirk: `_create_test_creation_result` assigns
        # `fixes_applied` (a list) directly to `FixResult.success`, not
        # `bool(fixes_applied)`.
        module_file = tmp_path / "crackerjack" / "svc.py"
        module_file.parent.mkdir(parents=True)
        module_file.write_text("def process(data): pass")

        issue = _issue(message="Missing tests", file_path=str(module_file))

        result = await tc.create_tests_for_issue(issue, tmp_path)

        assert result.fixes_applied
        assert result.success == result.fixes_applied
        assert not isinstance(result.success, bool)

    @pytest.mark.asyncio
    async def test_no_opportunities_yields_falsy_success_and_zero_confidence(
        self, tmp_path
    ) -> None:
        (tmp_path / "crackerjack").mkdir()
        issue = _issue(message="Missing tests", file_path=None)

        result = await tc.create_tests_for_issue(issue, tmp_path)

        assert not result.success
        assert result.confidence == 0.0
        assert result.recommendations == [
            "No test creation opportunities identified",
            "Consider manual test creation for complex scenarios",
        ]


class TestConfidenceAndRecommendations:
    def test_calculate_confidence_no_fixes(self) -> None:
        assert tc._calculate_confidence(False, [], []) == 0.0

    def test_calculate_confidence_with_fixes(self) -> None:
        fixes = [
            "Created test file for module",
            "Added test for function process_data",
            "Coverage increased to 85%",
        ]
        files = ["test_module1.py", "test_module2.py"]

        confidence = tc._calculate_confidence(True, fixes, files)

        assert confidence > 0.5
        assert confidence <= 0.95

    def test_generate_recommendations_success(self) -> None:
        recommendations = tc._generate_recommendations(True)

        assert recommendations[0] == "Generated comprehensive test suite"

    def test_generate_recommendations_failure(self) -> None:
        recommendations = tc._generate_recommendations(False)

        assert recommendations[0] == "No test creation opportunities identified"

    def test_get_enhanced_test_creation_recommendations(self) -> None:
        recommendations = tc.get_enhanced_test_creation_recommendations()

        assert len(recommendations) == 10
        assert any("coverage analysis" in r for r in recommendations)
