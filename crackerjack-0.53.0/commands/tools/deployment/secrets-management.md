______________________________________________________________________

title: Secrets Management
owner: Security Guild
last_reviewed: 2025-10-01
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: high
  status: active
  id: 01K6HDST4YKZQV8PX3NMWJ7HG2
  category: deployment
  agents:
- security-auditor
- devops-troubleshooter
- architecture-council
- terraform-specialist
  tags:
- secrets
- vault
- aws-secrets-manager
- gcp-secret-manager
- azure-key-vault
- kubernetes
- security

______________________________________________________________________

## Secrets Management

You are a secrets management expert specializing in secure storage, access control, and rotation of sensitive credentials. Design comprehensive secrets management solutions using HashiCorp Vault, cloud provider services (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault), and Kubernetes integration patterns with proper access control, audit logging, and zero-trust principles.

## Context

The user needs to implement secure secrets management to protect sensitive data (API keys, database passwords, certificates, encryption keys) with proper access control, rotation strategies, audit trails, and compliance requirements. Focus on production-ready patterns with defense-in-depth, least-privilege access, and automated rotation.

## Requirements for: $ARGUMENTS

1. **Secrets Storage**:

   - Centralized secret storage
   - Encryption at rest and in transit
   - Access control policies
   - Audit logging
   - Secret versioning

1. **Technology Selection**:

   - HashiCorp Vault for on-premise/hybrid
   - AWS Secrets Manager for AWS workloads
   - GCP Secret Manager for GCP workloads
   - Azure Key Vault for Azure workloads
   - Kubernetes secrets with external integration

1. **Access Patterns**:

   - Application integration (SDK, API)
   - Kubernetes sidecar/init containers
   - CI/CD pipeline integration
   - Development workflows (local, staging)
   - Emergency access (break-glass)

1. **Rotation Strategies**:

   - Automated rotation
   - Zero-downtime rotation
   - Rotation validation
   - Rollback procedures

1. **Compliance & Security**:

   - Principle of least privilege
   - Audit trail for all access
   - Encryption key management
   - Compliance requirements (SOC2, PCI-DSS, HIPAA)

______________________________________________________________________

## Technology Comparison

### When to Use Each Solution

| Feature | HashiCorp Vault | AWS Secrets Manager | GCP Secret Manager | Azure Key Vault |
|---------|----------------|---------------------|--------------------|--------------------|
| **Best For** | Multi-cloud, on-premise | AWS-native apps | GCP-native apps | Azure-native apps |
| **Dynamic Secrets** | ✅ Excellent | ❌ No | ❌ No | ❌ No |
| **Auto Rotation** | ✅ Yes (custom) | ✅ Built-in (RDS, etc) | ⚠️ Manual | ✅ Built-in |
| **Kubernetes Integration** | ✅ Native | ✅ External Secrets | ✅ External Secrets | ✅ External Secrets |
| **Encryption as a Service** | ✅ Yes | ❌ No | ❌ No | ✅ Yes (HSM) |
| **PKI/Certificates** | ✅ Built-in CA | ❌ Use ACM | ❌ Use Certificate Manager | ✅ Built-in |
| **Complexity** | High | Low | Low | Medium |
| **Cost** | Self-hosted | $0.40/secret/month | $0.06/10k ops | $0.03/10k ops |
| **Multi-region** | Self-managed | ✅ Auto-replicate | ✅ Auto-replicate | ✅ Auto-replicate |

**Choose HashiCorp Vault for:**

- Multi-cloud or hybrid environments
- Dynamic secret generation (database credentials, cloud IAM)
- Advanced features (PKI, encryption as a service)
- On-premise or air-gapped deployments
- Complex secret workflows

**Choose Cloud Provider Services for:**

- Cloud-native applications
- Simple secret storage needs
- Managed rotation for cloud services
- Lower operational overhead
- Native IAM integration

______________________________________________________________________

## HashiCorp Vault

### 1. Vault Server Setup

```bash
# docker-compose.yml
version: '3'

services:
  vault:
    image: vault:1.15
    container_name: vault
    ports:
      - "8200:8200"
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: "root"  # Dev only!
      VAULT_DEV_LISTEN_ADDRESS: "0.0.0.0:8200"
    cap_add:
      - IPC_LOCK
    volumes:
      - ./vault/config:/vault/config
      - vault-data:/vault/data
    command: server

  # Production setup with Consul backend
  vault-prod:
    image: vault:1.15
    ports:
      - "8200:8200"
    volumes:
      - ./vault/config/vault.hcl:/vault/config/vault.hcl
    environment:
      VAULT_ADDR: "http://127.0.0.1:8200"
    cap_add:
      - IPC_LOCK
    command: server -config=/vault/config/vault.hcl

  consul:
    image: consul:1.17
    ports:
      - "8500:8500"
    command: agent -server -ui -bootstrap-expect=1 -client=0.0.0.0

volumes:
  vault-data:
```

