# ADR-004: Quality Gate Threshold System

## Status

**Accepted** - 2025-01-28

## Context

Crackerjack runs multiple quality checks (type checking, security scanning, complexity analysis, etc.) and needed a way to enforce quality standards consistently across different project contexts. A flexible threshold system was required to:

1. **Prevent merging code below quality standards**
1. **Support gradual improvement** (allow temporary exceptions)
1. **Handle different project contexts** (library vs application vs scripts)
1. **Provide clear feedback** to developers about what needs fixing
1. **Integrate with CI/CD pipelines**

### Problem Statement

How should Crackerjack enforce quality standards while being:

1. **Strict enough** to prevent low-quality code from merging
1. **Flexible enough** to handle different project contexts
1. **Supportive of gradual improvement** (not all code can be fixed immediately)
1. **Clear** about what standards are enforced and why
1. **Configurable** without requiring code changes

### Key Requirements

- Thresholds must be configurable per project
- Different contexts require different thresholds (library vs app)
- Support for temporary exemptions with tracking
- CI/CD integration with clear pass/fail
- Gradual improvement support (ratchet system)
- Clear error messaging with actionable feedback

## Decision Drivers

| Driver | Importance | Rationale |
|--------|------------|-----------|
| **Quality Enforcement** | Critical | Prevent low-quality code from merging |
| **Flexibility** | High | Different projects have different needs |
| **Gradual Improvement** | High | Not all legacy code can be fixed immediately |
| **CI/CD Integration** | High | Must work in automated pipelines |
| **Clarity** | High | Developers must understand why quality gate failed |

## Considered Options

### Option 1: Hard-Coded Thresholds (Rejected)

**Description**: Use fixed thresholds in code (e.g., "coverage must be ≥ 80%").

**Pros**:

- Simple implementation
- Clear enforcement
- Easy to understand

**Cons**:

- **Inflexible**: One size does not fit all (libraries need higher coverage than scripts)
- **Hard to change**: Requires code modification
- **No context awareness**: Same thresholds for all projects
- **No gradual improvement**: Either pass or fail, no middle ground

**Example**:

```python
# Hard-coded threshold
MIN_COVERAGE = 80

if coverage < MIN_COVERAGE:
    raise QualityGateError(f"Coverage {coverage}% is below {MIN_COVERAGE}%")
```

**Problem**: A research script with 3 test files doesn't need 80% coverage, but a library does.

### Option 2: Configuration File with Overrides (Rejected)

**Description**: Use a configuration file (e.g., `.quality-gates.yml`) with project-specific overrides.

**Pros**:

- Per-project configuration
- Easy to change without code modification
- Can store in version control

**Cons**:

- **Configuration drift**: Different projects have different configs
- **No standard**: Hard to know what "good" thresholds are
- **No gradual improvement**: Still binary pass/fail
- **Maintenance burden**: Every project needs custom config

**Example**:

```yaml
# .quality-gates.yml
coverage:
  min: 80
  max: 100

complexity:
  max: 15

security:
  max_severity: "MEDIUM"
```

**Problem**: Developers just lower thresholds to pass quality gates instead of improving code.

### Option 3: Tiered Quality Gates with Ratchet System (SELECTED)

**Description**: Use tiered thresholds (Bronze/Silver/Gold) with a ratchet system that only allows improvement, never regression.

**Pros**:

- **Context-aware**: Different tiers for different project types
- **Gradual improvement**: Ratchet system prevents regression
- **Clear expectations**: Bronze → Silver → Gold progression
- **Configurable**: Can set initial tier and target tier
- **CI/CD integration**: Clear pass/fail with actionable feedback
- **Temporary exemptions**: Can exempt specific files with tracking

**Cons**:

- More complex implementation
- Requires tracking baseline metrics
- Need to define tier boundaries

**Decision**: Selected as best balance of strictness, flexibility, and gradual improvement.

## Decision Outcome

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Quality Context Detection                 │
│  (Detect project type: library, application, script, etc.)  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  Quality Tier Selection                     │
│  ┌──────────────┬──────────────┬────────────────────────┐  │
│  │ Bronze       │ Silver       │ Gold                   │  │
│  │ (Minimum)    │ (Standard)   │ (Excellence)           │  │
│  │              │              │                        │  │
│  │ Cov: 50%     │ Cov: 80%     │ Cov: 95%               │  │
│  │ Cx: 25       │ Cx: 15       │ Cx: 10                 │  │
│  │ Sec: HIGH    │ Sec: MEDIUM  │ Sec: LOW               │  │
│  └──────────────┴──────────────┴────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Quality Gate Enforcement                  │
│  (Check metrics against thresholds, pass/fail with report)  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ratchet System                           │
│  (Update baseline if metrics improved, never allow regression)│
└─────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. Quality Tiers

