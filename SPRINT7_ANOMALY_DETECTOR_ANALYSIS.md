# anomaly_detector.py - Implementation Analysis

**File**: crackerjack/services/quality/anomaly_detector.py
**Lines**: 353
**Statements**: 163 (from coverage report)
**Status**: 0% coverage → Target 60-65%

---

## Implementation Structure

### Dataclasses (3)

#### 1. MetricPoint (lines 12-17)
**Purpose**: Single metric measurement point
**Fields**:
- timestamp: datetime
- value: float
- metric_type: str
- metadata: dict[str, Any] (default factory)

#### 2. AnomalyDetection (lines 20-29)
**Purpose**: Detected anomaly result
**Fields**:
- timestamp: datetime
- metric_type: str
- value: float
- expected_range: tuple[float, float] (lower, upper)
- severity: str ("low", "medium", "high", "critical")
- confidence: float (0.0-1.0)
- description: str
- metadata: dict[str, Any] (default factory)

#### 3. BaselineModel (lines 32-42)
**Purpose**: Statistical baseline for a metric
**Fields**:
- metric_type: str
- mean: float
- std_dev: float
- min_value: float
- max_value: float
- sample_count: int
- last_updated: datetime
- seasonal_patterns: dict[str, float] (default factory, e.g., {"hour_13": 75.5})

---

## Class: AnomalyDetector

### Constructor (lines 44-68)
**Parameters**:
- baseline_window: int = 100 (max history size)
- sensitivity: float = 2.0 (z-score multiplier for anomaly threshold)
- min_samples: int = 10 (minimum samples before detection)

**Initialization**:
- metric_history: dict[str, deque[MetricPoint]] - max length = baseline_window
- baselines: dict[str, BaselineModel] = {}
- anomalies: list[AnomalyDetection] = []
- metric_configs: dict[str, dict] - predefined metric configurations:
  - test_pass_rate: critical_threshold=0.8, direction="both"
  - coverage_percentage: critical_threshold=0.7, direction="down"
  - complexity_score: critical_threshold=15.0, direction="up"
  - execution_time: critical_threshold=300.0, direction="up"
  - memory_usage: critical_threshold=1024.0, direction="up"
  - error_count: critical_threshold=5.0, direction="up"

### Public Methods (3)

#### 1. add_metric(metric_type, value, timestamp, metadata) (lines 70-95)
**Purpose**: Main API - add metric point and trigger detection
**Logic**:
- Creates MetricPoint
- Appends to metric_history[metric_type]
- If history >= min_samples:
  - Updates baseline
  - Detects anomaly
  - Appends to self.anomalies if found

#### 2. get_anomalies(metric_type, severity, since, limit) (lines 290-309)
**Purpose**: Retrieve filtered anomalies
**Parameters**:
- metric_type: str | None = None (filter by metric type)
- severity: str | None = None (filter by severity)
- since: datetime | None = None (filter by timestamp)
- limit: int = 100 (max results)
**Returns**: list[AnomalyDetection] sorted by timestamp descending

#### 3. get_baseline_summary() (lines 311-324)
**Purpose**: Get summary of all baselines
**Returns**: dict[str, dict] with mean, std_dev, range, sample_count, last_updated, seasonal_patterns

#### 4. export_model(output_path) (lines 326-352)
**Purpose**: Export baselines and config to JSON file
**Side Effect**: Writes JSON file with baselines and config

---

## Private Methods (11)

#### 1. _update_baseline(metric_type) (lines 97-117)
**Purpose**: Recalculate baseline from history
**Logic**:
- Extract values from metric_history
- Calculate mean, std_dev, min, max
- Detect seasonal patterns
- Create/update BaselineModel

#### 2. _detect_seasonal_patterns(history) (lines 119-134)
**Purpose**: Detect hourly patterns in metric data
**Logic**:
- Requires 24+ samples
- Groups values by hour (0-23)
- Calculates mean for each hour with 3+ samples
- Returns dict like {"hour_13": 75.5, "hour_9": 65.2}