```hcl
# vault/config/vault.hcl
storage "consul" {
  address = "consul:8500"
  path    = "vault/"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 0
  tls_cert_file = "/vault/config/vault.crt"
  tls_key_file  = "/vault/config/vault.key"
}

api_addr = "http://127.0.0.1:8200"
cluster_addr = "https://127.0.0.1:8201"
ui = true

# Enable audit logging
audit {
  file {
    path = "/vault/logs/audit.log"
  }
}
```

### 2. Initialize and Unseal Vault

```bash
#!/bin/bash
# init-vault.sh

# Initialize Vault (produces unseal keys and root token)
vault operator init \
  -key-shares=5 \
  -key-threshold=3 \
  > vault-keys.txt

# Extract unseal keys
UNSEAL_KEY_1=$(grep 'Unseal Key 1' vault-keys.txt | awk '{print $4}')
UNSEAL_KEY_2=$(grep 'Unseal Key 2' vault-keys.txt | awk '{print $4}')
UNSEAL_KEY_3=$(grep 'Unseal Key 3' vault-keys.txt | awk '{print $4}')
ROOT_TOKEN=$(grep 'Initial Root Token' vault-keys.txt | awk '{print $4}')

# Unseal Vault (requires 3 of 5 keys)
vault operator unseal $UNSEAL_KEY_1
vault operator unseal $UNSEAL_KEY_2
vault operator unseal $UNSEAL_KEY_3

# Login with root token
vault login $ROOT_TOKEN

echo "Vault initialized and unsealed!"
echo "IMPORTANT: Store vault-keys.txt securely and delete from server!"
```

### 3. Configure Secret Engines

```bash
# Enable KV v2 secrets engine
vault secrets enable -version=2 kv

# Store a secret
vault kv put kv/my-app/database \
  username=dbuser \
  password=supersecret \
  host=db.example.com \
  port=5432

# Read a secret
vault kv get kv/my-app/database

# Get specific field
vault kv get -field=password kv/my-app/database

# List secrets
vault kv list kv/my-app/

# Delete secret
vault kv delete kv/my-app/database

# Undelete (if versioned)
vault kv undelete -versions=2 kv/my-app/database

# Destroy secret permanently
vault kv destroy -versions=2 kv/my-app/database
```

### 4. Dynamic Database Credentials

```bash
# Enable database secrets engine
vault secrets enable database

# Configure PostgreSQL connection
vault write database/config/postgresql \
  plugin_name=postgresql-database-plugin \
  allowed_roles="readonly,readwrite" \
  connection_url="postgresql://{{username}}:{{password}}@postgres:5432/mydb?sslmode=disable" \
  username="vaultadmin" \
  password="vaultpass"

# Create role for read-only access
vault write database/roles/readonly \
  db_name=postgresql \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl="1h" \
  max_ttl="24h"

# Create role for read-write access
vault write database/roles/readwrite \
  db_name=postgresql \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl="1h" \
  max_ttl="24h"

# Generate dynamic credentials
vault read database/creds/readonly
# Output:
# Key                Value
# ---                -----
# lease_id           database/creds/readonly/abc123
# lease_duration     1h
# username           v-root-readonly-xyz789
# password           A1b2C3d4E5f6G7h8
```

### 5. Python Application Integration

