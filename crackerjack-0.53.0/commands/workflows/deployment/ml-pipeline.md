______________________________________________________________________

title: ML Pipeline Release Workflow
owner: ML Systems Guild
last_reviewed: 2025-02-06
related_tools:

- commands/tools/development/code-quality/dependency-lifecycle.md
- commands/tools/development/testing/quality-validation.md
- commands/tools/workflow/privacy-impact-assessment.md
- commands/tools/monitoring/observability-lifecycle.md
  risk: high
  status: active
  id: 01K6EF8EHTYXG10569SZTK2EZ1

______________________________________________________________________

## ML Pipeline Release Workflow

[Extended thinking: Ensure machine learning pipelines move from experimentation to production safely and compliantly.]

## Overview

Apply this workflow to promote ML pipelines, covering data readiness, model quality, deployment, and monitoring.

## Prerequisites

- Documented business objective and evaluation metrics.
- Labeled datasets and data retention policies.
- Access to training, staging, and production infrastructure.

## Inputs

- `$ARGUMENTS` — pipeline name and objective.
- `$MODEL_STAGE` — `prototype`, `staging`, or `production`.
- `$COMPLIANCE_FLAGS` — privacy or regulatory constraints.

## Outputs

- Approved deployment plan and model card.
- Automated retraining and validation jobs.
- Monitoring dashboards for drift, performance, and fairness.

## Phases

### Phase 0 – Prerequisites Validation

**Before starting ML pipeline deployment, validate all required infrastructure and data access:**

1. **Model Registry Access:**

   ```python
   # MLflow
   import mlflow

   mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
   client = mlflow.tracking.MlflowClient()
   experiments = client.list_experiments()
   print(f"✓ MLflow accessible: {len(experiments)} experiments found")

   # SageMaker
   import boto3

   sagemaker = boto3.client("sagemaker")
   response = sagemaker.list_models(MaxResults=5)
   print(f"✓ SageMaker accessible: {len(response['Models'])} models found")
   ```

1. **Data Access Validation:**

   ```python
   # Verify training data access
   import pandas as pd
   from datetime import datetime, timedelta

   # Check data warehouse connection
   training_data = pd.read_sql(
       "SELECT COUNT(*) as count FROM training_dataset WHERE created_at > %s",
       con=db_connection,
       params=[datetime.now() - timedelta(days=30)],
   )
   assert training_data["count"][0] > 1000, "Insufficient training data"

   # Verify feature store access (if applicable)
   from feast import FeatureStore

   store = FeatureStore(repo_path=".")
   features = store.get_online_features(
       features=["user_features:age", "user_features:country"],
       entity_rows=[{"user_id": "test_user"}],
   )
   print("✓ Feature store accessible")
   ```

1. **Compute Infrastructure:**

   ```bash
   # Training infrastructure
   # For Kubernetes
   kubectl get namespace ml-training || kubectl create namespace ml-training
   kubectl get resourcequota -n ml-training

   # Check GPU availability if required
   kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'

   # For SageMaker
   aws sagemaker describe-training-job --training-job-name latest-training-job || echo "No previous jobs"

   # For Vertex AI
   gcloud ai custom-jobs list --region=us-central1
   ```

1. **Model Serving Infrastructure:**

   ```bash
   # Kubernetes model serving
   kubectl get namespace ml-serving || kubectl create namespace ml-serving

   # Check model serving framework (Seldon, KServe, TorchServe)
   kubectl get svc -n ml-serving

   # SageMaker endpoints
   aws sagemaker list-endpoints --max-results 10

   # Verify inference scaling limits
   kubectl describe hpa -n ml-serving || echo "No HPA configured"
   ```

1. **Experiment Tracking & Monitoring:**

   ```python
   # Verify experiment tracking
   import mlflow
   experiment = mlflow.get_experiment_by_name($EXPERIMENT_NAME)
   if experiment is None:
       experiment_id = mlflow.create_experiment($EXPERIMENT_NAME)
       print(f"✓ Created experiment: {experiment_id}")
   else:
       print(f"✓ Experiment exists: {experiment.experiment_id}")

   # Check monitoring stack
   import requests
   prometheus_health = requests.get('http://prometheus:9090/-/healthy')
   assert prometheus_health.status_code == 200, "Prometheus not accessible"
   ```

