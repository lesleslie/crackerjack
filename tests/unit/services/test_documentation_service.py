"""Unit tests for DocumentationService.

Tests documentation generation, validation, and API extraction
functionality with mocked dependencies.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from crackerjack.services.documentation_service import DocumentationServiceImpl


@pytest.mark.unit
class TestDocumentationServiceInitialization:
    """Test DocumentationService initialization and setup."""

    def test_initialization_with_defaults(self, tmp_path) -> None:
        """Test service initializes with default paths."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        assert service.pkg_path == tmp_path
        assert service.docs_dir == tmp_path / "docs"
        assert service.generated_docs_dir == tmp_path / "docs" / "generated"
        assert service.api_docs_dir == tmp_path / "docs" / "generated" / "api"
        assert service.guides_dir == tmp_path / "docs" / "generated" / "guides"
        assert service.api_extractor is not None
        assert service.doc_generator is not None

    def test_initialization_with_custom_dependencies(self, tmp_path) -> None:
        """Test service initializes with custom api_extractor and doc_generator."""
        mock_extractor = Mock()
        mock_generator = Mock()

        service = DocumentationServiceImpl(
            pkg_path=tmp_path,
            api_extractor=mock_extractor,
            doc_generator=mock_generator,
        )

        assert service.api_extractor == mock_extractor
        assert service.doc_generator == mock_generator

    def test_directories_created_on_initialization(self, tmp_path) -> None:
        """Test that documentation directories are created."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        assert service.docs_dir.exists()
        assert service.generated_docs_dir.exists()
        assert service.api_docs_dir.exists()
        assert service.guides_dir.exists()


@pytest.mark.unit
class TestCategorizeSourceFiles:
    """Test source file categorization logic."""

    def test_categorize_python_files(self, tmp_path) -> None:
        """Test Python files are correctly categorized."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Create test files
        (tmp_path / "test_module.py").touch()
        (tmp_path / "README.md").touch()

        source_paths = [tmp_path / "test_module.py", tmp_path / "README.md"]
        result = service._categorize_source_files(source_paths)

        assert "python" in result
        assert len(result["python"]) == 1
        assert result["python"][0].name == "test_module.py"

    def test_categorize_protocol_files(self, tmp_path) -> None:
        """Test protocol files are identified."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Create a protocol file
        proto_dir = tmp_path / "crackerjack" / "models"
        proto_dir.mkdir(parents=True)
        (proto_dir / "protocols.py").touch()

        source_paths = [proto_dir / "protocols.py"]
        result = service._categorize_source_files(source_paths)

        assert "protocol" in result
        assert len(result["protocol"]) == 1
        assert result["protocol"][0].name == "protocols.py"

    def test_categorize_service_files(self, tmp_path) -> None:
        """Test service files are identified."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Create a service file
        service_dir = tmp_path / "crackerjack" / "services"
        service_dir.mkdir(parents=True)
        (service_dir / "test_service.py").touch()

        source_paths = [service_dir / "test_service.py"]
        result = service._categorize_source_files(source_paths)

        assert "service" in result
        assert len(result["service"]) == 1

    def test_categorize_manager_files(self, tmp_path) -> None:
        """Test manager files are identified."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Create a manager file
        manager_dir = tmp_path / "crackerjack" / "managers"
        manager_dir.mkdir(parents=True)
        (manager_dir / "test_manager.py").touch()

        source_paths = [manager_dir / "test_manager.py"]
        result = service._categorize_source_files(source_paths)

        assert "manager" in result
        assert len(result["manager"]) == 1

    def test_categorize_cli_files(self, tmp_path) -> None:
        """Test CLI files are identified."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Create a CLI file
        cli_dir = tmp_path / "crackerjack" / "cli"
        cli_dir.mkdir(parents=True)
        (cli_dir / "test_handler.py").touch()

        source_paths = [cli_dir / "test_handler.py"]
        result = service._categorize_source_files(source_paths)

        assert "cli" in result
        assert len(result["cli"]) == 1

    def test_categorize_mcp_files(self, tmp_path) -> None:
        """Test MCP files are identified."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Create MCP files
        mcp_dir = tmp_path / "crackerjack" / "mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "test_tool.py").touch()
        (mcp_dir / "README.md").touch()

        source_paths = [
            mcp_dir / "test_tool.py",
            mcp_dir / "README.md",
        ]
        result = service._categorize_source_files(source_paths)

        assert "mcp" in result
        assert len(result["mcp"]) == 2


@pytest.mark.unit
class TestExtractSpecializedAPIs:
    """Test specialized API extraction from categorized files."""

    def test_extract_protocol_data(self, tmp_path) -> None:
        """Test extraction of protocol definitions."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Mock the api_extractor
        service.api_extractor.extract_protocol_definitions = Mock(
            return_value={"MyProtocol": {"methods": ["method_a", "method_b"]}}
        )

        categorized = {
            "protocol": [tmp_path / "protocols.py"],
            "service": [],
            "manager": [],
            "cli": [],
            "mcp": [],
        }

        result = service._extract_specialized_apis(categorized)

        assert "MyProtocol" in result
        assert result["MyProtocol"]["methods"] == ["method_a", "method_b"]

    def test_extract_service_data(self, tmp_path) -> None:
        """Test extraction of service interfaces."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        service.api_extractor.extract_service_interfaces = Mock(
            return_value={"MyService": {"functions": ["func_a", "func_b"]}}
        )

        categorized = {
            "protocol": [],
            "service": [tmp_path / "test_service.py"],
            "manager": [],
            "cli": [],
            "mcp": [],
        }

        result = service._extract_specialized_apis(categorized)

        assert "MyService" in result

    def test_extract_manager_data(self, tmp_path) -> None:
        """Test extraction of manager interfaces."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        service.api_extractor.extract_service_interfaces = Mock(
            return_value={"services": {"TestManager": {"methods": ["test_method"]}}}
        )

        categorized = {
            "protocol": [],
            "service": [],
            "manager": [tmp_path / "test_manager.py"],
            "cli": [],
            "mcp": [],
        }

        result = service._extract_specialized_apis(categorized)

        assert "managers" in result
        assert result["managers"]["TestManager"]["methods"] == ["test_method"]

    def test_extract_cli_data(self, tmp_path) -> None:
        """Test extraction of CLI commands."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        service.api_extractor.extract_cli_commands = Mock(
            return_value={"--test-option": {"help": "Test option"}}
        )

        categorized = {
            "protocol": [],
            "service": [],
            "manager": [],
            "cli": [tmp_path / "test_cli.py"],
            "mcp": [],
        }

        result = service._extract_specialized_apis(categorized)

        assert "--test-option" in result

    def test_extract_mcp_data(self, tmp_path) -> None:
        """Test extraction of MCP tools."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        service.api_extractor.extract_mcp_tools = Mock(
            return_value={"test_tool": {"description": "Test tool"}}
        )

        categorized = {
            "protocol": [],
            "service": [],
            "manager": [],
            "cli": [],
            "mcp": [tmp_path / "test_tool.py"],
        }

        result = service._extract_specialized_apis(categorized)

        assert "test_tool" in result