```python
# vault_client.py
import hvac
import os
from typing import Dict, Optional


class VaultClient:
    def __init__(self, url: str = None, token: str = None):
        self.url = url or os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.token = token or os.getenv("VAULT_TOKEN")

        self.client = hvac.Client(url=self.url, token=self.token)

        if not self.client.is_authenticated():
            raise Exception("Vault authentication failed")

    def get_secret(self, path: str, mount_point: str = "kv") -> Dict:
        """
        Get secret from KV v2 engine

        Args:
            path: Secret path (e.g., 'my-app/database')
            mount_point: Secret engine mount point

        Returns:
            Dict of secret data
        """
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path, mount_point=mount_point
            )
            return response["data"]["data"]
        except Exception as e:
            raise Exception(f"Failed to read secret {path}: {e}")

    def set_secret(self, path: str, data: Dict, mount_point: str = "kv"):
        """Write secret to KV v2 engine"""
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path, secret=data, mount_point=mount_point
            )
        except Exception as e:
            raise Exception(f"Failed to write secret {path}: {e}")

    def get_dynamic_db_creds(self, role: str) -> Dict:
        """
        Get dynamic database credentials

        Args:
            role: Database role name

        Returns:
            Dict with username, password, lease info
        """
        try:
            response = self.client.read(f"database/creds/{role}")
            return {
                "username": response["data"]["username"],
                "password": response["data"]["password"],
                "lease_id": response["lease_id"],
                "lease_duration": response["lease_duration"],
            }
        except Exception as e:
            raise Exception(f"Failed to get dynamic credentials: {e}")

    def renew_lease(self, lease_id: str, increment: int = 3600):
        """Renew a lease"""
        try:
            self.client.sys.renew_lease(lease_id, increment=increment)
        except Exception as e:
            raise Exception(f"Failed to renew lease: {e}")

    def revoke_lease(self, lease_id: str):
        """Revoke a lease"""
        try:
            self.client.sys.revoke_lease(lease_id)
        except Exception as e:
            raise Exception(f"Failed to revoke lease: {e}")


# Example usage
if __name__ == "__main__":
    vault = VaultClient()

    # Get static secret
    db_config = vault.get_secret("my-app/database")
    print(f"Database: {db_config['host']}")

    # Set secret
    vault.set_secret("my-app/api-keys", {"stripe": "sk_test_...", "sendgrid": "SG...."})

    # Get dynamic database credentials
    creds = vault.get_dynamic_db_creds("readonly")
    print(f"Dynamic user: {creds['username']}")

    # Use credentials...

    # Revoke when done
    vault.revoke_lease(creds["lease_id"])
```

### 6. Access Policies

```hcl
# policies/app-policy.hcl
# Policy for application to read secrets

path "kv/data/my-app/*" {
  capabilities = ["read"]
}

path "database/creds/readonly" {
  capabilities = ["read"]
}

# Deny access to admin paths
path "sys/*" {
  capabilities = ["deny"]
}
```

```bash
# Create policy
vault policy write app-policy policies/app-policy.hcl

# Create token with policy
vault token create -policy=app-policy -ttl=24h

# AppRole authentication (for apps)
vault auth enable approle

vault write auth/approle/role/my-app \
  token_policies="app-policy" \
  token_ttl=1h \
  token_max_ttl=4h

# Get role-id
vault read auth/approle/role/my-app/role-id

# Generate secret-id
vault write -f auth/approle/role/my-app/secret-id
```

```python
# approle_auth.py
def login_with_approle(role_id: str, secret_id: str):
    """Authenticate using AppRole"""
    client = hvac.Client(url="http://localhost:8200")

    response = client.auth.approle.login(role_id=role_id, secret_id=secret_id)

    token = response["auth"]["client_token"]
    client.token = token

    return client
```

______________________________________________________________________

## AWS Secrets Manager

### 1. Create Secrets

```python
# aws_secrets.py
import boto3
import json
from botocore.exceptions import ClientError


class AWSSecretsManager:
    def __init__(self, region_name="us-east-1"):
        self.client = boto3.client("secretsmanager", region_name=region_name)

    def create_secret(self, name: str, secret_value: dict, description: str = ""):
        """Create a new secret"""
        try:
            response = self.client.create_secret(
                Name=name,
                Description=description,
                SecretString=json.dumps(secret_value),
                Tags=[
                    {"Key": "Environment", "Value": "production"},
                    {"Key": "ManagedBy", "Value": "terraform"},
                ],
            )
            return response["ARN"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceExistsException":
                print(f"Secret {name} already exists")
                return None
            raise

    def get_secret(self, secret_name: str) -> dict:
        """Retrieve secret value"""
        try:
            response = self.client.get_secret_value(SecretId=secret_name)

            if "SecretString" in response:
                return json.loads(response["SecretString"])
            else:
                # Binary secret
                return response["SecretBinary"]

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                raise Exception(f"Secret {secret_name} not found")
            elif e.response["Error"]["Code"] == "InvalidRequestException":
                raise Exception(f"Invalid request for {secret_name}")
            elif e.response["Error"]["Code"] == "InvalidParameterException":
                raise Exception(f"Invalid parameter for {secret_name}")
            raise

    def update_secret(self, name: str, secret_value: dict):
        """Update secret value"""
        try:
            self.client.update_secret(
                SecretId=name, SecretString=json.dumps(secret_value)
            )
        except ClientError as e:
            raise Exception(f"Failed to update secret: {e}")

    def rotate_secret(self, secret_name: str, lambda_arn: str):
        """Enable automatic rotation"""
        try:
            self.client.rotate_secret(
                SecretId=secret_name,
                RotationLambdaARN=lambda_arn,
                RotationRules={"AutomaticallyAfterDays": 30},
            )
        except ClientError as e:
            raise Exception(f"Failed to rotate secret: {e}")

    def list_secrets(self, filters: list = None):
        """List all secrets"""
        try:
            paginator = self.client.get_paginator("list_secrets")

            params = {}
            if filters:
                params["Filters"] = filters

            secrets = []
            for page in paginator.paginate(**params):
                secrets.extend(page["SecretList"])

            return secrets
        except ClientError as e:
            raise Exception(f"Failed to list secrets: {e}")


# Example usage
if __name__ == "__main__":
    sm = AWSSecretsManager(region_name="us-east-1")

    # Create secret
    arn = sm.create_secret(
        name="prod/myapp/database",
        secret_value={
            "username": "admin",
            "password": "supersecret",
            "host": "db.example.com",
            "port": 5432,
            "database": "myapp",
        },
        description="Production database credentials",
    )
    print(f"Secret created: {arn}")

    # Get secret
    db_creds = sm.get_secret("prod/myapp/database")
    print(f"Database host: {db_creds['host']}")

    # Update secret
    db_creds["password"] = "newsupersecret"
    sm.update_secret("prod/myapp/database", db_creds)
```