1. **Data Privacy & Compliance:**

   ```bash
   # Verify data retention policies configured
   [ -f "data_retention_policy.yaml" ] || echo "ERROR: No data retention policy"

   # Check PII detection/anonymization tooling
   python -c "import presidio_analyzer; print('✓ PII detection available')" || \
     echo "WARNING: No PII detection configured"

   # Validate data lineage tracking
   [ -f "dbt_project.yml" ] && echo "✓ DBT lineage configured" || \
     echo "WARNING: No data lineage tracking"
   ```

1. **Model Artifacts & Dependencies:**

   ```python
   # Verify model artifact storage
   import boto3
   s3 = boto3.client('s3')
   response = s3.list_objects_v2(Bucket=$MODEL_ARTIFACTS_BUCKET, MaxKeys=1)
   print(f"✓ Model artifacts bucket accessible: {$MODEL_ARTIFACTS_BUCKET}")

   # Check dependency versions
   import sys
   import importlib.metadata as metadata

   required_packages = [
       ('numpy', '>=1.21.0'),
       ('pandas', '>=1.3.0'),
       ('scikit-learn', '>=1.0.0'),
       ('tensorflow', '>=2.8.0') if 'tensorflow' in sys.modules else None,
       ('torch', '>=1.10.0') if 'torch' in sys.modules else None,
   ]

   for pkg, version in [p for p in required_packages if p]:
       installed = metadata.version(pkg[0])
       print(f"✓ {pkg[0]}: {installed}")
   ```

1. **Evaluation & Testing Infrastructure:**

   ```python
   # Verify test datasets exist
   import os

   required_datasets = [
       "data/test/holdout_set.parquet",
       "data/test/validation_set.parquet",
       "data/test/adversarial_examples.parquet",
   ]

   for dataset in required_datasets:
       assert os.path.exists(dataset), f"Missing: {dataset}"
       print(f"✓ Found: {dataset}")

   # Check A/B testing framework
   try:
       import optimizely

       print("✓ A/B testing framework available")
   except ImportError:
       print("WARNING: No A/B testing framework detected")
   ```

1. **Model Security & Scanning:**

   ```bash
   # Check model scanning for vulnerabilities
   pip install safety
   safety check --json || echo "WARNING: Vulnerable dependencies detected"

   # Verify model signing/verification (if applicable)
   [ -f ".signify/model_signing_key.pub" ] && echo "✓ Model signing configured" || \
     echo "INFO: No model signing configured"
   ```

1. **Rollback Capability:**

   ```python
   # Verify previous model version exists and is accessible
   client = mlflow.tracking.MlflowClient()
   production_models = client.get_latest_versions(
       name=$MODEL_NAME,
       stages=["Production"]
   )

   if len(production_models) > 0:
       print(f"✓ Rollback target available: v{production_models[0].version}")
   else:
       print("WARNING: No previous production model for rollback")
   ```

**Validation Checklist:**

- [ ] Model registry accessible and credentials valid
- [ ] Training data available with sufficient volume
- [ ] Feature store accessible (if applicable)
- [ ] Training compute infrastructure ready (CPUs/GPUs)
- [ ] Model serving infrastructure deployed
- [ ] Experiment tracking configured
- [ ] Monitoring stack (Prometheus/Grafana) accessible
- [ ] Data retention and privacy policies documented
- [ ] PII detection/anonymization tooling available
- [ ] Model artifact storage accessible
- [ ] Required ML library versions installed
- [ ] Test/validation datasets exist
- [ ] A/B testing framework configured (if applicable)
- [ ] Dependency security scans passing
- [ ] Previous model version available for rollback
- [ ] On-call ML engineer and data scientist identified

**If any validation fails:**

1. Document the missing prerequisite with severity (critical/warning)
1. Create task to resolve (assign to ML platform team or data team)
1. **Critical items must be resolved before Phase 1**
1. Warnings can be addressed in parallel with early phases

**Stage-Specific Requirements:**

