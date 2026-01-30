# JSON Output Support Audit for Crackerjack Tools

## Summary of Tool Output Formats

### ✅ Tools Already Using JSON (5 tools)

| Tool | Command | JSON Parser Status |
|------|---------|-------------------|
| **zuban** (mypy) | `--output json` | ✅ Implemented - `MypyJSONParser` |
| **bandit** | `--format json` | ✅ Implemented - `BanditJSONParser` |
| **semgrep** | `--json` | ⚠️ Not implemented yet |
| **ruff-check** | `--output-format json` | ✅ Implemented - `RuffJSONParser` |
| **pip-audit** | `--format json` | ⚠️ Not implemented yet |

### 🎯 Tools That Support JSON But Not Currently Enabled (2 tools)

| Tool | JSON Flag | Current Format | Priority |
|------|-----------|----------------|----------|
| **complexipy** | `--output-json` or `-j` | Text | **HIGH** |
| **refurb** | `--format github` (structured) | Text | LOW (not JSON, but structured) |

### ❌ Tools Without JSON Support (13 tools)

| Tool | Format | Reason |
|------|--------|---------|
| **check-yaml** | Text (✗/✓) | Our Python wrapper |
| **check-toml** | Text (✗/✓) | Our Python wrapper |
| **check-json** | Text (✗/✓) | Our Python wrapper |
| **codespell** | Text (`==>`) | No JSON in docs |
| **ruff-format** | Text | Formatter output |
| **mdformat** | Text | Formatter output |
| **check-local-links** | Text | Our Python wrapper |
| **linkcheckmd** | Text | Wrapped by us |
| **creosote** | Text | No JSON support |
| **pyscn** | Text | No JSON support |
| **skylos** | Text (Rust) | No JSON support yet |
| **gitleaks** | Text | Could use `--json` flag! |
| **validate-regex-patterns** | Text | Our Python tool |

### 🔍 Hidden Gems: Tools With JSON We're Not Using

| Tool | Available JSON Flag | Opportunity |
|------|---------------------|-------------|
| **gitleaks** | `--json` or `--report-format json` | **HIGH** - Security tool! |
| **codespell** | `--write-json <file>` | MEDIUM - Writes to file |

## Recommended Actions

### Priority 1: Easy Wins (Tools that already support JSON)

1. **complexipy** - Add `--output-json` flag
   - Current: `complexipy --max-complexity-allowed 15 package`
   - Change: `complexipy --max-complexity-allowed 15 --output-json package > /tmp/complexipy.json`
   - Impact: Complexity parsing becomes more reliable

2. **gitleaks** - Add `--json` or `--report-format json` flag
   - Current: `gitleaks protect -v`
   - Change: `gitleaks protect --report-format json --report /tmp/gitleaks.json`
   - Impact: Security issues parsed correctly

### Priority 2: Implement JSON Parsers

1. **SemgrepJSONParser** - For semgrep security scanning
2. **PipAuditJSONParser** - For vulnerability tracking
3. **ComplexipyJSONParser** - For complexity issues
4. **GitleaksJSONParser** - For security leaks

### Priority 3: Consider Structured Text Formats

1. **refurb** - Use `--format github` for GitHub Actions format
   - More structured than plain text
   - Could create `RefurbGitHubParser`

## Implementation Order

1. ✅ **ruff-check** - Already done
2. ✅ **zuban** (mypy) - Already done
3. ✅ **bandit** - Already done
4. 🔄 **complexipy** - Add JSON flag + parser
5. 🔄 **gitleaks** - Add JSON flag + parser
6. ⏳ **semgrep** - Implement parser
7. ⏳ **pip-audit** - Implement parser
8. ⏳ **refurb** - Consider GitHub format parser

## Current Parser Architecture Status

**Completed JSON Parsers:**
- ✅ RuffJSONParser
- ✅ MypyJSONParser (zuban)
- ✅ BanditJSONParser

**Completed Regex Parsers:**
- ✅ StructuredDataParser (check-yaml, check-toml, check-json)
- ✅ CodespellRegexParser
- ✅ RefurbRegexParser
- ✅ RuffFormatRegexParser
- ✅ ComplexityRegexParser

**Next to Add:**
- ComplexipyJSONParser
- SemgrepJSONParser
- PipAuditJSONParser
- GitleaksJSONParser

## Conclusion

We have **5 tools using JSON** (3 with parsers implemented) and **2 more tools that could easily be converted** to JSON (complexipy, gitleaks).

**Immediate action items:**
1. Add `--output-json` to complexipy command
2. Add `--report-format json` to gitleaks command
3. Implement JSON parsers for: complexipy, semgrep, pip-audit, gitleaks

This would bring us to **9 tools using JSON** out of ~20 total tools, significantly improving parsing reliability.

---

*Generated: 2025-01-30*
*Tools audited: 20*
*JSON support: 25% (5/20)*
*Potential JSON support: 35% (7/20)*