### 2. Automatic Rotation with Lambda

```python
# lambda_rotation.py
import boto3
import json
import psycopg2
import string
import secrets


def lambda_handler(event, context):
    """
    Lambda function to rotate RDS PostgreSQL password

    Steps:
    1. Create new password
    2. Set AWSPENDING secret version
    3. Test new password
    4. Finalize rotation
    """
    service_client = boto3.client("secretsmanager")

    arn = event["SecretId"]
    token = event["ClientRequestToken"]
    step = event["Step"]

    # Get secret metadata
    metadata = service_client.describe_secret(SecretId=arn)

    if step == "createSecret":
        create_secret(service_client, arn, token)

    elif step == "setSecret":
        set_secret(service_client, arn, token)

    elif step == "testSecret":
        test_secret(service_client, arn, token)

    elif step == "finishSecret":
        finish_secret(service_client, arn, token)

    else:
        raise ValueError(f"Invalid step: {step}")


def create_secret(service_client, arn, token):
    """Generate new password"""
    # Get current secret
    current = service_client.get_secret_value(SecretId=arn, VersionStage="AWSCURRENT")
    current_dict = json.loads(current["SecretString"])

    # Generate new password
    new_password = "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(32)
    )

    # Create pending secret
    current_dict["password"] = new_password

    service_client.put_secret_value(
        SecretId=arn,
        ClientRequestToken=token,
        SecretString=json.dumps(current_dict),
        VersionStages=["AWSPENDING"],
    )


def set_secret(service_client, arn, token):
    """Set new password in database"""
    # Get pending secret
    pending = service_client.get_secret_value(
        SecretId=arn, VersionId=token, VersionStage="AWSPENDING"
    )
    pending_dict = json.loads(pending["SecretString"])

    # Connect to database and change password
    conn = psycopg2.connect(
        host=pending_dict["host"],
        port=pending_dict["port"],
        user=pending_dict["username"],
        password=pending_dict["password"],  # Old password
        database=pending_dict["database"],
    )

    cursor = conn.cursor()
    cursor.execute(
        f"ALTER USER {pending_dict['username']} WITH PASSWORD %s",
        (pending_dict["password"],),  # New password
    )
    conn.commit()
    cursor.close()
    conn.close()


def test_secret(service_client, arn, token):
    """Test new password works"""
    pending = service_client.get_secret_value(
        SecretId=arn, VersionId=token, VersionStage="AWSPENDING"
    )
    pending_dict = json.loads(pending["SecretString"])

    # Try to connect with new password
    conn = psycopg2.connect(
        host=pending_dict["host"],
        port=pending_dict["port"],
        user=pending_dict["username"],
        password=pending_dict["password"],
        database=pending_dict["database"],
    )
    conn.close()


def finish_secret(service_client, arn, token):
    """Finalize rotation"""
    # Move AWSCURRENT to new version
    service_client.update_secret_version_stage(
        SecretId=arn,
        VersionStage="AWSCURRENT",
        MoveToVersionId=token,
        RemoveFromVersionId=metadata["VersionIdsToStages"]["AWSCURRENT"][0],
    )
```

### 3. Terraform Configuration

