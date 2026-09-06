from .ai_templates import AITemplateEngine, Template, TemplateContext, TemplateType
from .dual_output_generator import DocumentationResult, DualOutputGenerator
from .mkdocs_integration import (
    MkDocsConfig,
    MkDocsIntegrationService,
    MkDocsSiteBuilder,
)
from .reference_generator import (
    CommandInfo,
    CommandReference,
    ParameterInfo,
    ReferenceGenerator,
)

# `docstring_extractor` is loaded lazily via PEP 562 module-level __getattr__
# so pytest-cov can measure it during normal `pytest --cov=crackerjack` runs.
# Eagerly importing it from this `__init__.py` causes coverage.py to mark it
# as "imported before measurement started", producing false 0% coverage for
# every test that touches the module — even though tests do exercise it.
_DOCSTRING_EXTRACTOR_ATTRS = frozenset(
    {
        "extract_class_markdown",
        "extract_for_zensical",
        "extract_function_markdown",
        "extract_module_markdown",
        "validate_docstring_quality",
    },
)


def __getattr__(name: str):
    if name in _DOCSTRING_EXTRACTOR_ATTRS:
        from . import docstring_extractor

        value = getattr(docstring_extractor, name)
        globals()[name] = value  # cache for subsequent lookups
        return value
    msg = f"module 'crackerjack.documentation' has no attribute {name!r}"
    raise AttributeError(msg)


__all__ = [
    "AITemplateEngine",
    "CommandInfo",
    "CommandReference",
    "DocumentationResult",
    "DualOutputGenerator",
    "MkDocsConfig",
    "MkDocsIntegrationService",
    "MkDocsSiteBuilder",
    "ParameterInfo",
    "ReferenceGenerator",
    "Template",
    "TemplateContext",
    "TemplateType",
    "extract_class_markdown",
    "extract_for_zensical",
    "extract_function_markdown",
    "extract_module_markdown",
    "validate_docstring_quality",
]