**File**: `crackerjack/quality/tiers.py`

```python
from enum import Enum
from dataclasses import dataclass
from typing import Final

class QualityTier(str, Enum):
    """Quality tiers with different threshold levels."""

    BRONZE = "bronze"    # Minimum acceptable quality
    SILVER = "silver"    # Standard quality for production code
    GOLD = "gold"        # Excellence level for critical libraries


@dataclass(frozen=True)
class QualityThresholds:
    """Quality thresholds for a specific tier."""

    # Test coverage (percentage)
    min_coverage: float

    # Cyclomatic complexity (per function)
    max_complexity: int

    # Security issues (by severity)
    max_critical_security_issues: int
    max_high_security_issues: int
    max_medium_security_issues: int

    # Type checking (percentage of code with type hints)
    min_type_coverage: float

    # Code duplication (percentage)
    max_duplication: float

    # Documentation (percentage of documented functions)
    min_documentation_coverage: float


# Predefined thresholds for each tier
BRONZE_THRESHOLDS: Final = QualityThresholds(
    min_coverage=50.0,
    max_complexity=25,
    max_critical_security_issues=0,
    max_high_security_issues=5,
    max_medium_security_issues=20,
    min_type_coverage=30.0,
    max_duplication=15.0,
    min_documentation_coverage=20.0,
)

SILVER_THRESHOLDS: Final = QualityThresholds(
    min_coverage=80.0,
    max_complexity=15,
    max_critical_security_issues=0,
    max_high_security_issues=2,
    max_medium_security_issues=10,
    min_type_coverage=60.0,
    max_duplication=5.0,
    min_documentation_coverage=50.0,
)

GOLD_THRESHOLDS: Final = QualityThresholds(
    min_coverage=95.0,
    max_complexity=10,
    max_critical_security_issues=0,
    max_high_security_issues=0,
    max_medium_security_issues=5,
    min_type_coverage=80.0,
    max_duplication=3.0,
    min_documentation_coverage=80.0,
)


THRESHOLDS_BY_TIER: Final[dict[QualityTier, QualityThresholds]] = {
    QualityTier.BRONZE: BRONZE_THRESHOLDS,
    QualityTier.SILVER: SILVER_THRESHOLDS,
    QualityTier.GOLD: GOLD_THRESHOLDS,
}
```

#### 2. Quality Context Detection

**File**: `crackerjack/quality/context.py`

```python
from pathlib import Path
from crackerjack.quality.tiers import QualityTier

class QualityContext:
    """Detect project context and recommend appropriate quality tier."""

    @staticmethod
    def detect_context(project_path: Path) -> QualityTier:
        """
        Detect project context and recommend quality tier.

        Context Detection Rules:
        - Library (publishable package): Recommend GOLD
        - Application (web app, CLI): Recommend SILVER
        - Script/Tool (utility scripts): Recommend BRONZE
        - Test code: Recommend BRONZE
        """
        pyproject = project_path / "pyproject.toml"

        if not pyproject.exists():
            # No pyproject.toml → likely scripts
            return QualityTier.BRONZE

        config = toml_load(pyproject)

        # Check if library (has dependencies)
        dependencies = config.get("project", {}).get("dependencies", [])
        if dependencies:
            # Has dependencies → likely library
            return QualityTier.GOLD

        # Check if application (has entry points)
        entry_points = config.get("project", {}).get("scripts", {})
        if entry_points:
            # Has entry points → likely application
            return QualityTier.SILVER

        # Default to silver
        return QualityTier.SILVER
```

#### 3. Quality Gate Engine

**File**: `crackerjack/quality/gate.py`