```hcl
# secrets.tf
resource "aws_secretsmanager_secret" "database" {
  name        = "prod/myapp/database"
  description = "Production database credentials"

  recovery_window_in_days = 30  # Deletion protection

  tags = {
    Environment = "production"
    Application = "myapp"
  }
}

resource "aws_secretsmanager_secret_version" "database" {
  secret_id = aws_secretsmanager_secret.database.id
  secret_string = jsonencode({
    username = "admin"
    password = random_password.db_password.result
    host     = aws_db_instance.main.address
    port     = 5432
    database = "myapp"
  })
}

# Random password generation
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# Automatic rotation
resource "aws_secretsmanager_secret_rotation" "database" {
  secret_id           = aws_secretsmanager_secret.database.id
  rotation_lambda_arn = aws_lambda_function.rotate_secret.arn

  rotation_rules {
    automatically_after_days = 30
  }
}

# IAM policy for application
resource "aws_iam_policy" "app_secrets_read" {
  name = "myapp-secrets-read"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.database.arn
        ]
      }
    ]
  })
}
```

______________________________________________________________________

## GCP Secret Manager

### 1. Python Integration

```python
# gcp_secrets.py
from google.cloud import secretmanager
from google.api_core import exceptions
import json


class GCPSecretManager:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.client = secretmanager.SecretManagerServiceClient()
        self.parent = f"projects/{project_id}"

    def create_secret(self, secret_id: str, labels: dict = None):
        """Create a secret (without value)"""
        try:
            secret = {
                "replication": {
                    "automatic": {}  # Auto-replicate
                }
            }

            if labels:
                secret["labels"] = labels

            response = self.client.create_secret(
                request={
                    "parent": self.parent,
                    "secret_id": secret_id,
                    "secret": secret,
                }
            )
            return response.name

        except exceptions.AlreadyExists:
            print(f"Secret {secret_id} already exists")
            return f"{self.parent}/secrets/{secret_id}"

    def add_secret_version(self, secret_id: str, payload: dict):
        """Add a new version to secret"""
        secret_name = f"{self.parent}/secrets/{secret_id}"

        # Convert dict to JSON string
        payload_bytes = json.dumps(payload).encode("UTF-8")

        response = self.client.add_secret_version(
            request={"parent": secret_name, "payload": {"data": payload_bytes}}
        )
        return response.name

    def get_secret(self, secret_id: str, version: str = "latest") -> dict:
        """Get secret value"""
        name = f"{self.parent}/secrets/{secret_id}/versions/{version}"

        try:
            response = self.client.access_secret_version(request={"name": name})
            payload = response.payload.data.decode("UTF-8")
            return json.loads(payload)

        except exceptions.NotFound:
            raise Exception(f"Secret {secret_id} not found")

    def list_secrets(self):
        """List all secrets"""
        request = {"parent": self.parent}

        secrets = []
        for secret in self.client.list_secrets(request=request):
            secrets.append(
                {
                    "name": secret.name,
                    "labels": dict(secret.labels),
                    "created": secret.create_time,
                }
            )
        return secrets

    def delete_secret(self, secret_id: str):
        """Delete a secret"""
        name = f"{self.parent}/secrets/{secret_id}"
        self.client.delete_secret(request={"name": name})

    def enable_secret_version(self, secret_id: str, version: str):
        """Enable a disabled version"""
        name = f"{self.parent}/secrets/{secret_id}/versions/{version}"
        self.client.enable_secret_version(request={"name": name})

    def disable_secret_version(self, secret_id: str, version: str):
        """Disable a version"""
        name = f"{self.parent}/secrets/{secret_id}/versions/{version}"
        self.client.disable_secret_version(request={"name": name})


# Example usage
if __name__ == "__main__":
    sm = GCPSecretManager(project_id="my-project")

    # Create secret
    sm.create_secret(
        secret_id="database-credentials", labels={"env": "production", "app": "myapp"}
    )

    # Add secret version
    sm.add_secret_version(
        "database-credentials",
        {"username": "admin", "password": "supersecret", "host": "db.example.com"},
    )

    # Get secret
    creds = sm.get_secret("database-credentials")
    print(f"Database: {creds['host']}")
```

### 2. Terraform Configuration

```hcl
# gcp_secrets.tf
resource "google_secret_manager_secret" "database" {
  secret_id = "database-credentials"

  replication {
    automatic = true  # Replicate to all regions
  }

  labels = {
    environment = "production"
    application = "myapp"
  }
}

resource "google_secret_manager_secret_version" "database" {
  secret = google_secret_manager_secret.database.id

  secret_data = jsonencode({
    username = "admin"
    password = random_password.db_password.result
    host     = google_sql_database_instance.main.private_ip_address
  })
}

# IAM binding for service account
resource "google_secret_manager_secret_iam_member" "app_access" {
  secret_id = google_secret_manager_secret.database.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app.email}"
}
```

