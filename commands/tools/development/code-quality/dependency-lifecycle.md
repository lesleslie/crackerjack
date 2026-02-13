______________________________________________________________________

title: Dependency Lifecycle Management
owner: Platform Engineering Guild
last_reviewed: 2025-10-01
supported_platforms:

- macOS
- Linux
  required_scripts:
- scripts/agent_metadata_audit.py
- scripts/dependency_report.py
  risk: medium
  id: 01K6EEP8QJFB1XTCXAWQ09YSAB
  status: active
  category: development/code-quality
  agents:
  - python-pro
  - javascript-pro
  - golang-pro
  - security-auditor
    tags:
  - dependencies
  - security
  - vulnerabilities
  - automation
  - supply-chain

______________________________________________________________________

## Dependency Lifecycle Management

You are a dependency management expert specializing in auditing, upgrading, and securing software dependencies across multiple ecosystems. Design comprehensive dependency management workflows with vulnerability detection, automated upgrades, license compliance, and supply chain security for Node.js, Python, Go, Rust, and other ecosystems.

## Context

The user needs a unified approach to manage dependencies across their codebase - detecting vulnerabilities, planning upgrades, ensuring license compliance, and automating dependency maintenance. Focus on production-ready patterns that balance security, stability, and developer velocity.

## Requirements for: $ARGUMENTS

1. **Dependency Auditing** (`MODE=audit`):

   - Vulnerability scanning (CVE detection)
   - License compliance checking
   - Outdated package identification
   - Supply chain risk assessment
   - SBOM (Software Bill of Materials) generation

1. **Dependency Upgrades** (`MODE=upgrade`):

   - Semantic versioning analysis
   - Breaking change detection
   - Automated PR generation
   - Rollback procedures
   - Testing automation

1. **Environment Bootstrap** (`MODE=bootstrap`):

   - Development environment setup
   - Tool version management
   - Reproducible builds
   - Container definitions

1. **Ecosystem Support**:

   - Node.js (npm, yarn, pnpm)
   - Python (pip, poetry, uv)
   - Go (go modules)
   - Rust (cargo)
   - Java (maven, gradle)

______________________________________________________________________

## Inputs

- `$PROJECT_PATH` — Absolute path to repository
- `$MODE` — Operation mode: `audit`, `upgrade`, or `bootstrap`
- `$SEVERITY_THRESHOLD` — CVSS cut-off for vulnerabilities (default: 7.0)
- `$ECOSYSTEM` — Optional: Specific ecosystem to target (default: auto-detect all)
- `$AUTO_FIX` — Optional: Automatically apply safe upgrades (default: false)

______________________________________________________________________

## MODE=audit: Vulnerability & Compliance Audit

### 1. Multi-Ecosystem Vulnerability Scanner