```python
from dataclasses import dataclass
from typing import Final

@dataclass(frozen=True)
class QualityMetrics:
    """Measured quality metrics for a project."""

    coverage_percentage: float
    avg_complexity: float
    critical_security_issues: int
    high_security_issues: int
    medium_security_issues: int
    type_coverage_percentage: float
    duplication_percentage: float
    documentation_coverage_percentage: float


@dataclass(frozen=True)
class QualityGateResult:
    """Result of quality gate evaluation."""

    passed: bool
    tier: QualityTier
    metrics: QualityMetrics
    thresholds: QualityThresholds
    violations: list[str]
    warnings: list[str]

    def __str__(self) -> str:
        """Human-readable report."""
        if self.passed:
            return f"✅ Quality gate PASSED at {self.tier.value.upper()} tier"
        else:
            violations = "\n".join(f"  ❌ {v}" for v in self.violations)
            return f"❌ Quality gate FAILED at {self.tier.value.upper()} tier:\n{violations}"


class QualityGateEngine:
    """Evaluate quality metrics against thresholds."""

    def __init__(
        self,
        tier: QualityTier = QualityTier.SILVER,
        thresholds: QualityThresholds | None = None,
    ) -> None:
        self.tier = tier
        self.thresholds = thresholds or THRESHOLDS_BY_TIER[tier]

    def evaluate(self, metrics: QualityMetrics) -> QualityGateResult:
        """
        Evaluate metrics against thresholds.

        Returns:
            QualityGateResult with pass/fail and detailed violations.
        """
        violations: list[str] = []
        warnings: list[str] = []

        # Check coverage
        if metrics.coverage_percentage < self.thresholds.min_coverage:
            violations.append(
                f"Coverage {metrics.coverage_percentage:.1f}% is below "
                f"threshold {self.thresholds.min_coverage:.1f}%"
            )

        # Check complexity
        if metrics.avg_complexity > self.thresholds.max_complexity:
            violations.append(
                f"Complexity {metrics.avg_complexity:.1f} exceeds "
                f"threshold {self.thresholds.max_complexity}"
            )

        # Check security issues
        if metrics.critical_security_issues > self.thresholds.max_critical_security_issues:
            violations.append(
                f"Critical security issues: {metrics.critical_security_issues} "
                f"(threshold: {self.thresholds.max_critical_security_issues})"
            )

        # ... (other checks)

        passed = len(violations) == 0

        return QualityGateResult(
            passed=passed,
            tier=self.tier,
            metrics=metrics,
            thresholds=self.thresholds,
            violations=violations,
            warnings=warnings,
        )
```

#### 4. Ratchet System

**File**: `crackerjack/quality/ratchet.py`

```python
from pathlib import Path
import json
from dataclasses import dataclass, asdict

@dataclass
class QualityBaseline:
    """Baseline quality metrics that cannot regress."""

    coverage_percentage: float
    avg_complexity: float
    critical_security_issues: int
    high_security_issues: int
    medium_security_issues: int
    type_coverage_percentage: float
    duplication_percentage: float

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "QualityBaseline":
        """Deserialize from dict."""
        return cls(**data)


class QualityRatchet:
    """
    Ratchet system that only allows quality metrics to improve,
    never regress. Implements "coverage ratchet" pattern.
    """

    BASELINE_FILE: Final = ".crackerjack/quality_baseline.json"

    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self.baseline_path = project_path / self.BASELINE_FILE
        self.baseline = self._load_baseline()

    def _load_baseline(self) -> QualityBaseline | None:
        """Load existing baseline if it exists."""
        if not self.baseline_path.exists():
            return None

        with open(self.baseline_path) as f:
            data = json.load(f)
            return QualityBaseline.from_dict(data)

    def check_metrics(self, metrics: QualityMetrics) -> bool:
        """
        Check if metrics meet or exceed baseline.

        Returns:
            True if metrics are acceptable (>= baseline or no baseline)
            False if metrics regressed (< baseline)
        """
        if self.baseline is None:
            # No baseline yet, accept any metrics
            return True

        # Check for regression
        if metrics.coverage_percentage < self.baseline.coverage_percentage:
            raise QualityRegressionError(
                f"Coverage regressed from {self.baseline.coverage_percentage:.1f}% "
                f"to {metrics.coverage_percentage:.1f}%"
            )

        if metrics.avg_complexity > self.baseline.avg_complexity:
            raise QualityRegressionError(
                f"Complexity increased from {self.baseline.avg_complexity:.1f} "
                f"to {metrics.avg_complexity:.1f}"
            )

        # ... (other checks)

        return True

    def update_baseline(self, metrics: QualityMetrics) -> None:
        """
        Update baseline if metrics improved.

        Only updates if:
        1. No baseline exists yet
        2. Metrics improved (higher coverage, lower complexity, etc.)
        """
        if self.baseline is None:
            # First time, set baseline
            self.baseline = QualityBaseline(
                coverage_percentage=metrics.coverage_percentage,
                avg_complexity=metrics.avg_complexity,
                critical_security_issues=metrics.critical_security_issues,
                high_security_issues=metrics.high_security_issues,
                medium_security_issues=metrics.medium_security_issues,
                type_coverage_percentage=metrics.type_coverage_percentage,
                duplication_percentage=metrics.duplication_percentage,
            )
        else:
            # Update only if improved
            improved = False

            if metrics.coverage_percentage > self.baseline.coverage_percentage:
                self.baseline.coverage_percentage = metrics.coverage_percentage
                improved = True

            if metrics.avg_complexity < self.baseline.avg_complexity:
                self.baseline.avg_complexity = metrics.avg_complexity
                improved = True

            # ... (other improvements)

            if not improved:
                return  # No improvement, don't update

        # Save to file
        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.baseline_path, "w") as f:
            json.dump(self.baseline.to_dict(), f, indent=2)
```