______________________________________________________________________

## Kubernetes Integration

### 1. External Secrets Operator

```yaml
# external-secrets-operator.yaml
# Install with Helm:
# helm repo add external-secrets https://charts.external-secrets.io
# helm install external-secrets external-secrets/external-secrets -n external-secrets-system --create-namespace

apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secretsmanager
  namespace: default
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa

---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: database-credentials
  namespace: default
spec:
  refreshInterval: 1h  # Sync every hour

  secretStoreRef:
    name: aws-secretsmanager
    kind: SecretStore

  target:
    name: database-secret  # Kubernetes secret name
    creationPolicy: Owner

  data:
    - secretKey: username
      remoteRef:
        key: prod/myapp/database
        property: username

    - secretKey: password
      remoteRef:
        key: prod/myapp/database
        property: password

    - secretKey: host
      remoteRef:
        key: prod/myapp/database
        property: host

---
# Use in deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      containers:
        - name: app
          image: myapp:latest
          env:
            - name: DB_USERNAME
              valueFrom:
                secretKeyRef:
                  name: database-secret
                  key: username
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: database-secret
                  key: password
            - name: DB_HOST
              valueFrom:
                secretKeyRef:
                  name: database-secret
                  key: host
```

### 2. Vault Agent Sidecar

```yaml
# vault-sidecar.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "myapp"
        vault.hashicorp.com/agent-inject-secret-database: "kv/data/myapp/database"
        vault.hashicorp.com/agent-inject-template-database: |
          {{- with secret "kv/data/myapp/database" -}}
          export DB_USERNAME="{{ .Data.data.username }}"
          export DB_PASSWORD="{{ .Data.data.password }}"
          export DB_HOST="{{ .Data.data.host }}"
          {{- end }}
    spec:
      serviceAccountName: myapp
      containers:
        - name: app
          image: myapp:latest
          command:
            - sh
            - -c
            - |
              source /vault/secrets/database
              exec /app/start.sh
```

### 3. Sealed Secrets

```bash
# Install sealed-secrets controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# Install kubeseal CLI
brew install kubeseal

# Create a secret
kubectl create secret generic mysecret \
  --from-literal=username=admin \
  --from-literal=password=supersecret \
  --dry-run=client -o yaml > secret.yaml

# Seal the secret (encrypt)
kubeseal -f secret.yaml -w sealed-secret.yaml

# The sealed secret can be safely committed to Git
cat sealed-secret.yaml
```

```yaml
# sealed-secret.yaml (generated)
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: mysecret
  namespace: default
spec:
  encryptedData:
    username: AgBR7V... (encrypted)
    password: AgCK3M... (encrypted)
```

______________________________________________________________________

## Security Considerations

### 1. Principle of Least Privilege

```python
# Example: Time-bound access
from datetime import datetime, timedelta


def get_temporary_credentials(vault_client, role, duration_minutes=60):
    """Get credentials with limited TTL"""
    ttl = f"{duration_minutes}m"

    # Generate token with short TTL
    token_response = vault_client.auth.token.create(
        policies=[role],
        ttl=ttl,
        renewable=False,  # Cannot be renewed
        explicit_max_ttl=ttl,
    )

    return token_response["auth"]["client_token"]
```

### 2. Audit Logging

```python
# Parse Vault audit logs
import json


def analyze_vault_audit_log(log_file):
    """Analyze Vault audit logs for suspicious activity"""
    suspicious_events = []

    with open(log_file) as f:
        for line in f:
            entry = json.loads(line)

            # Check for unusual access patterns
            if entry["type"] == "response":
                # Multiple failed authentications
                if entry["auth"] and not entry["auth"].get("authenticated"):
                    suspicious_events.append(
                        {
                            "time": entry["time"],
                            "ip": entry["request"]["remote_address"],
                            "reason": "Failed authentication",
                        }
                    )

                # Access to sensitive paths
                if "admin" in entry["request"]["path"]:
                    suspicious_events.append(
                        {
                            "time": entry["time"],
                            "user": entry["auth"].get("display_name"),
                            "path": entry["request"]["path"],
                            "reason": "Admin path access",
                        }
                    )

    return suspicious_events
```

### 3. Secret Rotation