```python
# dependency_audit.py
import subprocess
import json
from typing import Dict, List
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Vulnerability:
    package: str
    version: str
    vulnerability_id: str
    severity: str
    cvss_score: float
    fixed_version: str
    description: str


class DependencyAuditor:
    def __init__(self, project_path: str, severity_threshold: float = 7.0):
        self.project_path = Path(project_path)
        self.severity_threshold = severity_threshold
        self.vulnerabilities: List[Vulnerability] = []

    def detect_ecosystems(self) -> Dict[str, Path]:
        """Detect which package managers are in use"""
        ecosystems = {}

        manifest_files = {
            "npm": ["package.json", "package-lock.json"],
            "python": ["requirements.txt", "pyproject.toml", "Pipfile"],
            "go": ["go.mod", "go.sum"],
            "rust": ["Cargo.toml", "Cargo.lock"],
            "ruby": ["Gemfile", "Gemfile.lock"],
        }

        for ecosystem, files in manifest_files.items():
            for file in files:
                manifest = self.project_path / file
                if manifest.exists():
                    ecosystems[ecosystem] = manifest
                    break

        return ecosystems

    def audit_npm(self, manifest: Path) -> List[Vulnerability]:
        """Audit Node.js dependencies"""
        print(f"Auditing NPM dependencies in {manifest.parent}...")

        try:
            result = subprocess.run(
                ["npm", "audit", "--json"],
                cwd=manifest.parent,
                capture_output=True,
                text=True,
                check=False,
            )

            data = json.loads(result.stdout)
            vulns = []

            if "vulnerabilities" in data:
                for pkg, details in data["vulnerabilities"].items():
                    severity = details.get("severity", "unknown")
                    cvss_score = self._severity_to_cvss(severity)

                    if cvss_score >= self.severity_threshold:
                        vulns.append(
                            Vulnerability(
                                package=pkg,
                                version=details.get("range", "unknown"),
                                vulnerability_id=details.get("via", [{}])[0].get(
                                    "url", "N/A"
                                ),
                                severity=severity,
                                cvss_score=cvss_score,
                                fixed_version=details.get("fixAvailable", {}).get(
                                    "version", "N/A"
                                ),
                                description=details.get("via", [{}])[0].get(
                                    "title", ""
                                ),
                            )
                        )

            return vulns

        except Exception as e:
            print(f"Error auditing NPM: {e}")
            return []

    def audit_python(self, manifest: Path) -> List[Vulnerability]:
        """Audit Python dependencies using pip-audit or safety"""
        print(f"Auditing Python dependencies in {manifest.parent}...")

        try:
            # Using pip-audit (install with: pip install pip-audit)
            result = subprocess.run(
                ["pip-audit", "--format", "json", "--requirement", str(manifest)],
                capture_output=True,
                text=True,
                check=False,
            )

            data = json.loads(result.stdout)
            vulns = []

            for vuln_data in data.get("dependencies", []):
                for vuln in vuln_data.get("vulns", []):
                    cvss_score = float(vuln.get("cvss", 0))

                    if cvss_score >= self.severity_threshold:
                        vulns.append(
                            Vulnerability(
                                package=vuln_data.get("name"),
                                version=vuln_data.get("version"),
                                vulnerability_id=vuln.get("id"),
                                severity=self._cvss_to_severity(cvss_score),
                                cvss_score=cvss_score,
                                fixed_version=vuln.get("fix_versions", ["N/A"])[0],
                                description=vuln.get("description", ""),
                            )
                        )

            return vulns

        except Exception as e:
            print(f"Error auditing Python: {e}")
            return []

    def audit_go(self, manifest: Path) -> List[Vulnerability]:
        """Audit Go dependencies using govulncheck"""
        print(f"Auditing Go dependencies in {manifest.parent}...")

        try:
            result = subprocess.run(
                ["govulncheck", "-json", "./..."],
                cwd=manifest.parent,
                capture_output=True,
                text=True,
                check=False,
            )

            # Parse govulncheck JSON output
            vulns = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                data = json.loads(line)
                if data.get("finding"):
                    finding = data["finding"]
                    osv = finding.get("osv", {})

                    # Calculate severity from CVSS
                    cvss_score = self._parse_go_severity(osv)

                    if cvss_score >= self.severity_threshold:
                        vulns.append(
                            Vulnerability(
                                package=finding.get("package"),
                                version=finding.get("version"),
                                vulnerability_id=osv.get("id"),
                                severity=self._cvss_to_severity(cvss_score),
                                cvss_score=cvss_score,
                                fixed_version=finding.get("fixed", "N/A"),
                                description=osv.get("summary", ""),
                            )
                        )

            return vulns

        except Exception as e:
            print(f"Error auditing Go: {e}")
            return []

    def run_audit(self) -> Dict[str, List[Vulnerability]]:
        """Run audit across all detected ecosystems"""
        ecosystems = self.detect_ecosystems()
        results = {}

        for ecosystem, manifest in ecosystems.items():
            if ecosystem == "npm":
                results["npm"] = self.audit_npm(manifest)
            elif ecosystem == "python":
                results["python"] = self.audit_python(manifest)
            elif ecosystem == "go":
                results["go"] = self.audit_go(manifest)

        return results

    def generate_report(self, results: Dict[str, List[Vulnerability]]) -> str:
        """Generate Markdown report"""
        report = "# Dependency Vulnerability Report\n\n"
        report += f"**Severity Threshold:** {self.severity_threshold} CVSS\n\n"

        total_vulns = sum(len(vulns) for vulns in results.values())
        report += f"**Total Vulnerabilities Found:** {total_vulns}\n\n"

        for ecosystem, vulns in results.items():
            if not vulns:
                continue

            report += f"## {ecosystem.upper()} ({len(vulns)} vulnerabilities)\n\n"

            # Group by severity
            critical = [v for v in vulns if v.cvss_score >= 9.0]
            high = [v for v in vulns if 7.0 <= v.cvss_score < 9.0]
            medium = [v for v in vulns if 4.0 <= v.cvss_score < 7.0]

            if critical:
                report += f"### 🔴 Critical ({len(critical)})\n\n"
                for v in critical:
                    report += self._format_vulnerability(v)

            if high:
                report += f"### 🟠 High ({len(high)})\n\n"
                for v in high:
                    report += self._format_vulnerability(v)

            if medium:
                report += f"### 🟡 Medium ({len(medium)})\n\n"
                for v in medium:
                    report += self._format_vulnerability(v)

        return report

    def _format_vulnerability(self, v: Vulnerability) -> str:
        return f"""
**{v.package}** ({v.version})
- **Vulnerability:** {v.vulnerability_id}
- **CVSS:** {v.cvss_score} ({v.severity})
- **Fix:** Upgrade to {v.fixed_version}
- **Description:** {v.description}

"""

    def _severity_to_cvss(self, severity: str) -> float:
        """Convert severity string to approximate CVSS score"""
        severity_map = {
            "critical": 9.5,
            "high": 7.5,
            "moderate": 5.5,
            "low": 3.0,
            "info": 0.0,
        }
        return severity_map.get(severity.lower(), 0.0)

    def _cvss_to_severity(self, cvss: float) -> str:
        """Convert CVSS score to severity"""
        if cvss >= 9.0:
            return "critical"
        elif cvss >= 7.0:
            return "high"
        elif cvss >= 4.0:
            return "moderate"
        else:
            return "low"

    def _parse_go_severity(self, osv: dict) -> float:
        """Extract CVSS from Go OSV data"""
        # govulncheck uses OSV format
        severity = osv.get("database_specific", {}).get("severity", "MODERATE")
        return self._severity_to_cvss(severity)


# Usage
if __name__ == "__main__":
    import sys

    project_path = sys.argv[1] if len(sys.argv) > 1 else "."
    severity_threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 7.0

    auditor = DependencyAuditor(project_path, severity_threshold)

    print("Detecting ecosystems...")
    ecosystems = auditor.detect_ecosystems()
    print(f"Found ecosystems: {list(ecosystems.keys())}")

    print("\nRunning vulnerability scan...")
    results = auditor.run_audit()

    print("\nGenerating report...")
    report = auditor.generate_report(results)

    # Save report
    with open("dependency-audit-report.md", "w") as f:
        f.write(report)

    print(f"\nReport saved to dependency-audit-report.md")
```