| Stage | Additional Validations |
|-------|----------------------|
| **Prototype** | Jupyter environment, development data access |
| **Staging** | Shadow deployment infrastructure, staging feature store |
| **Production** | Canary deployment config, production monitoring, incident runbooks |

### Phase 1 – Data & Feature Validation

- `data-engineer` verifies data pipelines, schema validation, and lineage.
- `privacy-officer` reviews data handling using `commands/tools/workflow/privacy-impact-assessment.md` when personal data is involved.

### Phase 2 – Model Quality & Testing

- `mlops-engineer` coordinates training pipelines, versioning, and reproducibility.
- `qa-strategist` defines acceptance tests (offline metrics, shadow traffic, canary suites) using `commands/tools/development/testing/quality-validation.md`.

### Phase 3 – Deployment & Operations

- `developer-enablement-lead` automates deployment and rollback paths referencing `commands/tools/development/code-quality/dependency-lifecycle.md`.
- `observability-incident-lead` instruments drift detection, alerting, and feedback loops.

### Phase 4 – Governance & Communication

- `product-manager` documents expected business impact and success thresholds.
- `customer-success-lead` prepares stakeholder updates and support readiness.

## ML Model Rollback Procedures

### When to Rollback

Initiate model rollback immediately if any of the following conditions occur:

- **Model Performance Degradation:**

  - Primary metric drops > 5% below baseline
  - Secondary metrics degrade significantly
  - Offline evaluation fails acceptance criteria
  - Model predictions show unexplained variance

- **Data Quality Issues:**

  - Feature distribution drift detected (PSI > 0.2)
  - Missing feature values > 5%
  - Data schema violations in production
  - Upstream data pipeline failures

- **Business Impact:**

  - Revenue metrics degrade (conversion, AOV, CTR)
  - Customer complaints or escalations
  - Increased support tickets related to predictions
  - Regulatory compliance violations

- **Technical Failures:**

  - Model serving latency > SLA (p95 > threshold)
  - Prediction failure rate > 1%
  - Memory/CPU resource exhaustion
  - Model inference errors or exceptions

### Rollback Decision Matrix

| Deployment Stage | Rollback Type | Estimated Time | Risk Level |
|-----------------|---------------|----------------|------------|
| Shadow mode (0% traffic) | Immediate disable | < 1 minute | Very Low |
| Canary (< 10% traffic) | Automatic rollback | 2-5 minutes | Low |
| A/B test (50% traffic) | Coordinated rollback | 5-15 minutes | Medium |
| Full production (100%) | Emergency rollback | 15-30 minutes | High |
| Post-retraining | Model version revert | 30-60 minutes | Very High |

### Rollback Steps by Deployment Pattern

#### 1. Model Version Pinning Rollback

**For Model Registries (MLflow, SageMaker, Vertex AI):**

```python
# MLflow Example
import mlflow

client = mlflow.tracking.MlflowClient()

# Get previous production model version
previous_versions = client.search_model_versions(
    f"name='{model_name}' AND tags.environment='production'"
)
previous_version = previous_versions[1]  # Second-to-last production version

# Transition current model to archived
client.transition_model_version_stage(
    name=model_name,
    version=current_version,
    stage="Archived",
    archive_existing_versions=False,
)

# Promote previous version back to production
client.transition_model_version_stage(
    name=model_name,
    version=previous_version.version,
    stage="Production",
    archive_existing_versions=True,
)
```

**For SageMaker:**

```python
import boto3

sagemaker = boto3.client("sagemaker")

# Update endpoint to use previous model
sagemaker.update_endpoint(
    EndpointName="my-model-endpoint",
    EndpointConfigName="my-model-config-v1",  # Previous stable version
)

# Monitor rollback
waiter = sagemaker.get_waiter("endpoint_in_service")
waiter.wait(EndpointName="my-model-endpoint")
```

#### 2. Traffic Shifting Rollback

**Gradual traffic reduction to new model:**

