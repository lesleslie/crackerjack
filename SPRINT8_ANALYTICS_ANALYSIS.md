# analytics.py - Implementation Analysis

**File**: crackerjack/cli/handlers/analytics.py
**Lines**: 432
**Statements**: 165
**Status**: 0% coverage → Target 60-65%

---

## Implementation Structure

### Module Overview

Analytics CLI handlers provide analytics and reporting functionality:

1. **Heatmap Generation**: Generate various heatmaps (error frequency, complexity, quality metrics, test failures)
2. **Anomaly Detection**: ML-based anomaly detection using AnomalyDetector
3. **Predictive Analytics**: Trend forecasting using PredictiveAnalyticsEngine
4. **Report Generation**: Save reports to JSON/HTML formats

---

## Public Functions (13)

### Heatmap Functions (3)

#### 1. handle_heatmap_generation(heatmap, heatmap_type, heatmap_output) (lines 58-103)
**Purpose**: Public handler for heatmap generation
**Parameters**:
- `heatmap: bool` - Whether to generate heatmap
- `heatmap_type: str` - Type of heatmap (error_frequency, complexity, quality_metrics, test_failures)
- `heatmap_output: str | None` - Output file path

**Returns**: `bool` - True if skipped, False if generated

**Logic**:
- Returns True if heatmap=False
- Imports HeatMapGenerator
- Generates heatmap by type using `_generate_heatmap_by_type()`
- Saves output using `_save_heatmap_output()`
- Displays success stats
- Returns False on success

**Raises**: Exception (caught and handled)

#### 2. _generate_heatmap_by_type(generator, heatmap_type, project_root, console) (lines 9-25)
**Purpose**: Generate heatmap by type
**Returns**: Heatmap data or None

**Logic**:
- Calls generator method based on heatmap_type:
  - `error_frequency` → `generate_error_frequency_heatmap()`
  - `complexity` → `generate_code_complexity_heatmap()`
  - `quality_metrics` → `generate_quality_metrics_heatmap()`
  - `test_failures` → `generate_test_failure_heatmap()`
- Prints error for unknown type
- Returns None on unknown type

#### 3. _save_heatmap_output(generator, heatmap_data, heatmap_output, heatmap_type, console) (lines 28-55)
**Purpose**: Save heatmap output to file
**Returns**: `bool` - True if saved successfully

**Logic**:
- If heatmap_output provided:
  - If .html: Generate HTML visualization and save
  - If .json/.csv: Export data and save
  - Otherwise: Print error and return False
- Otherwise: Save to default filename (`heatmap_{type}.html`)
- Returns True on success

---

### Anomaly Detection Functions (4)

#### 4. generate_anomaly_sample_data(detector) (lines 106-128)
**Purpose**: Generate sample anomaly data for testing
**Parameters**: `detector: AnomalyDetector`

**Logic**:
- Generates 50 data points (every 30 minutes over 24 hours)
- For 5 metric types: test_pass_rate, coverage_percentage, complexity_score, execution_time, error_count
- Calls `get_sample_metric_value()` for each
- Adds metrics to detector

#### 5. get_sample_metric_value(metric_type) (lines 130-148)
**Purpose**: Get sample metric value with 10% anomaly rate
**Parameters**: `metric_type: str`
**Returns**: `float`

**Logic**:
- 10% chance of being anomaly (random.random() <= 0.1)
- Returns different ranges for anomalies vs normal:
  - test_pass_rate: 0.3-0.7 (anomaly) vs 0.85-0.98 (normal)
  - coverage_percentage: 40-60 (anomaly) vs 75-95 (normal)
  - complexity_score: 20-35 (anomaly) vs 8-15 (normal)
  - execution_time: 300-600 (anomaly) vs 30-120 (normal)
  - error_count: 8-15 (anomaly) vs 0-3 (normal)
- Uses random.uniform() for values

#### 6. display_anomaly_results(anomalies, baselines) (lines 150-174)
**Purpose**: Display anomaly detection results
**Parameters**:
- `anomalies: list[t.Any]`
- `baselines: dict[str, t.Any]`

**Logic**:
- Prints summary (baseline count, anomaly count)
- If anomalies exist, displays top 5 with color-coded severity

#### 7. save_anomaly_report(anomalies, baselines, anomaly_sensitivity, anomaly_report) (lines 177-213)
**Purpose**: Save anomaly detection report to JSON
**Parameters**:
- `anomalies: list[t.Any]`
- `baselines: dict[str, t.Any]`
- `anomaly_sensitivity: float`
- `anomaly_report: str` - Output path

**Logic**:
- Builds report dict with timestamp, summary, anomalies, baselines
- Writes JSON to file
- Prints success message

