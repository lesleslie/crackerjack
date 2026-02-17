______________________________________________________________________

title: Data Validation
owner: Developer Enablement Guild
last_reviewed: 2025-02-06
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6EEXC6CHWGA6M371A5K27RY
  category: development/data

______________________________________________________________________

## Data Validation Pipeline

Create a comprehensive data validation system for: $ARGUMENTS

Implement validation including:

1. **Schema Validation**:

   - Pydantic models for structure
   - JSON Schema generation
   - Type checking and coercion
   - Nested object validation
   - Custom validators

1. **Data Quality Checks**:

   - Null/missing value handling
   - Outlier detection
   - Statistical validation
   - Business rule enforcement
   - Referential integrity

1. **Data Profiling**:

   - Automatic type inference
   - Distribution analysis
   - Cardinality checks
   - Pattern detection
   - Anomaly identification

1. **Validation Rules**:

   - Field-level constraints
   - Cross-field validation
   - Temporal consistency
   - Format validation (email, phone, etc.)
   - Custom business logic

1. **Error Handling**:

   - Detailed error messages
   - Error categorization
   - Partial validation support
   - Error recovery strategies
   - Validation reports

1. **Performance**:

   - Streaming validation
   - Batch processing
   - Parallel validation
   - Caching strategies
   - Incremental validation

1. **Integration**:

   - API endpoint validation
   - Database constraints
   - Message queue validation
   - File upload validation
   - Real-time validation

Include data quality metrics, monitoring dashboards, and alerting. Make it extensible for custom validation rules.

______________________________________________________________________

## Implementation Patterns

### 1. Pydantic Schema Validation

```python
from pydantic import BaseModel, EmailStr, validator, root_validator, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class Address(BaseModel):
    """Nested address validation"""

    street: str = Field(..., min_length=1, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., regex=r"^[A-Z]{2}$")
    zip_code: str = Field(..., regex=r"^\d{5}(-\d{4})?$")

    class Config:
        extra = "forbid"  # Reject unknown fields


class UserData(BaseModel):
    """User data validation with custom rules"""

    id: int = Field(..., gt=0)
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, regex=r"^[a-zA-Z0-9_-]+$")
    age: int = Field(..., ge=0, le=120)
    role: UserRole
    created_at: datetime
    address: Optional[Address] = None
    tags: List[str] = Field(default_factory=list, max_items=10)

    @validator("username")
    def username_no_profanity(cls, v):
        """Custom validator for username"""
        prohibited = ["admin", "root", "system"]
        if v.lower() in prohibited:
            raise ValueError(f"Username '{v}' is not allowed")
        return v

    @validator("created_at")
    def created_at_not_future(cls, v):
        """Ensure created_at is not in the future"""
        if v > datetime.utcnow():
            raise ValueError("created_at cannot be in the future")
        return v

    @root_validator
    def check_role_age_consistency(cls, values):
        """Cross-field validation"""
        age = values.get("age")
        role = values.get("role")

        if age and role:
            if role == UserRole.ADMIN and age < 18:
                raise ValueError("Admin users must be 18 or older")

        return values

    class Config:
        extra = "forbid"
        json_encoders = {datetime: lambda v: v.isoformat()}


# Usage
def validate_user_data(data: dict) -> UserData:
    """Validate user data with detailed error reporting"""
    try:
        validated = UserData(**data)
        return validated
    except ValueError as e:
        # Handle validation errors
        errors = e.errors() if hasattr(e, "errors") else [{"msg": str(e)}]
        for error in errors:
            field = ".".join(str(loc) for loc in error.get("loc", []))
            print(f"Validation failed for '{field}': {error['msg']}")
        raise


# Batch validation
def validate_batch(records: List[dict]) -> tuple[List[UserData], List[dict]]:
    """Validate batch with error collection"""
    valid_records = []
    failed_records = []

    for idx, record in enumerate(records):
        try:
            validated = UserData(**record)
            valid_records.append(validated)
        except ValueError as e:
            failed_records.append(
                {
                    "index": idx,
                    "record": record,
                    "errors": e.errors() if hasattr(e, "errors") else [str(e)],
                }
            )

    return valid_records, failed_records
```