### 2. License Compliance Scanner

```python
# license_scanner.py
import subprocess
import json
from typing import Dict, List


class LicenseScanner:
    """Scan for license compliance issues"""

    APPROVED_LICENSES = [
        "MIT",
        "Apache-2.0",
        "BSD-3-Clause",
        "BSD-2-Clause",
        "ISC",
        "CC0-1.0",
        "Unlicense",
        "Python-2.0",
    ]

    COPYLEFT_LICENSES = [
        "GPL-2.0",
        "GPL-3.0",
        "LGPL-2.1",
        "LGPL-3.0",
        "AGPL-3.0",
        "MPL-2.0",
        "EPL-2.0",
    ]

    def scan_npm_licenses(self, project_path: str) -> List[Dict]:
        """Scan NPM packages for license issues"""
        result = subprocess.run(
            ["npx", "license-checker", "--json"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )

        licenses = json.loads(result.stdout)
        issues = []

        for package, details in licenses.items():
            license_type = details.get("licenses", "UNKNOWN")

            if license_type == "UNKNOWN":
                issues.append(
                    {
                        "package": package,
                        "license": "UNKNOWN",
                        "severity": "high",
                        "reason": "License not specified",
                    }
                )
            elif license_type in self.COPYLEFT_LICENSES:
                issues.append(
                    {
                        "package": package,
                        "license": license_type,
                        "severity": "medium",
                        "reason": "Copyleft license requires legal review",
                    }
                )

        return issues

    def scan_python_licenses(self, project_path: str) -> List[Dict]:
        """Scan Python packages for license issues"""
        result = subprocess.run(
            ["pip-licenses", "--format=json"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )

        licenses = json.loads(result.stdout)
        issues = []

        for pkg in licenses:
            license_type = pkg.get("License", "UNKNOWN")

            if license_type == "UNKNOWN":
                issues.append(
                    {
                        "package": pkg.get("Name"),
                        "license": "UNKNOWN",
                        "severity": "high",
                        "reason": "License not specified",
                    }
                )

        return issues
```

______________________________________________________________________

