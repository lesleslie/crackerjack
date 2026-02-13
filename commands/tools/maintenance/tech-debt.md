______________________________________________________________________

title: Tech Debt
owner: Platform Reliability Guild
last_reviewed: 2025-02-06
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6EEXCPYXGEWZ0VAB5PB63DD
  category: maintenance

______________________________________________________________________

## Technical Debt Analysis and Remediation

You are a technical debt expert specializing in identifying, quantifying, and prioritizing technical debt in software projects. Analyze the codebase to uncover debt, assess its impact, and create actionable remediation plans.

## Context

The user needs a comprehensive technical debt analysis to understand what's slowing down development, increasing bugs, and creating maintenance challenges. Focus on practical, measurable improvements with clear ROI.

## Requirements

$ARGUMENTS

## Instructions

### 1. Technical Debt Inventory

Conduct a thorough scan for all types of technical debt:

**Code Debt**

- **Duplicated Code**

  - Exact duplicates (copy-paste)
  - Similar logic patterns
  - Repeated business rules
  - Quantify: Lines duplicated, locations

- **Complex Code**

  - High cyclomatic complexity (>10)
  - Deeply nested conditionals (>3 levels)
  - Long methods (>50 lines)
  - God classes (>500 lines, >20 methods)
  - Quantify: Complexity scores, hotspots

- **Poor Structure**

  - Circular dependencies
  - Inappropriate intimacy between classes
  - Feature envy (methods using other class data)
  - Shotgun surgery patterns
  - Quantify: Coupling metrics, change frequency

**Architecture Debt**

- **Design Flaws**

  - Missing abstractions
  - Leaky abstractions
  - Violated architectural boundaries
  - Monolithic components
  - Quantify: Component size, dependency violations

- **Technology Debt**

  - Outdated frameworks/libraries
  - Deprecated API usage
  - Legacy patterns (e.g., callbacks vs promises)
  - Unsupported dependencies
  - Quantify: Version lag, security vulnerabilities

**Testing Debt**

- **Coverage Gaps**

  - Untested code paths
  - Missing edge cases
  - No integration tests
  - Lack of performance tests
  - Quantify: Coverage %, critical paths untested

- **Test Quality**

  - Brittle tests (environment-dependent)
  - Slow test suites
  - Flaky tests
  - No test documentation
  - Quantify: Test runtime, failure rate

**Documentation Debt**

- **Missing Documentation**
  - No API documentation
  - Undocumented complex logic
  - Missing architecture diagrams
  - No onboarding guides
  - Quantify: Undocumented public APIs

**Infrastructure Debt**

- **Deployment Issues**
  - Manual deployment steps
  - No rollback procedures
  - Missing monitoring
  - No performance baselines
  - Quantify: Deployment time, failure rate

### 2. Impact Assessment

Calculate the real cost of each debt item:

**Development Velocity Impact**

```
Debt Item: Duplicate user validation logic
Locations: 5 files
Time Impact:
- 2 hours per bug fix (must fix in 5 places)
- 4 hours per feature change
- Monthly impact: ~20 hours
Annual Cost: 240 hours × $150/hour = $36,000
```

**Quality Impact**

```
Debt Item: No integration tests for payment flow
Bug Rate: 3 production bugs/month
Average Bug Cost:
- Investigation: 4 hours
- Fix: 2 hours
- Testing: 2 hours
- Deployment: 1 hour
Monthly Cost: 3 bugs × 9 hours × $150 = $4,050
Annual Cost: $48,600
```

**Risk Assessment**

- **Critical**: Security vulnerabilities, data loss risk
- **High**: Performance degradation, frequent outages
- **Medium**: Developer frustration, slow feature delivery
- **Low**: Code style issues, minor inefficiencies

### 3. Debt Metrics Dashboard

Create measurable KPIs:

**Code Quality Metrics**

```yaml
Metrics:
  cyclomatic_complexity:
    current: 15.2
    target: 10.0
    files_above_threshold: 45

  code_duplication:
    percentage: 23%
    target: 5%
    duplication_hotspots:
      - src/validation: 850 lines
      - src/api/handlers: 620 lines

  test_coverage:
    unit: 45%
    integration: 12%
    e2e: 5%
    target: 80% / 60% / 30%

  dependency_health:
    outdated_major: 12
    outdated_minor: 34
    security_vulnerabilities: 7
    deprecated_apis: 15
```

**Trend Analysis**

```python
debt_trends = {
    "2024_Q1": {"score": 750, "items": 125},
    "2024_Q2": {"score": 820, "items": 142},
    "2024_Q3": {"score": 890, "items": 156},
    "growth_rate": "18% quarterly",
    "projection": "1200 by 2025_Q1 without intervention",
}
```

### 4. Prioritized Remediation Plan