### 2. Great Expectations Integration

```python
import great_expectations as ge
from great_expectations.core import ExpectationSuite, ExpectationConfiguration
from great_expectations.data_context import DataContext
import pandas as pd


class DataQualityValidator:
    """Production-ready data quality validation"""

    def __init__(self, context_root_dir: str = "./great_expectations"):
        self.context = DataContext(context_root_dir)

    def create_user_expectation_suite(self) -> ExpectationSuite:
        """Create comprehensive expectation suite for user data"""
        suite = self.context.create_expectation_suite(
            expectation_suite_name="user_data_suite", overwrite_existing=True
        )

        # Column existence
        suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_table_columns_to_match_ordered_list",
                kwargs={
                    "column_list": [
                        "id",
                        "email",
                        "username",
                        "age",
                        "role",
                        "created_at",
                    ]
                },
            )
        )

        # ID validation
        suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_be_unique",
                kwargs={"column": "id"},
            )
        )

        suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_be_of_type",
                kwargs={"column": "id", "type_": "int"},
            )
        )

        # Email validation
        suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_match_regex",
                kwargs={
                    "column": "email",
                    "regex": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                },
            )
        )

        suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_be_unique",
                kwargs={"column": "email"},
            )
        )

        # Age validation
        suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_be_between",
                kwargs={"column": "age", "min_value": 0, "max_value": 120},
            )
        )

        # Null checks
        suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_not_be_null",
                kwargs={"column": "id"},
            )
        )

        # Statistical validation
        suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_mean_to_be_between",
                kwargs={"column": "age", "min_value": 18, "max_value": 65},
            )
        )

        return suite

    def validate_dataframe(self, df: pd.DataFrame, suite_name: str) -> dict:
        """Validate dataframe against expectation suite"""
        batch = self.context.get_batch(
            batch_kwargs={"dataset": df, "datasource": "pandas_datasource"},
            expectation_suite_name=suite_name,
        )

        results = batch.validate()

        # Process results
        validation_summary = {
            "success": results.success,
            "evaluated_expectations": results.statistics["evaluated_expectations"],
            "successful_expectations": results.statistics["successful_expectations"],
            "unsuccessful_expectations": results.statistics[
                "unsuccessful_expectations"
            ],
            "success_percent": results.statistics["success_percent"],
            "failures": [],
        }

        # Extract failure details
        for result in results.results:
            if not result.success:
                validation_summary["failures"].append(
                    {
                        "expectation_type": result.expectation_config.expectation_type,
                        "column": result.expectation_config.kwargs.get("column"),
                        "result": result.result,
                    }
                )

        return validation_summary


# Usage
def validate_with_ge(df: pd.DataFrame):
    """Validate data with Great Expectations"""
    validator = DataQualityValidator()

    # Create expectations
    suite = validator.create_user_expectation_suite()

    # Validate
    results = validator.validate_dataframe(df, "user_data_suite")

    if not results["success"]:
        print(f"Validation failed: {results['success_percent']:.1f}% passed")
        for failure in results["failures"]:
            print(f"  - {failure['expectation_type']} on {failure['column']}")

    return results
```

### 3. Streaming Validation with Error Recovery