#### 5. Exemption System

**File**: `crackerjack/quality/exemptions.py`

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

@dataclass
class QualityExemption:
    """Temporary exemption from quality gate for a specific file."""

    file_path: str
    exemption_type: str  # "coverage", "complexity", "security", etc.
    reason: str
    exemption_date: datetime
    expires: datetime | None = None
    issued_by: str = ""  # Developer who issued exemption


class ExemptionManager:
    """Manage quality exemptions with tracking and expiration."""

    EXEMPTIONS_FILE: Final = ".crackerjack/exemptions.yml"

    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self.exemptions_path = project_path / self.EXEMPTIONS_FILE
        self.exemptions = self._load_exemptions()

    def is_exempt(
        self,
        file_path: str,
        exemption_type: str,
    ) -> bool:
        """Check if file is exempt from specific quality check."""
        for exemption in self.exemptions:
            if exemption.file_path == file_path and exemption.exemption_type == exemption_type:
                # Check if expired
                if exemption.expires and datetime.now() > exemption.expires:
                    return False  # Exemption expired

                return True  # Exemption active

        return False  # No exemption

    def add_exemption(
        self,
        file_path: str,
        exemption_type: str,
        reason: str,
        expires: datetime | None = None,
    ) -> None:
        """Add a new exemption with tracking."""
        exemption = QualityExemption(
            file_path=file_path,
            exemption_type=exemption_type,
            reason=reason,
            exemption_date=datetime.now(),
            expires=expires,
            issued_by=getenv("USER", "unknown"),
        )

        self.exemptions.append(exemption)
        self._save_exemptions()

    def cleanup_expired(self) -> None:
        """Remove expired exemptions."""
        now = datetime.now()
        self.exemptions = [
            e for e in self.exemptions
            if e.expires is None or e.expires > now
        ]
        self._save_exemptions()
```

### Configuration

**File**: `settings/quality.yml`

```yaml
# Quality gate configuration
quality:
  # Target tier (bronze, silver, gold)
  # Default: auto-detect from project context
  target_tier: "silver"  # or "auto"

  # Ratchet system (coverage ratchet)
  ratchet:
    enabled: true
    baseline_file: ".crackerjack/quality_baseline.json"
    auto_update: true  # Update baseline when metrics improve

  # Exemptions
  exemptions:
    enabled: true
    file: ".crackerjack/exemptions.yml"
    require_reason: true
    default_expiry_days: 30  # Exemptions expire after 30 days

  # Quality metrics collection
  metrics:
    coverage:
      enabled: true
      tool: "pytest-cov"

    complexity:
      enabled: true
      tool: "complexipy"

    security:
      enabled: true
      tool: "bandit"

    type_coverage:
      enabled: true
      tool: "zuban"
```

### Usage Examples

#### Example 1: Basic Quality Gate

```python
from crackerjack.quality import QualityGateEngine, QualityMetrics, QualityTier

# Measure metrics
metrics = QualityMetrics(
    coverage_percentage=85.0,
    avg_complexity=12.5,
    critical_security_issues=0,
    high_security_issues=1,
    medium_security_issues=5,
    type_coverage_percentage=65.0,
    duplication_percentage=4.5,
    documentation_coverage_percentage=55.0,
)

# Evaluate against silver tier
gate = QualityGateEngine(tier=QualityTier.SILVER)
result = gate.evaluate(metrics)

