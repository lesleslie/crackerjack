# Coverage Badge Implementation Plan

## Overview

Implement automatic coverage badge management in README.md that:

1. Detects if coverage badge exists
1. Adds coverage badge if missing (near other badges)
1. Updates coverage percentage automatically when coverage changes
1. Integrates seamlessly with existing test workflow

## Current README Badge Pattern

Looking at crackerjack's README, badges are typically placed at the top using this format:

```markdown
![Coverage Badge](https://img.shields.io/badge/coverage-42.83%25-yellow)
```

## Implementation Components

### 1. Coverage Badge Service

**File**: `crackerjack/services/coverage_badge_service.py`

**Responsibilities**:

- Parse current coverage from coverage reports (`.coverage`, `coverage.json`)
- Generate coverage badge URL with appropriate color coding
- Detect existing coverage badges in README
- Update or insert coverage badges
- Handle badge color thresholds (red < 50%, yellow 50-80%, green > 80%)

### 2. README Badge Manager

**File**: `crackerjack/services/readme_badge_manager.py`

**Responsibilities**:

- Parse README.md structure
- Find badge section (typically at top after title)
- Insert badges in appropriate location
- Preserve existing badge ordering
- Handle multiple README formats

### 3. Integration Points

#### A. Test Manager Integration

**Location**: `crackerjack/managers/test_manager.py`

- Hook into coverage reporting workflow
- Trigger badge update after coverage calculation
- Only update if coverage percentage changed

#### B. Phase Coordinator Integration

**Location**: `crackerjack/core/phase_coordinator.py`

- Call badge update during test phase completion
- Handle badge update errors gracefully

## Badge Format Specification

### URL Template

```
https://img.shields.io/badge/coverage-{percentage}%25-{color}
```

### Color Coding

- **Red** (`red`): < 50% coverage
- **Yellow** (`yellow`): 50-79% coverage
- **Green** (`brightgreen`): ≥ 80% coverage

### Badge Text Format

```markdown
![Coverage](https://img.shields.io/badge/coverage-{percentage}%25-{color})
```

## Implementation Strategy

### Phase 1: Core Badge Service

```python
class CoverageBadgeService:
    def get_current_coverage(self) -> float
    def generate_badge_url(self, coverage: float) -> str
    def get_badge_color(self, coverage: float) -> str
```

### Phase 2: README Management

```python
class ReadmeBadgeManager:
    def find_badge_section(self, readme_content: str) -> int
    def has_coverage_badge(self, readme_content: str) -> bool
    def update_coverage_badge(self, readme_content: str, new_url: str) -> str
    def insert_coverage_badge(self, readme_content: str, badge_url: str) -> str
```

### Phase 3: Test Integration

```python
# In TestManager after coverage calculation
if self.coverage_changed():
    self.badge_service.update_readme_badge()
```

## Configuration Options

Add to `pyproject.toml`:

```toml
[tool.crackerjack.coverage_badge]
enabled = true
auto_update = true
color_thresholds = { red = 50, yellow = 80 }
badge_style = "flat"  # flat, flat-square, for-the-badge
```

## File Locations

**New Files**:

- `crackerjack/services/coverage_badge_service.py`
- `crackerjack/services/readme_badge_manager.py`

**Modified Files**:

- `crackerjack/managers/test_manager.py` - Add badge update trigger
- `crackerjack/core/phase_coordinator.py` - Integration point
- `pyproject.toml` - Configuration options

## Testing Strategy

**Unit Tests**:

- Badge URL generation with different coverage percentages
- README parsing and badge detection
- Badge insertion/update logic

**Integration Tests**:

- End-to-end badge update during test execution
- Multiple README formats handling
- Coverage change detection

## Benefits

1. **Automatic Maintenance**: No manual badge updates required
1. **Accurate Reporting**: Always reflects current coverage
1. **Professional Appearance**: Consistent badge formatting
1. **Zero Configuration**: Works out-of-the-box with sensible defaults
1. **Non-Disruptive**: Preserves existing README structure

This implementation will seamlessly integrate with crackerjack's existing test workflow and provide automatic, always-current coverage visibility in the README.