```python
from typing import Iterator, Tuple, Any
import json
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class ValidationMetrics:
    """Track validation metrics"""

    total: int = 0
    valid: int = 0
    invalid: int = 0
    errors_by_type: dict = field(default_factory=lambda: defaultdict(int))

    @property
    def success_rate(self) -> float:
        return (self.valid / self.total * 100) if self.total > 0 else 0.0


class StreamingValidator:
    """Validate records in stream with error handling"""

    def __init__(self, schema_class: type[BaseModel], error_threshold: float = 0.1):
        self.schema_class = schema_class
        self.error_threshold = error_threshold  # Stop if >10% errors
        self.metrics = ValidationMetrics()
        self.error_buffer = []

    def validate_stream(
        self, records: Iterator[dict]
    ) -> Iterator[Tuple[Any, Optional[dict]]]:
        """Validate stream of records"""
        for record in records:
            self.metrics.total += 1

            try:
                # Validate record
                validated = self.schema_class(**record)
                self.metrics.valid += 1
                yield validated, None

            except ValueError as e:
                self.metrics.invalid += 1

                # Collect error details
                error_info = {
                    "record": record,
                    "errors": e.errors() if hasattr(e, "errors") else [str(e)],
                    "index": self.metrics.total - 1,
                }

                # Track error types
                for error in (
                    e.errors() if hasattr(e, "errors") else [{"type": "unknown"}]
                ):
                    error_type = error.get("type", "unknown")
                    self.metrics.errors_by_type[error_type] += 1

                self.error_buffer.append(error_info)
                yield None, error_info

                # Check error threshold
                error_rate = self.metrics.invalid / self.metrics.total
                if error_rate > self.error_threshold:
                    raise ValidationError(
                        f"Error rate {error_rate:.1%} exceeds threshold {self.error_threshold:.1%}"
                    )

    def get_report(self) -> dict:
        """Generate validation report"""
        return {
            "total_records": self.metrics.total,
            "valid_records": self.metrics.valid,
            "invalid_records": self.metrics.invalid,
            "success_rate": f"{self.metrics.success_rate:.2f}%",
            "errors_by_type": dict(self.metrics.errors_by_type),
            "sample_errors": self.error_buffer[:10],  # First 10 errors
        }


# Usage
def process_data_stream(input_file: str, output_file: str, error_file: str):
    """Process and validate streaming data"""
    validator = StreamingValidator(UserData, error_threshold=0.1)

    with (
        open(input_file) as f_in,
        open(output_file, "w") as f_out,
        open(error_file, "w") as f_err,
    ):
        # Stream records
        records = (json.loads(line) for line in f_in)

        # Validate and write
        for validated, error in validator.validate_stream(records):
            if validated:
                f_out.write(json.dumps(validated.dict()) + "\n")
            if error:
                f_err.write(json.dumps(error) + "\n")

    # Print report
    report = validator.get_report()
    print(f"Validation complete: {report['success_rate']} success rate")
    print(f"Errors by type: {report['errors_by_type']}")
```

### 4. Data Profiling and Anomaly Detection