print(result)
# Output: ✅ Quality gate PASSED at SILVER tier
```

#### Example 2: Quality Gate Failure

```python
metrics = QualityMetrics(
    coverage_percentage=45.0,  # Below silver threshold (80%)
    avg_complexity=12.5,
    critical_security_issues=0,
    high_security_issues=1,
    medium_security_issues=5,
    type_coverage_percentage=65.0,
    duplication_percentage=4.5,
    documentation_coverage_percentage=55.0,
)

gate = QualityGateEngine(tier=QualityTier.SILVER)
result = gate.evaluate(metrics)

print(result)
# Output:
# ❌ Quality gate FAILED at SILVER tier:
#   ❌ Coverage 45.0% is below threshold 80.0%
```

#### Example 3: Ratchet System

```python
from crackerjack.quality import QualityRatchet, QualityMetrics
from pathlib import Path

ratchet = QualityRatchet(Path.cwd())

# First run: No baseline, accepts any metrics
metrics1 = QualityMetrics(coverage_percentage=60.0, ...)
ratchet.check_metrics(metrics1)  # Pass
ratchet.update_baseline(metrics1)  # Sets baseline at 60%

# Second run: Coverage improved to 70%
metrics2 = QualityMetrics(coverage_percentage=70.0, ...)
ratchet.check_metrics(metrics2)  # Pass
ratchet.update_baseline(metrics2)  # Updates baseline to 70%

# Third run: Coverage regressed to 65%
metrics3 = QualityMetrics(coverage_percentage=65.0, ...)
ratchet.check_metrics(metrics3)  # FAILS! Regression from 70% to 65%

# Output:
# QualityRegressionError: Coverage regressed from 70.0% to 65.0%
```

#### Example 4: Temporary Exemption

```python
from crackerjack.quality import ExemptionManager
from pathlib import Path
from datetime import datetime, timedelta

exemptions = ExemptionManager(Path.cwd())

# Exempt legacy file from coverage requirements
exemptions.add_exemption(
    file_path="src/legacy_module.py",
    exemption_type="coverage",
    reason="Legacy module, planned rewrite in Q2 2025",
    expires=datetime.now() + timedelta(days=90),  # Expires in 90 days
)

# Now quality gate will skip coverage check for this file
```

### CI/CD Integration

**GitHub Actions**:

```yaml
name: Quality Gate

on: [pull_request]

jobs:
  quality-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install Crackerjack
        run: pip install crackerjack

      - name: Run Quality Gate
        run: |
          python -m crackerjack run --quality-gate --tier silver

      - name: Comment PR with Results
        if: always()
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const result = fs.readFileSync('quality-gate-result.json', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: result
            });
```

## Consequences

### Positive

1. **Context-Aware**: Different tiers for different project types
1. **Gradual Improvement**: Ratchet system prevents regression while allowing improvement
1. **Clear Expectations**: Bronze → Silver → Gold progression is intuitive
1. **Flexible**: Can exempt specific files with tracking
1. **CI/CD Ready**: Clear pass/fail with actionable feedback
1. **Motivational**: Milestones encourage improvement (50% → 80% → 95%)

### Negative

1. **Complexity**: More complex than simple pass/fail
1. **Configuration**: Need to set initial tier and target tier
1. **Exemption Tracking**: Requires discipline to review and expire exemptions
1. **Baseline Management**: Need to commit baseline to version control

### Risks

| Risk | Mitigation |
|------|------------|
| Tier set too low | Use auto-detect to recommend appropriate tier |
| Exemptions never expire | Set default expiry of 30 days |
| Baseline conflicts in team | Commit baseline to version control |
| Quality gate blocks deployment | Allow manual override with justification |

## Quality Metrics Reference

**By Tier**:

| Metric | Bronze | Silver | Gold |
|--------|--------|--------|------|
| Coverage | ≥50% | ≥80% | ≥95% |
| Complexity | ≤25 | ≤15 | ≤10 |
| Critical Security | 0 | 0 | 0 |
| High Security | ≤5 | ≤2 | 0 |
| Medium Security | ≤20 | ≤10 | ≤5 |
| Type Coverage | ≥30% | ≥60% | ≥80% |
| Duplication | ≤15% | ≤5% | ≤3% |
| Documentation | ≥20% | ≥50% | ≥80% |

## Related Decisions

- **ADR-001**: MCP-first architecture with FastMCP
- **ADR-002**: Multi-agent quality check orchestration
- **ADR-003**: Property-based testing with Hypothesis

## References

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-01-28 | Les Leslie | Initial ADR creation |
| 2025-02-01 | Les Leslie | Added exemption system examples |
| 2025-02-03 | Les Leslie | Added CI/CD integration examples |