Create an actionable roadmap based on ROI:

**Quick Wins (High Value, Low Effort)**
Week 1-2:

```
1. Extract duplicate validation logic to shared module
   Effort: 8 hours
   Savings: 20 hours/month
   ROI: 250% in first month

2. Add error monitoring to payment service
   Effort: 4 hours
   Savings: 15 hours/month debugging
   ROI: 375% in first month

3. Automate deployment script
   Effort: 12 hours
   Savings: 2 hours/deployment × 20 deploys/month
   ROI: 333% in first month
```

**Medium-Term Improvements (Month 1-3)**

```
1. Refactor OrderService (God class)
   - Split into 4 focused services
   - Add comprehensive tests
   - Create clear interfaces
   Effort: 60 hours
   Savings: 30 hours/month maintenance
   ROI: Positive after 2 months

2. Upgrade React 16 → 18
   - Update component patterns
   - Migrate to hooks
   - Fix breaking changes
   Effort: 80 hours
   Benefits: Performance +30%, Better DX
   ROI: Positive after 3 months
```

**Long-Term Initiatives (Quarter 2-4)**

```
1. Implement Domain-Driven Design
   - Define bounded contexts
   - Create domain models
   - Establish clear boundaries
   Effort: 200 hours
   Benefits: 50% reduction in coupling
   ROI: Positive after 6 months

2. Comprehensive Test Suite
   - Unit: 80% coverage
   - Integration: 60% coverage
   - E2E: Critical paths
   Effort: 300 hours
   Benefits: 70% reduction in bugs
   ROI: Positive after 4 months
```

### 5. Implementation Strategy

**Incremental Refactoring**

```python
# Phase 1: Add facade over legacy code
class PaymentFacade:
    def __init__(self):
        self.legacy_processor = LegacyPaymentProcessor()

    def process_payment(self, order):
        # New clean interface
        return self.legacy_processor.doPayment(order.to_legacy())


# Phase 2: Implement new service alongside
class PaymentService:
    def process_payment(self, order):
        # Clean implementation
        pass


# Phase 3: Gradual migration
class PaymentFacade:
    def __init__(self):
        self.new_service = PaymentService()
        self.legacy = LegacyPaymentProcessor()

    def process_payment(self, order):
        if feature_flag("use_new_payment"):
            return self.new_service.process_payment(order)
        return self.legacy.doPayment(order.to_legacy())
```

**Team Allocation**

```yaml
Debt_Reduction_Team:
  dedicated_time: "20% sprint capacity"

  roles:
    - tech_lead: "Architecture decisions"
    - senior_dev: "Complex refactoring"
    - dev: "Testing and documentation"

  sprint_goals:
    - sprint_1: "Quick wins completed"
    - sprint_2: "God class refactoring started"
    - sprint_3: "Test coverage >60%"
```

### 6. Prevention Strategy

Implement gates to prevent new debt:

**Automated Quality Gates**

```yaml
pre_commit_hooks:
  - complexity_check: "max 10"
  - duplication_check: "max 5%"
  - test_coverage: "min 80% for new code"

ci_pipeline:
  - dependency_audit: "no high vulnerabilities"
  - performance_test: "no regression >10%"
  - architecture_check: "no new violations"

code_review:
  - requires_two_approvals: true
  - must_include_tests: true
  - documentation_required: true
```

**Debt Budget**

```python
debt_budget = {
    "allowed_monthly_increase": "2%",
    "mandatory_reduction": "5% per quarter",
    "tracking": {
        "complexity": "sonarqube",
        "dependencies": "dependabot",
        "coverage": "codecov",
    },
}
```

### 7. Communication Plan

**Stakeholder Reports**

```markdown
## Executive Summary
- Current debt score: 890 (High)
- Monthly velocity loss: 35%
- Bug rate increase: 45%
- Recommended investment: 500 hours
- Expected ROI: 280% over 12 months

## Key Risks
1. Payment system: 3 critical vulnerabilities
2. Data layer: No backup strategy
3. API: Rate limiting not implemented

## Proposed Actions
1. Immediate: Security patches (this week)
2. Short-term: Core refactoring (1 month)
3. Long-term: Architecture modernization (6 months)
```

**Developer Documentation**

```markdown
## Refactoring Guide
1. Always maintain backward compatibility
2. Write tests before refactoring
3. Use feature flags for gradual rollout
4. Document architectural decisions
5. Measure impact with metrics

## Code Standards
- Complexity limit: 10
- Method length: 20 lines
- Class length: 200 lines
- Test coverage: 80%
- Documentation: All public APIs
```

### 8. Success Metrics

Track progress with clear KPIs:

**Monthly Metrics**