#### 3. _detect_anomaly(point) (lines 136-177) ⭐ CORE
**Purpose**: Detect if point is anomalous
**Logic**:
- Get baseline for metric_type
- Calculate bounds: mean ± (sensitivity * std_dev)
- Apply seasonal adjustment if available
- Check if value outside bounds
- If anomalous:
  - Calculate severity (low/medium/high/critical)
  - Calculate confidence (0.0-1.0)
  - Generate description
  - Return AnomalyDetection
- Return None if not anomalous

#### 4. _get_seasonal_adjustment(point, baseline) (lines 179-190)
**Purpose**: Get seasonal adjustment for this point
**Logic**:
- Gets hour pattern from baseline.seasonal_patterns
- Returns pattern - mean (e.g., hour_13 pattern is 75.5, baseline mean is 70.0, adjustment = 5.5)
- Returns 0.0 if no pattern

#### 5. _calculate_severity(point, baseline, lower, upper) (lines 192-206)
**Purpose**: Calculate severity level
**Logic**:
- If std_dev == 0: return "medium"
- If critical threshold reached: return "critical"
- Otherwise: calculate z-score and map to severity

#### 6. _is_critical_threshold_breached(point) (lines 208-223)
**Purpose**: Check if metric type has critical threshold
**Logic**:
- Get config from self.metric_configs
- Check critical_threshold
- Check direction (up/down/both)
- Call _threshold_breached_in_direction()

#### 7. _threshold_breached_in_direction(value, threshold, direction) (lines 225-237)
**Purpose**: Check if threshold breached in specific direction
**Logic**:
- direction="up": value > threshold
- direction="down": value < threshold
- direction="both": value > threshold or value < -threshold

#### 8. _calculate_z_score(point, baseline, lower, upper) (lines 239-247)
**Purpose**: Calculate z-score (how many std_devs from bound)
**Formula**: min(abs(value - lower), abs(value - upper)) / std_dev

#### 9. _severity_from_z_score(z_score) (lines 249-256)
**Purpose**: Map z-score to severity
**Logic**:
- z_score > 4: "critical"
- z_score > 3: "high"
- z_score > 2: "medium"
- else: "low"

#### 10. _calculate_confidence(point, baseline) (lines 258-271)
**Purpose**: Calculate confidence in anomaly detection (0.0-1.0)
**Formula**: sample_factor * std_factor
- sample_factor = min(sample_count / 50, 1.0)
- std_factor = 0.5 if std_dev == 0 else max(0.1, 1.0 - cv)
- cv (coefficient of variation) = std_dev / abs(mean)

#### 11. _generate_anomaly_description(...) (lines 273-288)
**Purpose**: Generate human-readable description
**Format**: "{Severity} anomaly in {metric_type}: value {value} is {direction} expected range {range} (baseline: {mean})"

---

## Testing Strategy

### Test Groups (estimated 35-40 tests)

#### Group 1: Dataclasses (5 tests)
- ✅ MetricPoint creation with all fields
- ✅ AnomalyDetection creation with all fields
- ✅ BaselineModel creation with all fields
- ✅ BaselineModel with empty seasonal_patterns
- ✅ BaselineModel with seasonal_patterns

#### Group 2: Constructor (3 tests)
- ✅ Default parameters
- ✅ Custom parameters
- ✅ Initialization of data structures

#### Group 3: add_metric() (6 tests) ⭐ CRITICAL
- ✅ Basic metric addition
- ✅ Timestamp default (datetime.now())
- ✅ Metadata default (empty dict)
- ✅ Triggers baseline update when >= min_samples
- ✅ Triggers anomaly detection when >= min_samples
- ✅ Handles different metric types

