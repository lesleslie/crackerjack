#!/usr/bin/env python3
"""Fix patch decorators in test_analytics.py to use correct import locations."""

import re

# Read the test file
with open("tests/unit/cli/handlers/test_analytics.py", "r") as f:
    content = f.read()

# Fix HeatMapGenerator patches
content = re.sub(
    r'@patch\("crackerjack\.cli\.handlers\.analytics\.HeatMapGenerator"\)',
    '@patch("crackerjack.services.heatmap_generator.HeatMapGenerator")',
    content
)

# Fix AnomalyDetector patches
content = re.sub(
    r'@patch\("crackerjack\.cli\.handlers\.analytics\.AnomalyDetector"\)',
    '@patch("crackerjack.services.quality.anomaly_detector.AnomalyDetector")',
    content
)

# Fix PredictiveAnalyticsEngine patches
content = re.sub(
    r'@patch\("crackerjack\.cli\.handlers\.analytics\.PredictiveAnalyticsEngine"\)',
    '@patch("crackerjack.services.ai.predictive_analytics.PredictiveAnalyticsEngine")',
    content
)

# Fix random.uniform patches - need to patch at module level since random is imported inside functions
content = re.sub(
    r'@patch\("random\.uniform"\)',
    '@patch("crackerjack.cli.handlers.analytics.random")',
    content
)

# Also fix the mock_uniform.return_value usage to mock_random.uniform.return_value
# This will require test logic changes, so let's handle that separately

# Write back
with open("tests/unit/cli/handlers/test_analytics.py", "w") as f:
    f.write(content)

print("✅ Fixed patch decorators in test_analytics.py")
