# Documentation System Architecture

## Overview

The Crackerjack documentation system provides automated documentation generation, maintenance, and validation integrated with the existing protocol-based architecture. The system extracts API documentation from code, generates user documentation from templates, and maintains consistency across all documentation sources.

## Architecture Components

### Core Protocols

```python
@t.runtime_checkable
class DocumentationServiceProtocol(t.Protocol):
    def extract_api_documentation(
        self, source_paths: list[Path]
    ) -> dict[str, t.Any]: ...
    def generate_documentation(
        self, template_name: str, context: dict[str, t.Any]
    ) -> str: ...
    def validate_documentation(self, doc_paths: list[Path]) -> list[dict[str, str]]: ...
    def update_documentation_index(self) -> bool: ...


@t.runtime_checkable
class APIExtractorProtocol(t.Protocol):
    def extract_from_python_files(self, files: list[Path]) -> dict[str, t.Any]: ...
    def extract_protocol_definitions(self, protocol_file: Path) -> dict[str, t.Any]: ...
    def extract_service_interfaces(
        self, service_files: list[Path]
    ) -> dict[str, t.Any]: ...
    def extract_cli_commands(self, cli_files: list[Path]) -> dict[str, t.Any]: ...


@t.runtime_checkable
class DocumentationGeneratorProtocol(t.Protocol):
    def generate_api_reference(self, api_data: dict[str, t.Any]) -> str: ...
    def generate_user_guide(self, template_context: dict[str, t.Any]) -> str: ...
    def generate_changelog_update(
        self, version: str, changes: dict[str, t.Any]
    ) -> str: ...
    def render_template(
        self, template_path: Path, context: dict[str, t.Any]
    ) -> str: ...
```

### Service Layer Architecture

```
DocumentationService
├── APIExtractor (Python, Protocol, CLI extraction)
├── DocumentationGenerator (Template rendering, markdown generation)
├── DocumentationValidator (Link checking, consistency validation)
└── DocumentationIndexer (Cross-reference generation, search index)
```

## Integration Points

### 1. CLI Integration

- Add `--generate-docs` flag to Options protocol
- Integrate with existing semantic CLI naming system
- Support `--docs-format` (markdown, html, json) option

### 2. Quality Workflow Integration

- Documentation validation in comprehensive hooks phase
- API documentation freshness checks
- Cross-reference validation against codebase

### 3. MCP Server Integration

- WebSocket endpoint for real-time documentation updates
- Progress tracking for documentation generation jobs
- API endpoint for documentation queries

### 4. Changelog Integration

- Automatic documentation updates on version bumps
- Integration with existing ChangelogGenerator service
- Documentation change tracking in quality baseline

## File Structure

```
crackerjack/
├── services/
│   ├── documentation_service.py        # Main service implementation
│   ├── api_extractor.py               # Code analysis and extraction
│   ├── documentation_generator.py     # Template rendering and generation
│   ├── documentation_validator.py     # Validation and consistency checking
│   └── documentation_indexer.py       # Cross-reference and search indexing
├── managers/
│   └── documentation_manager.py       # High-level orchestration
├── templates/
│   ├── api_reference.md.jinja2       # API documentation template
│   ├── user_guide.md.jinja2          # User guide template
│   ├── changelog_entry.md.jinja2     # Changelog entry template
│   └── index.md.jinja2               # Main documentation index
└── docs/
    ├── generated/                     # Auto-generated documentation
    │   ├── api/                      # API reference docs
    │   ├── guides/                   # User guides
    │   └── index.md                  # Generated index
    └── templates/                    # Source templates
```

## Implementation Phases

### Phase 1: API Extraction (Current)

- Python file parsing for docstrings, type hints, protocols
- CLI option extraction from Options protocol
- Service interface extraction from protocols.py
- MCP tool extraction from existing slash commands

### Phase 2: Template System

- Jinja2 template integration
- Markdown generation with consistent formatting
- Cross-reference link generation
- Template validation and error handling

### Phase 3: Validation & Quality Integration

- Documentation freshness validation
- Link checking and cross-reference validation
- Integration with quality baseline tracking
- Documentation coverage metrics

## Technical Specifications

### API Extraction Capabilities

#### Python Code Analysis

- **Docstring Extraction**: Parse Google/Sphinx style docstrings
- **Type Hint Analysis**: Extract parameter and return type information
- **Protocol Detection**: Identify protocol definitions and methods
- **Decorator Analysis**: Track important decorators (@runtime_checkable, etc.)

#### CLI Documentation

- **Options Mapping**: Extract semantic CLI options from Options protocol
- **Command Examples**: Generate usage examples from option combinations
- **Deprecation Warnings**: Document legacy options and replacements