## MODE=upgrade: Automated Dependency Upgrades

### 1. Upgrade Strategy Generator

```python
# upgrade_planner.py
import subprocess
import json
import semver
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class UpgradePlan:
    package: str
    current_version: str
    latest_version: str
    upgrade_type: str  # major, minor, patch
    breaking_changes: bool
    changelog_url: str
    confidence: str  # high, medium, low


class UpgradePlanner:
    def __init__(self, project_path: str):
        self.project_path = project_path

    def analyze_npm_upgrades(self) -> List[UpgradePlan]:
        """Analyze available NPM upgrades"""
        # Get outdated packages
        result = subprocess.run(
            ["npm", "outdated", "--json"],
            cwd=self.project_path,
            capture_output=True,
            text=True,
            check=False,
        )

        outdated = json.loads(result.stdout) if result.stdout else {}
        plans = []

        for package, details in outdated.items():
            current = details.get("current", "0.0.0")
            latest = details.get("latest", "0.0.0")

            upgrade_type = self._determine_upgrade_type(current, latest)
            breaking = upgrade_type == "major"

            plans.append(
                UpgradePlan(
                    package=package,
                    current_version=current,
                    latest_version=latest,
                    upgrade_type=upgrade_type,
                    breaking_changes=breaking,
                    changelog_url=f"https://github.com/{package}/blob/main/CHANGELOG.md",
                    confidence="high"
                    if upgrade_type == "patch"
                    else "medium"
                    if upgrade_type == "minor"
                    else "low",
                )
            )

        return plans

    def generate_upgrade_commands(
        self, plans: List[UpgradePlan], safe_only: bool = True
    ) -> List[str]:
        """Generate upgrade commands"""
        commands = []

        # Group by upgrade type
        patch_upgrades = [p for p in plans if p.upgrade_type == "patch"]
        minor_upgrades = [p for p in plans if p.upgrade_type == "minor"]
        major_upgrades = [p for p in plans if p.upgrade_type == "major"]

        if patch_upgrades:
            packages = " ".join(
                [f"{p.package}@{p.latest_version}" for p in patch_upgrades]
            )
            commands.append(f"# Patch upgrades (safe)")
            commands.append(f"npm install {packages}")
            commands.append("")

        if minor_upgrades and not safe_only:
            packages = " ".join(
                [f"{p.package}@{p.latest_version}" for p in minor_upgrades]
            )
            commands.append(f"# Minor upgrades (review recommended)")
            commands.append(f"npm install {packages}")
            commands.append("")

        if major_upgrades and not safe_only:
            commands.append(f"# Major upgrades (BREAKING CHANGES - review required)")
            for p in major_upgrades:
                commands.append(
                    f"# {p.package}: {p.current_version} → {p.latest_version}"
                )
                commands.append(f"# Changelog: {p.changelog_url}")
                commands.append(f"npm install {p.package}@{p.latest_version}")
            commands.append("")

        return commands

    def _determine_upgrade_type(self, current: str, latest: str) -> str:
        """Determine if upgrade is major, minor, or patch"""
        try:
            curr_ver = semver.VersionInfo.parse(current.lstrip("v^~"))
            latest_ver = semver.VersionInfo.parse(latest.lstrip("v^~"))

            if latest_ver.major > curr_ver.major:
                return "major"
            elif latest_ver.minor > curr_ver.minor:
                return "minor"
            else:
                return "patch"
        except:
            return "unknown"


# Example usage
if __name__ == "__main__":
    planner = UpgradePlanner(".")

    plans = planner.analyze_npm_upgrades()
    print(f"Found {len(plans)} upgradeable packages\n")

    # Generate safe upgrade commands
    commands = planner.generate_upgrade_commands(plans, safe_only=True)
    print("Safe upgrade commands:")
    print("\n".join(commands))
```

### 2. Automated PR Generator

