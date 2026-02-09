#!/usr/bin/env bash
# Crackerjack Coverage Audit Script
# Runs comprehensive coverage analysis and generates reports

set -e  # Exit on error

echo "🔍 Crackerjack Coverage Audit"
echo "=============================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Change to project directory
cd /Users/les/Projects/crackerjack

echo -e "${BLUE}Step 1: Running coverage analysis...${NC}"
pytest --cov=crackerjack \
       --cov-report=html \
       --cov-report=json \
       --cov-report=term-missing:skip-covered \
       --cov-report=term \
       -v \
       --tb=short

echo ""
echo -e "${BLUE}Step 2: Generating coverage summary...${NC}"
if [ -f coverage.json ]; then
    python3 << 'EOF'
import json
import sys

with open('coverage.json') as f:
    data = json.load(f)

totals = data['totals']
percent_covered = totals['percent_covered']
num_statements = totals['num_statements']
covered_lines = totals['covered_lines']
missing_lines = totals['missing_lines']

print(f"\n📊 Coverage Summary:")
print(f"   Overall Coverage: {percent_covered:.1f}%")
print(f"   Total Statements: {num_statements}")
print(f"   Covered Lines: {covered_lines}")
print(f"   Missing Lines: {missing_lines}")

# Find low-coverage files
print(f"\n📉 Low Coverage Files (<30%):")
low_coverage = []
for filename, file_data in data['files'].items():
    file_pct = file_data['summary']['percent_covered']
    if file_pct < 30.0:
        low_coverage.append((filename, file_pct))

low_coverage.sort(key=lambda x: x[1])  # Sort by coverage ascending

for filename, pct in low_coverage[:20]:  # Top 20 worst
    print(f"   {pct:5.1f}% - {filename}")

if len(low_coverage) > 20:
    print(f"   ... and {len(low_coverage) - 20} more")

print(f"\n✅ High Coverage Files (>70%):")
high_coverage = []
for filename, file_data in data['files'].items():
    file_pct = file_data['summary']['percent_covered']
    if file_pct >= 70.0:
        high_coverage.append((filename, file_pct))

high_coverage.sort(key=lambda x: x[1], reverse=True)  # Sort by coverage descending

for filename, pct in high_coverage[:10]:  # Top 10 best
    print(f"   {pct:5.1f}% - {filename}")
EOF
fi

echo ""
echo -e "${BLUE}Step 3: Opening HTML coverage report...${NC}"
if [ -f htmlcov/index.html ]; then
    open htmlcov/index.html
    echo -e "${GREEN}✓ HTML report opened in browser${NC}"
else
    echo -e "${YELLOW}⚠ HTML report not found${NC}"
fi

echo ""
echo -e "${BLUE}Step 4: Generating module coverage breakdown...${NC}"
pytest --cov=crackerjack/adapters --cov-report=term-missing --cov=crackerjack/agents --cov-report=term-missing --cov=crackerjack/cli --cov-report=term-missing -q

echo ""
echo -e "${GREEN}✓ Coverage audit complete!${NC}"
echo ""
echo "📋 Reports generated:"
echo "   - htmlcov/index.html (HTML report)"
echo "   - coverage.json (JSON data)"
echo ""
echo "🎯 Next steps:"
echo "   1. Review HTML coverage report in browser"
echo "   2. Check COVERAGE_AUDIT_REPORT.md for analysis"
echo "   3. Start implementing tests from CRACKERJACK_TEST_COVERAGE_PLAN.md"