#### 8. handle_anomaly_detection(anomaly_detection, anomaly_sensitivity, anomaly_report) (lines 215-251)
**Purpose**: Public handler for anomaly detection
**Parameters**:
- `anomaly_detection: bool`
- `anomaly_sensitivity: float`
- `anomaly_report: str | None`

**Returns**: `bool` - True if skipped, False if generated

**Logic**:
- Returns True if anomaly_detection=False
- Imports AnomalyDetector
- Creates detector with sensitivity
- Generates sample data
- Gets anomalies and baselines
- Displays results
- Saves report if path provided
- Returns False on success

**Raises**: Exception (caught and handled)

---

### Predictive Analytics Functions (4)

#### 9. generate_predictive_sample_data(engine) (lines 254-290)
**Purpose**: Generate sample predictive analytics data
**Parameters**: `engine: PredictiveAnalyticsEngine`
**Returns**: `list[str]` - metric types

**Logic**:
- Generates 48 data points (every hour over 72 hours)
- For 5 metric types with trend factor and noise
- Adds metrics to engine
- Returns list of metric types

#### 10. generate_predictions_summary(engine, metric_types, prediction_periods) (lines 293-322)
**Purpose**: Generate predictions summary
**Returns**: `dict[str, t.Any]` - predictions summary

**Logic**:
- Gets trend summary from engine
- For each metric type:
  - Gets predictions from engine
  - Builds dict with trend and top 5 predictions
- Returns summary dict

#### 11. display_trend_analysis(predictions_summary) (lines 325-354)
**Purpose**: Display trend analysis results
**Parameters**: `predictions_summary: dict[str, t.Any]`

**Logic**:
- Prints header
- For each metric type:
  - Extracts trend direction and strength
  - Color-codes direction
  - Displays next prediction with confidence

#### 12. save_analytics_dashboard(predictions_summary, trend_summary, metric_types, prediction_periods, analytics_dashboard) (lines 356-383)
**Purpose**: Save analytics dashboard to JSON
**Parameters**:
- `predictions_summary: dict[str, t.Any]`
- `trend_summary: dict[str, t.Any]`
- `metric_types: list[str]`
- `prediction_periods: int`
- `analytics_dashboard: str` - Output path

**Logic**:
- Builds dashboard dict with timestamp, summary, trends, predictions
- Writes JSON to file
- Prints success message

#### 13. handle_predictive_analytics(predictive_analytics, prediction_periods, analytics_dashboard) (lines 386-431)
**Purpose**: Public handler for predictive analytics
**Parameters**:
- `predictive_analytics: bool`
- `prediction_periods: int`
- `analytics_dashboard: str | None`

**Returns**: `bool` - True if skipped, False if generated

**Logic**:
- Returns True if predictive_analytics=False
- Imports PredictiveAnalyticsEngine
- Creates engine
- Generates sample data
- Generates predictions summary
- Gets trend summary
- Displays trend analysis
- Saves dashboard if path provided
- Returns False on success

**Raises**: Exception (caught and handled)

---

## Testing Strategy

### Test Groups (estimated 30-35 tests)

#### Group 1: handle_heatmap_generation() (4 tests) ⭐ CRITICAL
- ✅ Returns True when heatmap=False
- ✅ Generates heatmap by correct type
- ✅ Saves heatmap output successfully
- ✅ Returns False when heatmap generated successfully

#### Group 2: _generate_heatmap_by_type() (6 tests)
- ✅ Calls generate_error_frequency_heatmap() for error_frequency
- ✅ Calls generate_code_complexity_heatmap() for complexity
- ✅ Calls generate_quality_metrics_heatmap() for quality_metrics
- ✅ Calls generate_test_failure_heatmap() for test_failures
- ✅ Returns None for unknown heatmap_type
- ✅ Prints error message for unknown type

#### Group 3: _save_heatmap_output() (6 tests) ⭐ CRITICAL
- ✅ Saves HTML output when .html suffix
- ✅ Saves JSON output when .json suffix
- ✅ Saves CSV output when .csv suffix
- ✅ Returns False for unsupported format
- ✅ Saves to default filename when no output path
- ✅ Writes file with correct content

#### Group 4: generate_anomaly_sample_data() (3 tests)
- ✅ Generates 50 data points
- ✅ Covers 5 metric types
- ✅ Adds metrics to detector

#### Group 5: get_sample_metric_value() (6 tests) ⭐ CRITICAL
- ✅ Returns values in correct ranges for each metric type
- ✅ Has 10% anomaly rate
- ✅ test_pass_rate: 0.3-0.7 (anomaly) vs 0.85-0.98 (normal)
- ✅ coverage_percentage: 40-60 (anomaly) vs 75-95 (normal)
- ✅ complexity_score: 20-35 (anomaly) vs 8-15 (normal)
- ✅ execution_time: 300-600 (anomaly) vs 30-120 (normal)