#### Service Interface Mapping

- **Protocol Relationships**: Map protocols to implementation classes
- **Dependency Injection**: Document DI container structure
- **Service Lifecycle**: Track service initialization and cleanup patterns

### Template System Features

#### Dynamic Content Generation

- **Context-Aware Templates**: Templates receive rich context about extracted APIs
- **Conditional Rendering**: Show/hide sections based on available data
- **Auto-Linking**: Automatic cross-references between related components
- **Code Examples**: Generate working code examples from API signatures

#### Output Formats

- **Markdown**: Primary format for GitHub integration
- **HTML**: Rich web documentation with navigation
- **JSON**: Machine-readable API specifications
- **OpenAPI**: For MCP tool documentation

### Quality Integration Points

#### Documentation Freshness

- **API Change Detection**: Track when code changes but docs don't
- **Version Synchronization**: Ensure docs match current version
- **Broken Link Detection**: Validate all internal and external links
- **Example Validation**: Test that code examples actually work

#### Metrics and Reporting

- **Documentation Coverage**: Percentage of APIs with documentation
- **Quality Score Integration**: Documentation quality contributes to overall score
- **Change Impact Analysis**: Show documentation implications of code changes
- **Maintenance Alerts**: Notify when documentation needs updates

## Integration with Existing Services

### Changelog Automation Integration

```python
# In changelog_automation.py
def update_documentation_references(self, version: str) -> bool:
    """Update documentation version references automatically."""
    doc_service = self._get_documentation_service()
    return doc_service.update_version_references(version)
```

### Quality Baseline Integration

```python
# In quality_baseline_enhanced.py
def _calculate_documentation_score(self, metrics: dict) -> float:
    """Include documentation coverage in quality score."""
    doc_coverage = metrics.get("documentation_coverage", 0.0)
    freshness_score = metrics.get("documentation_freshness", 100.0)
    return (doc_coverage * 0.3) + (freshness_score * 0.2)
```

### MCP Server Integration

```python
# New WebSocket endpoint
@app.websocket("/ws/docs/{job_id}")
async def documentation_progress(websocket: WebSocket, job_id: str):
    """Real-time documentation generation progress."""
    await websocket.accept()
    # Stream documentation generation progress
```

## Security Considerations

### Input Validation

- **Template Injection Prevention**: Sanitize all template inputs
- **File Path Validation**: Ensure documentation files stay within bounds
- **Code Execution Prevention**: No arbitrary code execution in templates
- **Cross-Site Scripting**: HTML output sanitization when applicable

### Access Control

- **Documentation Visibility**: Control what gets documented publicly
- **Sensitive Information**: Automatic detection and redaction of secrets
- **API Surface Control**: Option to exclude internal APIs from documentation

## Performance Optimization

### Caching Strategy

- **Incremental Updates**: Only regenerate changed documentation
- **Template Compilation**: Cache compiled Jinja2 templates
- **Cross-Reference Caching**: Cache link resolution for faster regeneration
- **Parallel Processing**: Generate multiple documentation sections concurrently

### Resource Management

- **Memory Efficiency**: Stream large documentation generation jobs
- **Disk Usage**: Cleanup old generated documentation versions
- **CPU Optimization**: Efficient AST parsing and template rendering
- **Network Efficiency**: Batch external link validation

## Future Enhancements

### Advanced Features (Post-MVP)

- **Interactive Documentation**: Integration with Jupyter notebooks
- **API Playground**: Live API testing interface
- **Documentation Analytics**: Track documentation usage and effectiveness
- **Multi-language Support**: Documentation generation for multiple languages
- **AI-Powered Improvements**: Automatic documentation quality suggestions

### Integration Opportunities

- **IDE Integration**: Real-time documentation preview in development
- **CI/CD Pipeline**: Automatic documentation deployment
- **Documentation Testing**: Validate that documentation examples work
- **Community Contributions**: Framework for external documentation contributions

## Success Metrics

### Quality Indicators

- **Documentation Coverage**: Target 95%+ API coverage
- **Freshness Score**: \<2 day lag between code and documentation updates
- **Link Validity**: 99%+ internal links working
- **User Satisfaction**: Measure through documentation usage analytics

### Performance Targets

- **Generation Speed**: Complete documentation regeneration \<30 seconds
- **Incremental Updates**: Individual file updates \<2 seconds
- **Resource Usage**: \<100MB memory for full documentation generation
- **Template Rendering**: \<1ms per template for common templates

This architecture provides a robust foundation for automated documentation generation while seamlessly integrating with Crackerjack's existing systems and maintaining the project's quality standards.
