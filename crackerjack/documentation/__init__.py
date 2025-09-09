"""AI-optimized documentation generation system for crackerjack."""

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

__all__ = [
    "DualOutputGenerator",
    "DocumentationResult",
    "AITemplateEngine",
    "TemplateContext",
    "Template",
    "TemplateType",
    "ReferenceGenerator",
    "CommandReference",
    "CommandInfo",
    "ParameterInfo",
    "MkDocsIntegrationService",
    "MkDocsSiteBuilder",
    "MkDocsConfig",
]