```python
import pandas as pd
from scipy import stats
import numpy as np


class DataProfiler:
    """Automated data profiling and anomaly detection"""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.profile = {}

    def generate_profile(self) -> dict:
        """Generate comprehensive data profile"""
        for column in self.df.columns:
            col_profile = {
                "dtype": str(self.df[column].dtype),
                "null_count": int(self.df[column].isnull().sum()),
                "null_percentage": float(
                    self.df[column].isnull().sum() / len(self.df) * 100
                ),
                "unique_count": int(self.df[column].nunique()),
                "cardinality": float(self.df[column].nunique() / len(self.df) * 100),
            }

            # Numeric columns
            if pd.api.types.is_numeric_dtype(self.df[column]):
                col_profile.update(
                    {
                        "mean": float(self.df[column].mean()),
                        "median": float(self.df[column].median()),
                        "std": float(self.df[column].std()),
                        "min": float(self.df[column].min()),
                        "max": float(self.df[column].max()),
                        "q25": float(self.df[column].quantile(0.25)),
                        "q75": float(self.df[column].quantile(0.75)),
                        "outliers": self.detect_outliers(column),
                    }
                )

            # String columns
            elif pd.api.types.is_string_dtype(self.df[column]):
                col_profile.update(
                    {
                        "avg_length": float(self.df[column].str.len().mean()),
                        "max_length": int(self.df[column].str.len().max()),
                        "top_values": self.df[column].value_counts().head(5).to_dict(),
                    }
                )

            # Datetime columns
            elif pd.api.types.is_datetime64_any_dtype(self.df[column]):
                col_profile.update(
                    {
                        "min_date": str(self.df[column].min()),
                        "max_date": str(self.df[column].max()),
                        "date_range_days": (
                            self.df[column].max() - self.df[column].min()
                        ).days,
                    }
                )

            self.profile[column] = col_profile

        return self.profile

    def detect_outliers(self, column: str, method: str = "iqr") -> dict:
        """Detect outliers using IQR or Z-score"""
        data = self.df[column].dropna()

        if method == "iqr":
            Q1 = data.quantile(0.25)
            Q3 = data.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            outliers = data[(data < lower_bound) | (data > upper_bound)]

        elif method == "zscore":
            z_scores = np.abs(stats.zscore(data))
            outliers = data[z_scores > 3]

        return {
            "count": len(outliers),
            "percentage": len(outliers) / len(data) * 100,
            "values": outliers.tolist()[:10],  # Sample
        }

    def validate_against_baseline(self, baseline_profile: dict) -> List[dict]:
        """Compare current data against baseline profile"""
        issues = []

        for column, baseline in baseline_profile.items():
            if column not in self.profile:
                issues.append(
                    {
                        "column": column,
                        "issue": "missing_column",
                        "severity": "critical",
                    }
                )
                continue

            current = self.profile[column]

            # Check dtype consistency
            if current["dtype"] != baseline["dtype"]:
                issues.append(
                    {
                        "column": column,
                        "issue": "dtype_mismatch",
                        "expected": baseline["dtype"],
                        "actual": current["dtype"],
                        "severity": "critical",
                    }
                )

            # Check null percentage drift
            null_drift = abs(current["null_percentage"] - baseline["null_percentage"])
            if null_drift > 10:  # >10% drift
                issues.append(
                    {
                        "column": column,
                        "issue": "null_percentage_drift",
                        "baseline": baseline["null_percentage"],
                        "current": current["null_percentage"],
                        "severity": "warning",
                    }
                )

            # Check cardinality drift (for categorical)
            if "cardinality" in baseline:
                card_drift = abs(current["cardinality"] - baseline["cardinality"])
                if card_drift > 20:
                    issues.append(
                        {
                            "column": column,
                            "issue": "cardinality_drift",
                            "baseline": baseline["cardinality"],
                            "current": current["cardinality"],
                            "severity": "warning",
                        }
                    )

        return issues
```

______________________________________________________________________

## Validation Strategies

### 1. Multi-Layer Validation

```python
class MultiLayerValidator:
    """Implement defense-in-depth validation"""

    def __init__(self):
        self.layers = []

    def add_layer(self, name: str, validator_func: callable):
        """Add validation layer"""
        self.layers.append((name, validator_func))

    def validate(self, data: Any) -> Tuple[bool, List[dict]]:
        """Run all validation layers"""
        errors = []

        for layer_name, validator in self.layers:
            try:
                validator(data)
            except Exception as e:
                errors.append(
                    {
                        "layer": layer_name,
                        "error": str(e),
                        "data_sample": str(data)[:100],
                    }
                )

        return len(errors) == 0, errors


# Usage
validator = MultiLayerValidator()
validator.add_layer("schema", lambda d: UserData(**d))
validator.add_layer("business_rules", lambda d: check_business_rules(d))
validator.add_layer("data_quality", lambda d: check_data_quality(d))

success, errors = validator.validate(user_data)
```

### 2. Progressive Validation

