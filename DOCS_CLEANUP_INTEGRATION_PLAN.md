# Documentation Cleanup Integration Plan

## Problem Statement

The `DocumentationCleanup` service (`crackerjack/services/documentation_cleanup.py`) currently uses **simple glob patterns** (`fnmatch`) that are significantly less capable than the **sophisticated regex-based categorization** in `scripts/docs_cleanup.py`.

### Current Limitations

**Production Service** (`DocumentationCleanup`):
- Uses `fnmatch(filename, "*PLAN*.md")` - too broad
- Only 7 archive patterns
- Binary classification (essential vs. archivable)
- Misses nuanced cases like:
  - Agent reports: `TYPE_FIXING_REPORT_AGENT4.md`
  - Dash-separated files: `bandit-performance-investigation.md`
  - Mixed patterns: `refactoring-plan-complexity-violations.md`

**Analysis Tool** (`scripts/docs_cleanup.py`):
- Uses regex patterns with `re.IGNORECASE`
- 10 distinct categories with specific destinations
- Achieved **100% categorization** (60/60 files)
- Handles edge cases like all-caps agent reports

## Proposed Solution

### Option A: Upgrade `DocumentationCleanup` with Regex Engine (RECOMMENDED)

**Benefits**:
- Single source of truth for documentation rules
- Production service gets our 100% categorization accuracy
- Maintains backup/rollback/security logging features
- Configuration-driven patterns can still work

**Implementation**:

1. **Extract categorization logic** from `scripts/docs_cleanup.py` into a reusable module
2. **Add regex support** to `DocumentationCleanup._matches_archive_patterns()`
3. **Upgrade pattern configuration** to support both glob and regex
4. **Maintain backward compatibility** with existing fnmatch patterns

**File Structure**:
```
crackerjack/
  services/
    documentation_cleanup.py          # Upgrade with regex engine
    doc_categorizer.py                # NEW: Extract categorization logic
  config/
    settings.py                       # Add regex_patterns field
scripts/
  docs_cleanup.py                     # Keep as standalone analysis tool
```

### Option B: Configuration-Based Enhancement

**Benefits**:
- Pure configuration change, no code modification
- Can deploy via `settings/crackerjack.yaml`
- Backward compatible

**Implementation**:

Update `crackerjack/config/settings.py` to add comprehensive patterns:

```python
class DocumentationSettings(Settings):
    # Existing fields...
    archive_patterns: list[str] = [
        # Completion reports (expanded)
        "*COMPLETE*.md",
        "*COMPLETION*.md",
        "*FINAL_REPORT*.md",
        "*SUMMARY*.md",
        "*_REPORT*.md",
        "*_report*.md",
        "*[A-Z][A-Z]*_REPORT*.md",  # Agent reports like TYPE_FIXING_REPORT_AGENT4

        # Implementation plans (refined)
        "*_PLAN.md",
        "*_plan.md",
        "implementation-plan-*.md",
        "*-plan-*.md",  # Dash-separated plans

        # Investigations (expanded)
        "*investigation.md",
        "*INVESTIGATION.md",
        "*-investigation.md",  # Dash-separated

        # Audits (expanded)
        "*AUDIT.md",
        "AUDIT_*.md",

        # And so on...
    ]
    archive_subdirectories: dict[str, str] = {
        # More granular mappings...
    }
```

**Limitation**: `fnmatch()` doesn't support regex features like:
- Case-insensitive matching
- Character classes: `[A-Z]+`
- Word boundaries: `\b`
- Complex alternation: `(plan|PLAN)`

### Option C: Hybrid Approach (BEST OF BOTH WORLDS)

Combine regex power with configuration flexibility:

```python
class DocumentationSettings(Settings):
    # Existing glob patterns (backward compatibility)
    archive_patterns: list[str] = [...]  # fnmatch patterns

    # NEW: Regex patterns for advanced cases
    archive_regex_patterns: list[str] = [
        r".*_COMPLETE\.md$",
        r".*_COMPLETION\.md$",
        r".*_[A-Z]+_REPORT.*\.md$",  # Agent reports
        r".*-investigation\.md$",
        # ... all our sophisticated patterns
    ]

    # Category-based destinations (NEW)
    archive_categories: dict[str, dict] = {
        "completion_reports": {
            "patterns": [r".*_COMPLETE\.md$", ...],
            "destination": "completion-reports/"
        },
        "implementation_plans": {
            "patterns": [r".*_PLAN\.md$", ...],
            "destination": "implementation-plans/"
        },
        # ... all 10 categories
    }
```

## Recommendation: Option C with Module Extraction

### Phase 1: Extract Categorization Logic

Create `crackerjack/services/doc_categorizer.py`:

```python
"""Shared documentation categorization logic."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DocCategory = Literal[
    "keep_in_root",
    "keep_in_docs",
    "implementation_plans",
    "completion_reports",
    "audits",
    "investigations",
    "fixes",
    "sprints_and_fixes",
    "implementation_reports",
    "analysis",
]

@dataclass
class CategoryResult:
    category: DocCategory | None
    destination: str | None
    reason: str


class DocumentationCategorizer:
    """Categorize documentation files using regex patterns."""

    PATTERNS = {
        "keep_in_root": {
            "patterns": [
                r"^README\.md$",
                r"^CHANGELOG\.md$",
                # ... all our patterns
            ],
            "destination": None,
            "reason": "Core documentation or completion milestones",
        },
        # ... all 10 categories
    }

    def __init__(self, docs_root: Path):
        self.docs_root = docs_root

    def categorize_file(self, filepath: Path) -> CategoryResult:
        """Categorize a single file."""
        filename = filepath.name

        for category, config in self.PATTERNS.items():
            for pattern in config["patterns"]:
                if re.match(pattern, filename, re.IGNORECASE):
                    return CategoryResult(
                        category=category,
                        destination=config["destination"],
                        reason=config["reason"]
                    )

        return CategoryResult(category=None, destination=None, reason="Uncategorized")

    def analyze_all(self) -> dict[str, list[Path]]:
        """Analyze all markdown files."""
        results = {cat: [] for cat in self.PATTERNS.keys()}
        results["uncategorized"] = []

        for md_file in self.docs_root.glob("*.md"):
            result = self.categorize_file(md_file)
            if result.category:
                results[result.category].append(md_file)
            else:
                results["uncategorized"].append(md_file)

        return results
```