```python
# SageMaker variant weights
sagemaker.update_endpoint_weights_and_capacities(
    EndpointName="my-model-endpoint",
    DesiredWeightsAndCapacities=[
        {
            "VariantName": "new-model-variant",
            "DesiredWeight": 0.0,  # Reduce to 0%
        },
        {
            "VariantName": "old-model-variant",
            "DesiredWeight": 1.0,  # Increase to 100%
        },
    ],
)
```

**Feature flag-based rollback:**

```python
# Immediate disable via feature flag
import requests

response = requests.patch(
    "https://feature-flags-api/flags/ml-model-v2-enabled",
    headers={"Authorization": f"Bearer {token}"},
    json={"enabled": False, "rollout_percentage": 0},
)
```

#### 3. A/B Test Termination

**End experiment and revert to control:**

```python
# Optimizely example
from optimizely import optimizely

optimizely_client = optimizely.Optimizely(datafile=datafile)

# Pause experiment
experiment_key = "ml_model_v2_test"
# Update via Optimizely dashboard or API to force all traffic to control variant

# Or use feature flag to override
optimizely_client.set_forced_variation(
    experiment_key=experiment_key,
    user_id="*",  # All users
    variation_key="control",  # Original model
)
```

#### 4. Container/Kubernetes Model Rollback

**For containerized model serving:**

```bash
# Kubernetes deployment rollback
kubectl rollout undo deployment/ml-model-serving -n ml-prod

# Or scale new deployment to zero
kubectl scale deployment ml-model-serving-v2 --replicas=0 -n ml-prod

# Verify old version is serving
kubectl get pods -n ml-prod -l app=ml-model-serving,version=v1
```

### Data Pipeline Rollback

**If model rollback requires reverting feature engineering:**

1. **Identify feature version:**

   ```python
   # Check model metadata for feature version
   model_features_version = model_metadata["feature_version"]  # e.g., 'v2.3.1'
   ```

1. **Revert feature pipeline:**

   ```python
   # Airflow DAG version pinning
   from airflow import DAG

   # Trigger previous DAG version
   trigger_dag(
       dag_id="feature_engineering_pipeline",
       conf={"version": "v2.3.0"},  # Previous stable version
   )
   ```

1. **Validate feature consistency:**

   ```python
   # Compare feature distributions
   from scipy.stats import ks_2samp

   old_features = load_features(version="v2.3.0")
   new_features = load_features(version="v2.3.1")

   for feature in critical_features:
       stat, pval = ks_2samp(old_features[feature], new_features[feature])
       assert pval > 0.05, f"Feature {feature} distribution changed significantly"
   ```

### Model Drift Monitoring & Auto-Rollback

**Automated rollback triggers:**

```python
# Example monitoring script
import numpy as np
from evidently.metric_preset import DataDriftPreset
from evidently.report import Report


def check_drift_and_rollback(reference_data, current_data, threshold=0.2):
    """
    Monitor drift and trigger rollback if PSI > threshold
    """
    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=reference_data, current_data=current_data)

    drift_score = report.as_dict()["metrics"][0]["result"]["dataset_drift_score"]

    if drift_score > threshold:
        print(f"ALERT: Drift score {drift_score} exceeds threshold {threshold}")
        # Trigger rollback
        rollback_to_previous_model()
        send_alert(f"Auto-rollback triggered due to drift: {drift_score}")
        return True

    return False


# Run every hour
schedule.every(1).hours.do(
    check_drift_and_rollback, reference_data=training_data, current_data=production_data
)
```

### Post-Rollback Verification

After executing rollback, verify:

1. **Model Serving Health:**

   - [ ] Model endpoint responding with 200 status
   - [ ] Prediction latency < SLA (p95, p99)
   - [ ] Prediction success rate > 99%
   - [ ] No model inference errors in logs

1. **Model Performance:**

   - [ ] Primary metrics back to baseline (within 1%)
   - [ ] Secondary metrics stable
   - [ ] Offline evaluation passing acceptance criteria
   - [ ] A/B test shows no degradation vs control

1. **Data Quality:**

   - [ ] Feature distributions match expected ranges
   - [ ] No missing feature values
   - [ ] Data schema validation passing
   - [ ] Upstream data pipelines healthy

