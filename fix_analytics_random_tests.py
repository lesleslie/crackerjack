#!/usr/bin/env python3
"""Fix random-related test code in test_analytics.py."""

import re

# Read the test file
with open("tests/unit/cli/handlers/test_analytics.py", "r") as f:
    content = f.read()

# Fix test class TestGenerateAnomalySampleData
# Change mock_uniform to mock_random and update return_value setup
content = re.sub(
    r'(@patch\("crackerjack\.cli\.handlers\.analytics\.random"\)\s+def test_\w+\(self, mock_uniform: Mock\) -> None:\s+"""\.[^"]*"""\s+)(mock_uniform\.return_value = 0\.5)',
    r'\1mock_random = Mock()\n        mock_random.uniform.return_value = 0.5',
    content,
    flags=re.DOTALL
)

# Also need to update the parameter name
content = re.sub(
    r'@patch\("crackerjack\.cli\.handlers\.analytics\.random"\)\s+def test_\w+\(self, mock_uniform: Mock\)',
    '@patch("crackerjack.cli.handlers.analytics.random")\n    def test_\\1(self, mock_random: Mock)',
    content,
)

# Fix TestGetSampleMetricValue class
# Need to set up mock_random.uniform to return appropriate values
content = re.sub(
    r'class TestGetSampleMetricValue:.*?(?=\nclass |\Z)',
    lambda m: m.group(0).replace('mock_random.return_value = 0.05',
                                     'mock_random.uniform.return_value = 0.05')
                             .replace('mock_random.return_value = 0.15',
                                     'mock_random.uniform.return_value = 0.15'),
    content,
    flags=re.DOTALL
)

# Also need to handle random.uniform being called multiple times
# The function calls random.random() first to check for anomaly, then random.uniform()
# So we need to mock both
content = re.sub(
    r'(# Test with random value <= 0\.1 \(anomaly\)\s+)(mock_random\.uniform\.return_value = 0\.05)',
    r'\1mock_random.random.return_value = 0.05  # Triggers anomaly\n        mock_random.uniform.return_value = 0.5  # Actual value',
    content,
)

content = re.sub(
    r'(# Normal case\s+)(mock_random\.uniform\.return_value = 0\.15)',
    r'\1mock_random.random.return_value = 0.15  # Normal range\n        mock_random.uniform.return_value = 0.5  # Actual value',
    content,
)

# Fix TestGeneratePredictiveSampleData similarly
content = re.sub(
    r'class TestGeneratePredictiveSampleData:.*?(?=\nclass |\Z)',
    lambda m: m.group(0).replace('mock_random.return_value = 0.5',
                                     'mock_random.random.return_value = 0.5\n        mock_random.uniform.return_value = 0.5'),
    content,
    flags=re.DOTALL
)

# Write back
with open("tests/unit/cli/handlers/test_analytics.py", "w") as f:
    f.write(content)

print("✅ Fixed random mocking in test_analytics.py")