### Phase 2: Upgrade `DocumentationCleanup` Service

Modify `crackerjack/services/documentation_cleanup.py`:

```python
from crackerjack.services.doc_categorizer import DocumentationCategorizer, CategoryResult

class DocumentationCleanup:
    def __init__(self, ...):
        # ... existing init ...
        self.categorizer = DocumentationCategorizer(self.pkg_path)

    def _detect_archivable_files(self) -> list[Path]:
        """Use regex-based categorization."""
        all_files = list(self.pkg_path.glob("*.md"))
        archivable = []

        for md_file in all_files:
            result = self.categorizer.categorize_file(md_file)

            # Keep if categorized as "keep_in_*" or uncategorized
            if result.category in ("keep_in_root", "keep_in_docs"):
                continue

            # Archive everything else
            if result.category:
                archivable.append(md_file)

        return archivable

    def _determine_archive_subdirectory(self, filename: str) -> str | None:
        """Use categorizer for destination mapping."""
        result = self.categorizer.categorize_file(Path(filename))

        if result.destination:
            # Convert "docs/archive/completion-reports/" to "completion-reports"
            parts = Path(result.destination).parts
            if "archive" in parts:
                idx = parts.index("archive")
                if idx + 1 < len(parts):
                    return parts[idx + 1]

        # Fallback to legacy fnmatch patterns
        for mapping in self._archive_mappings:
            if fnmatch(filename, mapping.pattern):
                return mapping.subdirectory

        return "uncategorized"
```

### Phase 3: Update `scripts/docs_cleanup.py`

Make the standalone tool use the shared categorizer:

```python
#!/usr/bin/env python3
"""Documentation cleanup utility for crackerjack project."""

from crackerjack.services.doc_categorizer import DocumentationCategorizer

class DocCleanupAnalyzer:
    def __init__(self, docs_root: Path):
        self.categorizer = DocumentationCategorizer(docs_root)

    def analyze(self) -> dict:
        """Use shared categorization logic."""
        return self.categorizer.analyze_all()

    # ... rest of analysis/reporting logic
```

### Phase 4: Update Configuration

Enhance `crackerjack/config/settings.py`:

```python
class DocumentationSettings(Settings):
    # Existing configuration...
    essential_files: list[str] = [...]
    archive_patterns: list[str] = [...]  # Keep for backward compatibility
    archive_subdirectories: dict[str, str] = {...}

    # NEW: Advanced regex categorization
    use_regex_categorization: bool = True  # Opt-in to new engine
    regex_categories: dict[str, dict] = DocumentationCategorizer.PATTERNS
```

## Benefits of This Approach

1. **Single Source of Truth**: Patterns defined once, used everywhere
2. **100% Accuracy**: Production service gets our proven categorization
3. **Backward Compatible**: Existing fnmatch patterns still work
4. **Configuration Flexibility**: Can disable regex via `use_regex_categorization: false`
5. **Testable**: `DocumentationCategorizer` is pure logic, easy to test
6. **Maintainable**: Update patterns in one place, all tools benefit

## Migration Path

1. **Phase 1** (Low Risk): Create `doc_categorizer.py` module
2. **Phase 2** (Medium Risk): Upgrade `DocumentationCleanup` service
3. **Phase 3** (Low Risk): Update `scripts/docs_cleanup.py` to use shared module
4. **Phase 4** (Low Risk): Update configuration schema
5. **Phase 5** (Testing): Comprehensive testing of all categorization scenarios
6. **Phase 6** (Deployment): Roll out with feature flag for safe rollback

## Testing Strategy

```python
# tests/test_doc_categorizer.py
def test_completion_reports_captured():
    categorizer = DocumentationCategorizer(Path("/test"))
    result = categorizer.categorize_file(Path("TYPE_FIXING_REPORT_AGENT4.md"))
    assert result.category == "completion_reports"

def test_dash_separated_investigations():
    result = categorizer.categorize_file(Path("bandit-performance-investigation.md"))
    assert result.category == "investigations"

def test_essential_files_preserved():
    result = categorizer.categorize_file(Path("README.md"))
    assert result.category == "keep_in_root"
    assert result.destination is None
```

## Success Criteria

- ✅ Production service achieves 100% categorization (60/60 files)
- ✅ All edge cases from `scripts/docs_cleanup.py` handled
- ✅ Backward compatibility maintained
- ✅ Backup/rollback still works
- ✅ Configuration-driven patterns still supported
- ✅ Zero breaking changes to existing workflows

## Estimated Effort

- **Phase 1**: 2-3 hours (extract logic, write tests)
- **Phase 2**: 2-3 hours (integrate into service, handle edge cases)
- **Phase 3**: 1 hour (update standalone script)
- **Phase 4**: 1 hour (update config)
- **Phase 5-6**: 2-3 hours (testing, deployment)

**Total**: ~8-12 hours of development time