```python
# secrets_rotation.py
import schedule
import time
from datetime import datetime


class SecretRotator:
    def __init__(self, secrets_manager):
        self.sm = secrets_manager
        self.rotation_log = []

    def rotate_database_password(self, secret_name):
        """Rotate database password with zero downtime"""
        print(f"Starting rotation for {secret_name} at {datetime.now()}")

        try:
            # 1. Get current secret
            current = self.sm.get_secret(secret_name)

            # 2. Generate new password
            new_password = generate_secure_password(length=32)

            # 3. Create new user in database with new password
            create_temp_db_user(
                username=f"{current['username']}_new", password=new_password
            )

            # 4. Update secret
            current["password"] = new_password
            current["username"] = f"{current['username']}_new"
            self.sm.update_secret(secret_name, current)

            # 5. Wait for applications to pick up new secret
            time.sleep(300)  # 5 minutes

            # 6. Delete old user
            delete_db_user(current["username"].replace("_new", ""))

            # 7. Log success
            self.rotation_log.append(
                {"secret": secret_name, "time": datetime.now(), "status": "success"}
            )

            print(f"Rotation completed for {secret_name}")

        except Exception as e:
            print(f"Rotation failed: {e}")
            self.rotation_log.append(
                {
                    "secret": secret_name,
                    "time": datetime.now(),
                    "status": "failed",
                    "error": str(e),
                }
            )

    def schedule_rotations(self):
        """Schedule automatic rotations"""
        # Rotate every 30 days
        schedule.every(30).days.do(
            self.rotate_database_password, secret_name="prod/myapp/database"
        )

        while True:
            schedule.run_pending()
            time.sleep(3600)  # Check every hour
```

### Security Checklist

- [ ] All secrets encrypted at rest
- [ ] TLS/HTTPS for all secret access
- [ ] Principle of least privilege enforced
- [ ] Audit logging enabled and monitored
- [ ] Secrets rotated regularly (30-90 days)
- [ ] No secrets in code or version control
- [ ] No secrets in container images
- [ ] Access reviewed quarterly
- [ ] Break-glass procedures documented
- [ ] Compliance requirements met (SOC2, PCI-DSS)

______________________________________________________________________

## Testing & Validation

### Unit Testing

```python
# test_secrets.py
import pytest
from unittest.mock import Mock, patch
from vault_client import VaultClient


@pytest.fixture
def mock_vault_client():
    with patch("hvac.Client") as mock_client:
        mock_instance = Mock()
        mock_instance.is_authenticated.return_value = True
        mock_client.return_value = mock_instance
        yield mock_instance


def test_get_secret(mock_vault_client):
    mock_vault_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": {"password": "test123"}}
    }

    vault = VaultClient(url="http://localhost:8200", token="test-token")
    secret = vault.get_secret("test/secret")

    assert secret["password"] == "test123"


def test_get_secret_not_found(mock_vault_client):
    mock_vault_client.secrets.kv.v2.read_secret_version.side_effect = Exception(
        "Not found"
    )

    vault = VaultClient(url="http://localhost:8200", token="test-token")

    with pytest.raises(Exception):
        vault.get_secret("nonexistent/secret")
```

### Integration Testing

```python
# test_secrets_integration.py
import pytest
from aws_secrets import AWSSecretsManager


@pytest.fixture(scope="module")
def secrets_manager():
    """Use localstack for testing"""
    return AWSSecretsManager(
        region_name="us-east-1",
        endpoint_url="http://localhost:4566",  # LocalStack
    )


def test_create_and_retrieve_secret(secrets_manager):
    secret_name = "test/integration/database"
    secret_value = {"username": "test", "password": "test123"}

    # Create
    arn = secrets_manager.create_secret(secret_name, secret_value)
    assert arn is not None

    # Retrieve
    retrieved = secrets_manager.get_secret(secret_name)
    assert retrieved["username"] == "test"

    # Cleanup
    secrets_manager.client.delete_secret(
        SecretId=secret_name, ForceDeleteWithoutRecovery=True
    )
```

### Testing Checklist

- [ ] Secret creation works
- [ ] Secret retrieval works
- [ ] Secret updates work
- [ ] Secret deletion works
- [ ] Access control policies enforced
- [ ] Rotation completes without errors
- [ ] Applications handle secret updates
- [ ] Audit logs capture all operations
- [ ] Performance acceptable (\<100ms per operation)

______________________________________________________________________

## Troubleshooting

### Common Issues

#### Issue: "Access Denied" Errors

**Symptoms:**

- Applications cannot read secrets
- 403 Forbidden errors
- Authentication failures

**Causes:**