```python
def progressive_validation(df: pd.DataFrame, sample_size: int = 1000):
    """Validate sample first, then full dataset"""

    # Quick validation on sample
    sample = df.sample(min(sample_size, len(df)))
    validator = DataQualityValidator()

    sample_results = validator.validate_dataframe(sample, "user_data_suite")

    if sample_results["success_percent"] < 90:
        return {
            "status": "failed_sample",
            "message": f"Sample validation only {sample_results['success_percent']:.1f}% successful",
            "failures": sample_results["failures"],
        }

    # Full validation if sample passes
    full_results = validator.validate_dataframe(df, "user_data_suite")

    return {
        "status": "complete",
        "sample_success": sample_results["success_percent"],
        "full_success": full_results["success_percent"],
        "failures": full_results["failures"],
    }
```

______________________________________________________________________

## Related Agents

**Primary Orchestrators**:

- `data-engineer` - Data pipeline validation integration
- `python-pro` - Advanced validation patterns and optimization

**Supporting Specialists**:

- `postgresql-specialist` - Database constraint validation
- `architecture-council` - API validation strategies

**Quality Assurance**:

- `qa-strategist` - Validation testing
- `security-auditor` - Input sanitization validation

______________________________________________________________________

## Best Practices

1. **Fail Fast**: Validate at ingestion, not at consumption
1. **Detailed Errors**: Provide actionable error messages with field names
1. **Partial Validation**: Support validating subsets for performance
1. **Error Recovery**: Implement dead letter queues for failed records
1. **Schema Evolution**: Version schemas and handle backward compatibility
1. **Sampling**: Validate samples for large datasets before full validation
1. **Monitoring**: Track validation metrics (success rate, error types, performance)
1. **Custom Validators**: Create reusable validators for common business rules
1. **Type Coercion**: Handle automatic type conversion with caution
1. **Documentation**: Document validation rules and expected formats

______________________________________________________________________

## Security Considerations

### Data Access Control

- **Principle of Least Privilege**: Grant minimal necessary permissions
- **Row-Level Security**: Implement tenant isolation in multi-tenant systems
- **Audit Logging**: Track all data access and modifications

```python
# Example: Row-level security in PostgreSQL
CREATE POLICY tenant_isolation ON orders
    USING (tenant_id = current_setting('app.current_tenant')::int);

ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
```

### Data Encryption

- **Encryption at Rest**: Enable database encryption (TDE)
- **Encryption in Transit**: Enforce TLS for all connections
- **Column-Level Encryption**: Encrypt sensitive fields (SSN, credit cards)

```python
# Example: Column-level encryption
from cryptography.fernet import Fernet


class EncryptedField:
    def __init__(self, key: bytes):
        self.cipher = Fernet(key)

    def encrypt(self, value: str) -> bytes:
        return self.cipher.encrypt(value.encode())

    def decrypt(self, encrypted: bytes) -> str:
        return self.cipher.decrypt(encrypted).decode()


# Usage in models
ssn_cipher = EncryptedField(ENCRYPTION_KEY)
encrypted_ssn = ssn_cipher.encrypt(user.ssn)
```

### SQL Injection Prevention

- **Parameterized Queries**: Never concatenate user input into SQL
- **ORM Usage**: Use SQLAlchemy, Django ORM, Sequelize properly
- **Input Validation**: Validate and sanitize all user inputs

```python
# ❌ VULNERABLE - SQL Injection
query = f"SELECT * FROM users WHERE email = '{user_input}'"

# ✅ SAFE - Parameterized query
query = "SELECT * FROM users WHERE email = %s"
cursor.execute(query, (user_input,))
```

### Data Retention & Privacy

- **Data Retention Policies**: Define and enforce retention periods
- **Right to Deletion**: Implement GDPR/CCPA deletion capabilities
- **Data Anonymization**: Anonymize data for analytics/testing

### Backup Security

- **Encrypted Backups**: Encrypt all backup files
- **Secure Storage**: Store backups in separate, access-controlled locations
- **Backup Access Auditing**: Log all backup access and restorations

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