```bash
#!/bin/bash
# create-dependency-pr.sh

set -e

BRANCH_NAME="deps/automated-upgrade-$(date +%Y%m%d)"
COMMIT_MESSAGE="chore(deps): automated dependency upgrades"

# Create branch
git checkout -b "$BRANCH_NAME"

# Run safe upgrades
npm update  # Respects semver ranges in package.json
pip install --upgrade pip-tools
pip-compile --upgrade requirements.in

# Run tests
npm test
pytest

# Commit
git add package*.json requirements.txt
git commit -m "$COMMIT_MESSAGE

Automated dependency upgrades:
- Patches applied for security fixes
- Minor version bumps for new features
- All tests passing

Generated by dependency-lifecycle tool"

# Push
git push origin "$BRANCH_NAME"

# Create PR (using gh CLI)
gh pr create \
  --title "$COMMIT_MESSAGE" \
  --body "Automated dependency upgrade PR

## Changes
$(git diff main...HEAD --stat)

## Testing
- [x] Unit tests passing
- [x] Integration tests passing
- [ ] Manual QA (if needed)

## Checklist
- [x] No breaking changes
- [x] All tests passing
- [x] Dependencies updated in lockfiles
" \
  --label "dependencies" \
  --label "automated"
```

______________________________________________________________________

## MODE=bootstrap: Environment Setup

### 1. Tool Version Manager

```bash
#!/bin/bash
# bootstrap-environment.sh

set -e

echo "Setting up development environment..."

# Detect tools needed
if [ -f "package.json" ]; then
  echo "Installing Node.js tooling..."

  # Install nvm if not present
  if ! command -v nvm &> /dev/null; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
  fi

  # Install Node version from .nvmrc or latest LTS
  if [ -f ".nvmrc" ]; then
    nvm install
  else
    nvm install --lts
  fi

  nvm use

  # Install dependencies
  npm install
fi

if [ -f "pyproject.toml" ] || [ -f "requirements.txt" ]; then
  echo "Installing Python tooling..."

  # Install pyenv if not present
  if ! command -v pyenv &> /dev/null; then
    curl https://pyenv.run | bash
  fi

  # Install Python version from .python-version or 3.11
  if [ -f ".python-version" ]; then
    pyenv install --skip-existing
  else
    pyenv install --skip-existing 3.11
  fi

  # Create virtualenv
  python -m venv .venv
  source .venv/bin/activate

  # Install dependencies
  if [ -f "pyproject.toml" ]; then
    pip install -e .
  else
    pip install -r requirements.txt
  fi
fi

if [ -f "go.mod" ]; then
  echo "Installing Go tooling..."

  # Install Go version manager
  if ! command -v gvm &> /dev/null; then
    bash < <(curl -s -S -L https://raw.githubusercontent.com/moovweb/gvm/master/binscripts/gvm-installer)
  fi

  # Install Go dependencies
  go mod download
fi

echo "Environment setup complete!"
```

______________________________________________________________________

## Security Considerations

### Supply Chain Security

```python
# supply_chain_checker.py
def check_package_integrity(package_name: str, version: str, ecosystem: str):
    """Verify package hasn't been tampered with"""

    if ecosystem == "npm":
        # Check npm public registry signatures
        result = subprocess.run(
            ["npm", "audit", "signatures"], capture_output=True, text=True
        )

        # Parse and verify signatures
        pass

    elif ecosystem == "python":
        # Check PyPI signatures with Sigstore
        result = subprocess.run(
            ["python", "-m", "pip_audit", "--verify"], capture_output=True, text=True
        )


def scan_for_malicious_packages():
    """Scan for known malicious packages"""
    # Use Socket.dev, Snyk, or similar services
    # Check against OSV database
    # Verify package maintainer reputation
    pass
```

### Security Checklist

- [ ] All dependencies scanned for vulnerabilities
- [ ] High/critical CVEs remediated
- [ ] License compliance verified
- [ ] No malicious packages detected
- [ ] Package integrity verified (checksums, signatures)
- [ ] Private packages use authenticated registries
- [ ] Lockfiles committed to version control
- [ ] Automated scanning in CI/CD
- [ ] Security policy documented
- [ ] Incident response plan for supply chain attacks

______________________________________________________________________

## Testing & Validation

### Test Upgrade Safety

```python
# test_upgrades.py
import subprocess
import pytest


def test_dependencies_install():
    """Verify dependencies install without errors"""
    result = subprocess.run(["npm", "install"], capture_output=True, check=True)
    assert result.returncode == 0


def test_no_breaking_changes():
    """Run test suite to verify no breaking changes"""
    result = subprocess.run(["npm", "test"], capture_output=True)
    assert result.returncode == 0, "Tests failed after upgrade"


def test_build_succeeds():
    """Verify build completes successfully"""
    result = subprocess.run(["npm", "run", "build"], capture_output=True)
    assert result.returncode == 0


@pytest.mark.slow
def test_e2e_after_upgrade():
    """Run E2E tests to verify functionality"""
    result = subprocess.run(["npm", "run", "test:e2e"], capture_output=True)
    assert result.returncode == 0
```