#### Group 6: display_anomaly_results() (4 tests)
- ✅ Prints baseline and anomaly counts
- ✅ Displays top 5 anomalies
- ✅ Color-codes severity levels
- ✅ Handles empty anomaly list

#### Group 7: save_anomaly_report() (4 tests) ⭐ CRITICAL
- ✅ Creates report dict with correct structure
- ✅ Writes JSON to file
- ✅ Includes timestamp, summary, anomalies, baselines
- ✅ Prints success message

#### Group 8: handle_anomaly_detection() (5 tests) ⭐ CRITICAL
- ✅ Returns True when anomaly_detection=False
- ✅ Creates AnomalyDetector with sensitivity
- ✅ Generates sample data
- ✅ Gets anomalies and baselines
- ✅ Saves report when path provided

#### Group 9: generate_predictive_sample_data() (3 tests)
- ✅ Generates 48 data points
- ✅ Covers 5 metric types
- ✅ Adds metrics to engine
- ✅ Returns list of metric types

#### Group 10: generate_predictions_summary() (4 tests)
- ✅ Gets trend summary from engine
- ✅ Calls predict_metric for each type
- ✅ Builds predictions dict correctly
- ✅ Returns summary dict

#### Group 11: display_trend_analysis() (4 tests)
- ✅ Prints trend analysis header
- ✅ Displays direction with color coding
- ✅ Displays next prediction with confidence
- ✅ Handles multiple metric types

#### Group 12: save_analytics_dashboard() (4 tests) ⭐ CRITICAL
- ✅ Creates dashboard dict with correct structure
- ✅ Writes JSON to file
- ✅ Includes timestamp, summary, trends, predictions
- ✅ Prints success message

#### Group 13: handle_predictive_analytics() (5 tests) ⭐ CRITICAL
- ✅ Returns True when predictive_analytics=False
- ✅ Creates PredictiveAnalyticsEngine
- ✅ Generates sample data
- ✅ Generates predictions summary
- ✅ Saves dashboard when path provided

---

## Key Testing Points

### MUST Test:
1. ✅ All public handler functions (handle_heatmap_generation, handle_anomaly_detection, handle_predictive_analytics)
2. ✅ Sample data generation (anomaly and predictive)
3. ✅ Report saving (JSON format, file I/O)
4. ✅ Console output mocking (rich.Console)
5. ✅ External service mocking (HeatMapGenerator, AnomalyDetector, PredictiveAnalyticsEngine)

### MOCK:
1. ✅ HeatMapGenerator and its methods
2. ✅ AnomalyDetector (add_metric, get_anomalies, get_baseline_summary)
3. ✅ PredictiveAnalyticsEngine (add_metric, get_trend_summary, predict_metric)
4. ✅ rich.Console (print method)
5. ✅ Path.write_text for file I/O
6. ✅ random module for sample data generation

### SKIP (intentionally):
1. ❌ Actual heatmap visual quality (just verify method calls)
2. ❌ Exact prediction accuracy (just verify structure)
3. ❌ Random number distribution (just verify ranges)

---

## Estimated Coverage

**Target**: 60-65% of 165 statements = 99-107 statements

**Achievable via**:
- 30-35 test methods
- Testing all public handler functions
- Testing core private helpers
- Testing error handling paths
- Testing report generation

**Uncovered** (~35-40%):
- Some console formatting branches
- Some file I/O edge cases
- Some exception handling paths
- Random value distributions

---

## Dependencies

### Internal
- **HeatMapGenerator** from services.heatmap_generator
- **AnomalyDetector** from services.quality.anomaly_detector
- **PredictiveAnalyticsEngine** from services.ai.predictive_analytics

### External
- **rich.Console** (rich library)
- **json** (standard library)
- **datetime** (standard library)
- **random** (standard library)
- **pathlib.Path** (standard library)
- **typing** (standard library)

---

## Complexity Assessment

**Expected Complexity**: Low-Medium

**Simplifying factors**:
- Mostly handler functions that call other services
- Clear separation of concerns
- Simple data structure manipulation
- No complex algorithms

**Challenges**:
- Multiple external service dependencies
- Rich console output formatting
- File I/O operations
- Random number generation

---

## Test Creation Strategy

1. **Mock External Services**: Prevent actual heatmap/anomaly/predictive analytics execution
2. **Mock Console**: Control rich.Console output
3. **Mock File I/O**: Use tmp_path fixture for report files
4. **Mock Random**: Control sample data generation
5. **Test Handler Logic**: Focus on correct method calls and flow
6. **Test Report Structure**: Verify correct JSON structure
7. **Skip Complex Integrations**: Don't test actual heatmap rendering or ML models

---

## Success Criteria

- ✅ 100% test pass rate
- ✅ 60-65% statement coverage
- ✅ All public handler functions tested
- ✅ Core logic paths covered
- ✅ Error handling tested
- ✅ Report generation tested
- ✅ Zero implementation bugs introduced