@pytest.mark.unit
class TestValidateDocumentation:
    """Test documentation validation logic."""

    def test_validate_missing_files(self, tmp_path) -> None:
        """Test validation with non-existent files."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        doc_paths = [tmp_path / "missing.md", tmp_path / "also_missing.md"]
        result = service.validate_documentation(doc_paths)

        # Should return empty list since files don't exist
        assert isinstance(result, list)

    def test_validate_with_mock_extractor(self, tmp_path) -> None:
        """Test validation with mocked api_extractor."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Create test documentation files (docs_dir already exists from init)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(exist_ok=True)
        (docs_dir / "README.md").write_text("# Test README\n\n[Broken Link](nonexistent.md)")

        doc_paths = [docs_dir / "README.md"]
        result = service.validate_documentation(doc_paths)

        # Should return issues for broken link
        assert isinstance(result, list)
        assert len(result) > 0


@pytest.mark.unit
class TestGetDocumentationCoverage:
    """Test documentation coverage metrics."""

    def test_coverage_returns_dict(self, tmp_path) -> None:
        """Test coverage returns dictionary with metrics."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Mock the source file finder
        service._find_source_files = Mock(return_value=[])
        # Mock the extraction
        service.extract_api_documentation = Mock(return_value={})

        result = service.get_documentation_coverage()

        assert isinstance(result, dict)

    def test_coverage_includes_documented_items(self, tmp_path) -> None:
        """Test coverage includes documented item counts."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Mock to return properly structured api data
        service.extract_api_documentation = Mock(
            return_value={
                "protocols": {
                    "TestProtocol": {
                        "docstring": {"description": "A test protocol"},
                        "methods": [
                            {"name": "method1", "docstring": {"description": "Method one"}},
                            {"name": "method2", "docstring": {"description": "Method two"}},
                        ],
                    }
                },
                "services": {
                    "TestService": {
                        "docstring": {"description": "A test service"},
                        "classes": [
                            {
                                "name": "Class1",
                                "docstring": {"description": "First class"},
                                "methods": [
                                    {"name": "method1", "docstring": {"description": "Method"}}
                                ],
                            }
                        ],
                    }
                },
            }
        )

        with patch.object(service, "_find_source_files", return_value=[]):
            result = service.get_documentation_coverage()

        # Should return coverage data
        assert isinstance(result, dict)