1. **Business Metrics:**

   - [ ] Revenue metrics stable (conversion, AOV, CTR)
   - [ ] Customer behavior metrics unchanged
   - [ ] Support ticket volume normal
   - [ ] No regulatory compliance alerts

1. **Monitoring & Alerting:**

   - [ ] Drift detection monitoring active
   - [ ] Performance dashboards updated
   - [ ] Alert thresholds recalibrated
   - [ ] On-call team notified of rollback

### Rollback Documentation

After each rollback, document:

- **Model Metadata:**

  - Previous model version: [version]
  - Current model version: [version]
  - Rollback timestamp: [ISO-8601]
  - Rollback duration: [minutes]

- **Root Cause:**

  - Performance degradation: [metric name, % drop]
  - Data drift: [features affected, PSI score]
  - Technical failure: [error type, frequency]
  - Business impact: [revenue impact, customer complaints]

- **Rollback Method:**

  - [ ] Model version pinning
  - [ ] Traffic shifting
  - [ ] A/B test termination
  - [ ] Container rollback
  - [ ] Feature pipeline revert

- **Impact Assessment:**

  - Predictions affected: [number or %]
  - Revenue impact: [estimated $]
  - Customer impact: [user count]
  - Data integrity: [any data loss/corruption]

- **Follow-up Actions:**

  - Incident ticket: [TICKET-ID]
  - Postmortem scheduled: [date]
  - Retraining plan: [yes/no, timeline]
  - Model improvement tasks: [list]

### Prevention: Pre-Deployment Checklist

To minimize rollback risk:

- [ ] **Shadow mode testing:** New model running in parallel, predictions logged but not served
- [ ] **Offline metrics:** All evaluation metrics pass acceptance criteria (e.g., AUC > 0.85)
- [ ] **Data validation:** Feature distributions within expected ranges (PSI < 0.1)
- [ ] **Canary deployment:** Start with 5-10% traffic, monitor for 24-48 hours
- [ ] **A/B test design:** Statistical power analysis, sample size calculation, success criteria defined
- [ ] **Rollback testing:** Rollback procedure tested in staging environment
- [ ] **Monitoring dashboards:** Drift detection, performance metrics, business KPIs
- [ ] **Alert configuration:** Automated alerts for drift > threshold, latency > SLA, errors > 1%
- [ ] **Model card:** Documentation of model architecture, training data, evaluation metrics, limitations
- [ ] **On-call coverage:** ML engineer and data scientist identified and available
- [ ] **Feature flags:** Instant disable capability via feature flag
- [ ] **Versioning:** Model, features, and data pipeline versions tracked in registry

### Model Rollback SLAs

| Rollback Trigger | Detection Time | Rollback Execution | Total Recovery Time |
|-----------------|----------------|-------------------|-------------------|
| Automated drift alert | < 5 minutes | 5-10 minutes | < 15 minutes |
| Performance degradation | < 15 minutes | 10-20 minutes | < 35 minutes |
| Business metric impact | < 1 hour | 15-30 minutes | < 90 minutes |
| Manual discovery | Variable | 15-30 minutes | Variable |

### Rollback vs Retrain Decision Tree

```
Model Issue Detected
│
├─ Immediate business impact? (revenue, customer)
│  ├─ YES → Rollback immediately, investigate later
│  └─ NO → Continue to next check
│
├─ Data quality issue?
│  ├─ YES → Fix data pipeline first, then decide
│  │         ├─ Quick fix possible? → Fix and monitor
│  │         └─ Complex fix needed? → Rollback, fix data, retrain
│  └─ NO → Continue to next check
│
├─ Model drift detected?
│  ├─ PSI > 0.3 → Rollback, retrain urgently
│  ├─ PSI 0.2-0.3 → Increase monitoring, plan retrain
│  └─ PSI < 0.2 → Monitor closely, scheduled retrain
│
└─ Performance degradation?
   ├─ > 10% drop → Rollback immediately
   ├─ 5-10% drop → Canary rollback (reduce traffic), investigate
   └─ < 5% drop → Monitor, may be acceptable variance
```

## Handoffs & Follow-Up

- Schedule recurring model reviews (monthly/quarterly) to assess drift and business value.
- Capture updates in the model registry with versioned documentation.