- Insufficient IAM permissions
- Wrong Vault policy
- Expired tokens/credentials
- Incorrect secret path

**Solutions:**

1. **Verify IAM permissions (AWS)**:

```bash
# Check current IAM identity
aws sts get-caller-identity

# Test secret access
aws secretsmanager get-secret-value --secret-id prod/myapp/database
```

2. **Check Vault policy**:

```bash
# List policies for token
vault token lookup

# View policy contents
vault policy read app-policy
```

3. **Debug with verbose logging**:

```python
import logging

logging.basicConfig(level=logging.DEBUG)

# AWS
import boto3

boto3.set_stream_logger("", logging.DEBUG)
```

______________________________________________________________________

#### Issue: Secret Rotation Failures

**Symptoms:**

- Rotation stuck in "InProgress"
- Applications lose access after rotation
- Database connection failures

**Causes:**

- Lambda function errors
- Database unavailable during rotation
- Network connectivity issues
- Insufficient permissions

**Solutions:**

1. **Check CloudWatch Logs** (AWS):

```bash
aws logs tail /aws/lambda/rotate-secret --follow
```

2. **Test rotation manually**:

```python
# Test connection with both old and new credentials
def test_rotation():
    old_creds = get_secret_version("AWSCURRENT")
    new_creds = get_secret_version("AWSPENDING")

    # Try old
    connect_db(old_creds)  # Should work

    # Try new
    connect_db(new_creds)  # Should work after setSecret step
```

3. **Rollback rotation**:

```bash
# AWS: Delete AWSPENDING version
aws secretsmanager put_secret_value \
  --secret-id prod/myapp/database \
  --version-stages AWSCURRENT \
  --client-request-token <previous-version-id>
```

______________________________________________________________________

#### Issue: Secrets Not Syncing to Kubernetes

**Symptoms:**

- ExternalSecret shows error
- Kubernetes Secret not created/updated
- Pods getting old secret values

**Causes:**

- External Secrets Operator not running
- Invalid SecretStore configuration
- IAM/RBAC permissions missing
- Network policy blocking egress

**Solutions:**

1. **Check ExternalSecret status**:

```bash
kubectl get externalsecret database-credentials -o yaml

# Look for status.conditions
kubectl describe externalsecret database-credentials
```

2. **Check operator logs**:

```bash
kubectl logs -n external-secrets-system \
  deployment/external-secrets -f
```

3. **Verify SecretStore**:

```bash
kubectl get secretstore aws-secretsmanager -o yaml

# Test connectivity
kubectl run test --rm -it --image=amazon/aws-cli \
  --serviceaccount=external-secrets-sa \
  -- secretsmanager get-secret-value --secret-id prod/myapp/database
```

______________________________________________________________________

### Getting Help

**Check Logs:**

- Vault audit logs: `/vault/logs/audit.log`
- AWS CloudWatch Logs for Lambda functions
- Kubernetes operator logs

**Related Tools:**

- Use `terraform-specialist` agent for IaC setup
- Use `security-auditor` agent for security review
- Use `devops-troubleshooter` agent for deployment issues

**Agents to Consult:**

- `security-auditor` - Security best practices
- `architecture-council` - Cloud provider integration
- `devops-troubleshooter` - Operational issues
- `terraform-specialist` - Infrastructure as code

______________________________________________________________________

## Best Practices

1. **Never Hardcode**: Never put secrets in code, config files, or version control
1. **Least Privilege**: Grant minimum required permissions to access secrets
1. **Rotate Regularly**: Rotate secrets every 30-90 days
1. **Audit Everything**: Enable audit logging and monitor access patterns
1. **Encrypt in Transit**: Always use TLS/HTTPS for secret access
1. **Separate Environments**: Use different secrets for dev/staging/prod
1. **Version Secrets**: Keep old versions for rollback capability
1. **Test Rotation**: Regularly test rotation procedures
1. **Break-Glass Procedures**: Document emergency access procedures
1. **Compliance**: Ensure secrets management meets compliance requirements

______________________________________________________________________

## Related Agents

**Primary Orchestrators**:

- `security-auditor` - Security architecture and compliance
- `devops-troubleshooter` - Deployment and operations
- `architecture-council` - Cloud provider integration

**Supporting Specialists**:

- `terraform-specialist` - Infrastructure as code
- `python-pro` - Python integration
- `docker-specialist` - Container secrets
- `kubernetes-specialist` - Kubernetes integration

**Quality & Compliance**:

- `compliance-check` - Regulatory compliance
- `observability-incident-lead` - Audit logging and monitoring