### Testing Checklist

- [ ] All tests pass after upgrade
- [ ] Build completes successfully
- [ ] No new deprecation warnings
- [ ] Performance benchmarks maintained
- [ ] Integration tests pass
- [ ] E2E tests pass
- [ ] Manual smoke testing completed
- [ ] Rollback procedure tested

______________________________________________________________________

## Troubleshooting

### Common Issues

#### Issue: Conflicting Dependencies

**Symptoms:**

- Package manager unable to resolve versions
- "Cannot find compatible version" errors
- Circular dependencies

**Solutions:**

1. **Check dependency tree**:

```bash
# NPM
npm list <package-name>

# Python
pipdeptree -p <package-name>

# Go
go mod graph | grep <package-name>
```

2. **Force resolution** (NPM):

```json
{
  "overrides": {
    "package-with-conflict": "^1.2.3"
  }
}
```

3. **Use dependency resolution tools**:

```bash
# NPM
npx npm-check-updates -u

# Python
pip-compile --upgrade
```

______________________________________________________________________

#### Issue: Broken After Upgrade

**Symptoms:**

- Tests failing
- Application crashes
- Unexpected behavior

**Solutions:**

1. **Rollback immediately**:

```bash
git checkout package*.json
npm install
```

2. **Bisect the upgrade**:

```bash
# Upgrade one package at a time
npm install package1@latest
npm test
```

3. **Check changelog**:

```bash
# View changes between versions
npx diff-package package-name old-version new-version
```

______________________________________________________________________

#### Issue: Security Scan False Positives

**Symptoms:**

- Vulnerabilities reported in dev dependencies
- CVEs for unused code paths
- Transitive dependency issues

**Solutions:**

1. **Audit each vulnerability**:

```bash
npm audit --json | jq '.vulnerabilities'
```

2. **Add exceptions** (document why):

```json
{
  "auditExclusions": {
    "CVE-2024-XXXX": "Dev dependency, not in production"
  }
}
```

3. **Override vulnerable transitive deps**:

```json
{
  "overrides": {
    "vulnerable-package": "^safe-version"
  }
}
```

______________________________________________________________________

### Getting Help

**Related Tools:**

- Use `security-auditor` agent for vulnerability assessment
- Use `python-pro` / `javascript-pro` for ecosystem-specific issues
- Use `devops-troubleshooter` for CI/CD integration

**Agents to Consult:**

- `security-auditor` - Security and vulnerability advice
- `python-pro` - Python dependency issues
- `javascript-pro` - Node.js dependency issues
- `golang-pro` - Go module issues

______________________________________________________________________

## Best Practices

1. **Automate Scanning**: Run vulnerability scans in CI/CD on every commit
1. **Pin Dependencies**: Use lockfiles (package-lock.json, poetry.lock)
1. **Update Regularly**: Schedule weekly/monthly dependency updates
1. **Test Thoroughly**: Always run full test suite after upgrades
1. **Review Breaking Changes**: Read changelogs for major version bumps
1. **Separate PRs**: One upgrade per PR for easier review/rollback
1. **Monitor Advisories**: Subscribe to security advisories for your stack
1. **Use Renovate/Dependabot**: Automate dependency update PRs
1. **Verify Sources**: Only install from trusted registries
1. **SBOM Generation**: Generate software bills of materials for compliance

______________________________________________________________________

## Related Agents

**Primary Orchestrators**:

- `security-auditor` - Vulnerability assessment and remediation
- `python-pro` - Python dependency expertise
- `javascript-pro` - Node.js dependency expertise

**Supporting Specialists**:

- `golang-pro` - Go module management
- `devops-troubleshooter` - CI/CD automation
- `observability-incident-lead` - Dependency monitoring

**Quality & Compliance**:

- `qa-strategist` - Testing strategies
- `compliance-check` - License compliance

______________________________________________________________________

## Migration from Deprecated Tools

**From `deps-audit.md`:**

```bash
# Old
./deps-audit.sh

# New
python dependency_audit.py . 7.0
```

**From `deps-upgrade.md`:**

```bash
# Old
./deps-upgrade.sh

# New
python upgrade_planner.py .
```

Both workflows are now unified in this comprehensive dependency lifecycle tool with enhanced capabilities for vulnerability scanning, license compliance, and automated upgrades.