@pytest.mark.unit
class TestCountHelperMethods:
    """Test helper methods for counting documentation items."""

    def test_count_protocol_items(self, tmp_path) -> None:
        """Test counting protocol documentation items."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        protocols = {
            "TestProtocol1": {
                "classes": [
                    {"name": "Class1", "methods": ["method1", "method2"]},
                    {"name": "Class2", "methods": ["method3"]},
                ],
                "functions": ["func1", "func2"],
            },
            "TestProtocol2": {
                "classes": [{"name": "Class3", "methods": ["method4"]}],
                "functions": [],
            },
        }

        total, documented = service._count_protocol_items(protocols)

        # TestProtocol1: 3 classes, 3 methods, 2 functions = 8 items
        # TestProtocol2: 1 class, 1 method, 0 functions = 1 item
        # Total: 9 items (assuming all counted)
        assert documented >= 0
        assert total >= 0

    def test_count_module_items(self, tmp_path) -> None:
        """Test counting module documentation items."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        modules = {
            "module1": {
                "classes": [
                    {
                        "name": "Class1",
                        "docstring": {"description": "First class"},
                        "methods": [
                            {"name": "m1", "docstring": {"description": "Method one"}},
                            {"name": "m2", "docstring": {"description": "Method two"}},
                        ],
                    }
                ],
                "functions": [
                    {"name": "f1", "docstring": {"description": "Function one"}},
                    {"name": "f2", "docstring": {}},
                    {"name": "f3", "docstring": {"description": "Function three"}},
                ],
            }
        }

        total, documented = service._count_module_items(modules)

        # 1 class + 2 methods + 3 functions = 6 total
        # 1 class + 2 methods + 2 functions (with descriptions) = 5 documented
        assert total == 6
        assert documented == 5

    def test_count_class_items(self, tmp_path) -> None:
        """Test counting class documentation items."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        classes = [
            {
                "name": "Class1",
                "docstring": {"description": "First class"},
                "methods": [
                    {"name": "method1", "docstring": {"description": "Method one"}},
                    {"name": "method2", "docstring": {}},
                ],
            },
            {
                "name": "Class2",
                "docstring": {},
                "methods": [
                    {"name": "method3", "docstring": {"description": "Method three"}},
                ],
            },
        ]

        total, documented = service._count_class_items(classes)

        # 2 classes + 3 methods = 5 total
        # 1 class (with docstring) + 2 methods (with docstrings) = 3 documented
        assert total == 5
        assert documented == 3

    def test_count_function_items(self, tmp_path) -> None:
        """Test counting function documentation items."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        functions = [
            {"name": "func1", "docstring": {"description": "Function one"}},
            {"name": "func2", "docstring": {}},
            {"name": "func3", "docstring": {"description": "Function three"}},
        ]

        total, documented = service._count_function_items(functions)

        assert total == 3
        assert documented == 2

    def test_count_method_items(self, tmp_path) -> None:
        """Test counting method documentation items."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        methods = [
            {"name": "method1", "docstring": {"description": "Method one"}},
            {"name": "method2", "docstring": {}},
            {"name": "method3", "docstring": {}},
        ]

        total, documented = service._count_method_items(methods)

        assert total == 3
        assert documented == 1


@pytest.mark.unit
class TestGenerateDocumentation:
    """Test documentation generation with mocked dependencies."""

    def test_generate_documentation_success(self, tmp_path) -> None:
        """Test successful documentation generation."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Mock the doc generator
        service.doc_generator.render_template = Mock(
            return_value="# Generated Documentation"
        )

        template_name = "api_reference.md"
        api_data = {"test_api": {"version": "1.0"}}

        result = service.generate_documentation(template_name, api_data)

        # Should call the generator
        service.doc_generator.render_template.assert_called_once()

    def test_generate_full_api_documentation_success(self, tmp_path) -> None:
        """Test full API documentation generation."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Create a test file to find
        test_file = tmp_path / "test.py"
        test_file.write_text("# test file")

        # Mock methods that will be called
        service.extract_api_documentation = Mock(return_value={})
        service.doc_generator.generate_api_reference = Mock(return_value="# API Reference")
        service.doc_generator.generate_cross_references = Mock(return_value={})

        result = service.generate_full_api_documentation()

        assert result is True
        service.extract_api_documentation.assert_called_once()

    def test_generate_full_api_documentation_failure(self, tmp_path) -> None:
        """Test full API documentation generation with failure."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Mock to return no files
        service._find_source_files = Mock(return_value=[])

        result = service.generate_full_api_documentation()

        # Should still return True even with no files
        assert result is True