#### Group 4: Baseline Update (4 tests)
- ✅ _update_baseline creates BaselineModel
- ✅ Correct mean, std_dev, min, max calculated
- ✅ Sample count correct
- ✅ Last updated timestamp set

#### Group 5: Seasonal Patterns (3 tests)
- ✅ Returns empty dict with < 24 samples
- ✅ Detects hourly patterns with 24+ samples
- ✅ Calculates hourly means correctly

#### Group 6: Anomaly Detection (8 tests) ⭐ CRITICAL
- ✅ No anomaly when within bounds
- ✅ Detects anomaly above upper bound
- ✅ Detects anomaly below lower bound
- ✅ Returns None when no baseline exists
- ✅ Creates AnomalyDetection with correct fields
- ✅ Logs anomaly detection (check logger.info call)
- ✅ Seasonal adjustment applied
- ✅ Sensitivity parameter affects bounds

#### Group 7: Seasonal Adjustment (3 tests)
- ✅ Returns 0.0 when no seasonal pattern
- ✅ Returns pattern - mean when pattern exists
- ✅ Gets correct hour from timestamp

#### Group 8: Severity Calculation (5 tests)
- ✅ Returns "medium" when std_dev == 0
- ✅ Returns "critical" when critical threshold reached
- ✅ Returns "critical" for z-score > 4
- ✅ Returns "high" for z-score > 3
- ✅ Returns "medium" for z-score > 2
- ✅ Returns "low" otherwise

#### Group 9: Critical Threshold (4 tests)
- ✅ Returns False when no config for metric_type
- ✅ Checks "up" direction correctly
- ✅ Checks "down" direction correctly
- ✅ Checks "both" direction correctly

#### Group 10: Z-Score Calculation (2 tests)
- ✅ Calculates deviation from bounds
- ✅ Divides by std_dev

#### Group 11: Confidence Calculation (3 tests)
- ✅ Sample factor caps at 1.0 (50+ samples)
- ✅ std_factor = 0.5 when std_dev == 0
- ✅ std_factor based on coefficient of variation

#### Group 12: get_anomalies() (6 tests)
- ✅ Returns all anomalies when no filters
- ✅ Filters by metric_type
- ✅ Filters by severity
- ✅ Filters by since timestamp
- ✅ Respects limit parameter
- ✅ Sorts by timestamp descending

#### Group 13: get_baseline_summary() (2 tests)
- ✅ Returns empty dict when no baselines
- ✅ Returns summary with all fields

#### Group 14: export_model() (3 tests)
- ✅ Exports baselines to JSON
- ✅ Exports config (baseline_window, sensitivity, min_samples)
- ✅ Includes exported_at timestamp

#### Group 15: Integration (3 tests)
- ✅ Full workflow: add metrics → detect anomalies → get_anomalies
- ✅ Multiple metric types tracked separately
- ✅ Anomalies list accumulates

---

## Key Testing Points

### MUST Test:
1. ✅ add_metric() main API - all branches
2. ✅ _detect_anomaly() - all 4 severity paths
3. ✅ Seasonal pattern detection (hourly grouping)
4. ✅ Baseline calculation (mean, std_dev, bounds)
5. ✅ get_anomalies() filtering logic
6. ✅ Confidence calculation formula

### MOCK:
1. ✅ datetime.now() for consistent timestamps
2. ✅ Logger output verification (check info call)

### SKIP (intentionally):
1. ❌ Exact floating point calculations (use approximate assertions)
2. ❌ Statistical edge cases (very small std_dev, etc.)

---

## Estimated Coverage

**Target**: 60-65% of 163 statements = 98-106 statements

**Achievable via**:
- 35-40 test methods
- Testing all public API methods
- Testing core detection logic
- Testing seasonal patterns
- Testing severity calculation

**Uncovered** (~35-40%):
- Some statistical edge cases
- Complex floating point scenarios
- Some error handling paths (if any exist)
- Integration with real-time systems