- Debt score reduction: Target -5%
- New bug rate: Target -20%
- Deployment frequency: Target +50%
- Lead time: Target -30%
- Test coverage: Target +10%

**Quarterly Reviews**

- Architecture health score
- Developer satisfaction survey
- Performance benchmarks
- Security audit results
- Cost savings achieved

## Output Format

1. **Debt Inventory**: Comprehensive list categorized by type with metrics
1. **Impact Analysis**: Cost calculations and risk assessments
1. **Prioritized Roadmap**: Quarter-by-quarter plan with clear deliverables
1. **Quick Wins**: Immediate actions for this sprint
1. **Implementation Guide**: Step-by-step refactoring strategies
1. **Prevention Plan**: Processes to avoid accumulating new debt
1. **ROI Projections**: Expected returns on debt reduction investment

Focus on delivering measurable improvements that directly impact development velocity, system reliability, and team morale.

______________________________________________________________________

## Security Considerations

### Authentication & Authorization

- Implement proper authentication mechanisms for accessing this tool
- Use role-based access control (RBAC) to restrict sensitive operations
- Enable audit logging for all security-relevant actions

### Data Protection

- Encrypt sensitive data at rest and in transit
- Implement proper secrets management (see `secrets-management.md`)
- Follow data minimization principles

### Access Control

- Follow principle of least privilege when granting permissions
- Use dedicated service accounts with minimal required permissions
- Implement multi-factor authentication for production access

### Secure Configuration

- Avoid hardcoding credentials in code or configuration files
- Use environment variables or secure vaults for sensitive configuration
- Regularly rotate credentials and API keys

### Monitoring & Auditing

- Log security-relevant events (authentication, authorization failures, data access)
- Implement alerting for suspicious activities
- Maintain immutable audit trails for compliance

______________________________________________________________________

______________________________________________________________________

## Testing & Validation

### Unit Testing

```python
# Example unit tests
import pytest


def test_basic_functionality():
    result = function_under_test(input_value)
    assert result == expected_output


def test_error_handling():
    with pytest.raises(ValueError):
        function_under_test(invalid_input)


def test_edge_cases():
    assert function_under_test([]) == []
    assert function_under_test(None) is None
```

### Integration Testing

```python
# Integration test example
@pytest.mark.integration
def test_end_to_end_workflow():
    # Setup
    resource = create_resource()

    # Execute workflow
    result = process_resource(resource)

    # Verify
    assert result.status == "success"
    assert result.output is not None

    # Cleanup
    delete_resource(resource.id)
```

### Validation

```bash
# Validate configuration files
yamllint config/*.yaml

# Validate scripts
shellcheck scripts/*.sh

# Run linters
pylint src/
flake8 src/
mypy src/
```

### CI/CD Testing

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          pytest tests/ -v --cov=src
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

______________________________________________________________________

______________________________________________________________________

## Troubleshooting

### Common Issues

**Issue 1: Configuration Errors**

**Symptoms:**

- Tool fails to start or execute
- Missing required parameters
- Invalid configuration values

**Solutions:**

1. Verify all required environment variables are set
1. Check configuration file syntax (YAML, JSON)
1. Review logs for specific error messages
1. Validate file paths and permissions

______________________________________________________________________

**Issue 2: Permission Denied Errors**

**Symptoms:**

- Cannot access files or directories
- Operations fail with permission errors
- Insufficient privileges

**Solutions:**

1. Check file/directory permissions: `ls -la`
1. Run with appropriate user privileges
1. Verify user is in required groups: `groups`
1. Use `sudo` for privileged operations when necessary

______________________________________________________________________

**Issue 3: Resource Not Found**

**Symptoms:**

- "File not found" or "Resource not found" errors
- Missing dependencies
- Broken references

**Solutions:**

1. Verify resource paths are correct (use absolute paths)
1. Check that required files exist before execution
1. Ensure dependencies are installed
1. Review environment-specific configurations

______________________________________________________________________

**Issue 4: Timeout or Performance Issues**

**Symptoms:**

- Operations taking longer than expected
- Timeout errors
- Resource exhaustion (CPU, memory, disk)

**Solutions:**

1. Increase timeout values in configuration
1. Optimize queries or operations
1. Add pagination for large datasets
1. Monitor resource usage: `top`, `htop`, `docker stats`
1. Implement caching where appropriate

______________________________________________________________________

### Getting Help

If issues persist after trying these solutions:

1. **Check Logs**: Review application and system logs for detailed error messages
1. **Enable Debug Mode**: Set `LOG_LEVEL=DEBUG` for verbose output
1. **Consult Documentation**: Review related tool documentation in this directory
1. **Contact Support**: Reach out with:
   - Error messages and stack traces
   - Steps to reproduce
   - Environment details (OS, versions, configuration)
   - Relevant log excerpts

______________________________________________________________________