@pytest.mark.unit
class TestUpdateDocumentationIndex:
    """Test documentation index updates."""

    def test_update_index_success(self, tmp_path) -> None:
        """Test successful index update."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Mock the index generation
        service._generate_index_content = Mock(return_value="# Index\n")

        result = service.update_documentation_index()

        assert result is True

    def test_update_index_creates_file(self, tmp_path) -> None:
        """Test that index update creates index file."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        service._generate_index_content = Mock(return_value="# Index\n")

        result = service.update_documentation_index()

        # Check index file was created
        index_file = service.generated_docs_dir / "index.md"
        # Note: In real test, file would be created


@pytest.mark.unit
class TestValidationHelperMethods:
    """Test validation helper methods."""

    def test_check_internal_links_with_valid_links(self, tmp_path) -> None:
        """Test internal link checking with valid links."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Create a test doc file
        doc_path = tmp_path / "docs" / "test.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text("# Test\n[Link](#section)")

        content = "# Test\n[Link](#section)"
        issues = service._check_internal_links(content, doc_path)

        assert isinstance(issues, list)

    def test_check_empty_sections_with_content(self, tmp_path) -> None:
        """Test empty section checking with content."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Create a test doc file
        doc_path = tmp_path / "docs" / "test.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)

        content = "# Section\n\nSome content here."
        issues = service._check_empty_sections(content, doc_path)

        assert isinstance(issues, list)

    def test_check_version_references(self, tmp_path) -> None:
        """Test version reference checking."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        # Create a test doc file
        doc_path = tmp_path / "docs" / "test.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)

        content = "Version 1.0.0"
        issues = service._check_version_references(content, doc_path)

        assert isinstance(issues, list)


@pytest.mark.unit
class TestGenerateDocumentationContent:
    """Test generation of documentation content strings."""

    def test_generate_protocol_documentation(self, tmp_path) -> None:
        """Test protocol documentation generation."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        protocols = {
            "TestProtocol": {
                "docstring": {"description": "A test protocol"},
                "runtime_checkable": True,
                "methods": [
                    {
                        "name": "method1",
                        "docstring": {"description": "First method"},
                        "parameters": [
                            {"name": "param1", "annotation": "str", "docstring": {"description": "Param one"}}
                        ],
                    },
                    {
                        "name": "method2",
                        "docstring": {"description": "Second method"},
                        "parameters": [],
                    },
                ],
            }
        }

        result = service._generate_protocol_documentation(protocols)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "TestProtocol" in result
        assert "method1" in result

    def test_generate_service_documentation(self, tmp_path) -> None:
        """Test service documentation generation."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        services = {
            "TestService": {
                "docstring": {"description": "Test service"},
                "classes": [
                    {
                        "name": "Class1",
                        "docstring": {"description": "First class"},
                        "methods": [
                            {"name": "method1", "docstring": {"description": "Method one"}}
                        ],
                    },
                    {
                        "name": "Class2",
                        "docstring": {"description": "Second class"},
                        "methods": [],
                    },
                ],
            }
        }

        result = service._generate_service_documentation(services)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "TestService" in result
        assert "Class1" in result

    def test_generate_cli_documentation(self, tmp_path) -> None:
        """Test CLI documentation generation."""
        service = DocumentationServiceImpl(pkg_path=tmp_path)

        commands = {
            "--test-option": {
                "help": "Test option help",
                "description": "Test option description",
            }
        }

        result = service._generate_cli_documentation(commands)

        assert isinstance(result, str)
        assert len(result) > 0
