______________________________________________________________________

title: Security Hardening Workflow
owner: Security & Compliance Office
last_reviewed: 2025-02-06
related_tools:

- commands/tools/maintenance/maintenance-cadence.md
- commands/tools/monitoring/observability-lifecycle.md
- commands/tools/workflow/privacy-impact-assessment.md
  risk: high
  status: active
  id: 01K6EF8EKEX284G0ND30WGYBW5

______________________________________________________________________

## Security Hardening Workflow

[Extended thinking: Reduce attack surface and embed ongoing security practices without disrupting delivery.]

## Overview

Use this workflow to plan and execute hardening campaigns across services, infrastructure, or processes.

## Prerequisites

- Identified security findings or audit requirements.
- Owners committed to remediation windows.
- Access to threat models, penetration test results, or vulnerability reports.

## Inputs

- `$ARGUMENTS` — scope of hardening effort.
- `$RISK_DRIVERS` — critical vulnerabilities or compliance obligations.
- `$TIMELINE` — target completion window.

## Outputs

- Prioritized remediation backlog with owners.
- Verified fixes and evidence packages for auditors.
- Updated policies, runbooks, and monitoring alerts.

## Phases

### Phase 0 – Threat Modeling & Attack Surface Analysis

**Before implementing security controls, understand your threats and attack surface:**

**Agent:** `security-auditor` leads threat modeling exercises

1. **Asset Identification & Classification:**

   ```markdown
   # Critical Assets Inventory

   ## Data Assets
   | Asset | Classification | Location | Encryption | Access Control |
   |-------|---------------|----------|------------|----------------|
   | Customer PII | Critical | PostgreSQL | At-rest: AES-256, In-transit: TLS 1.3 | RBAC + MFA |
   | Payment data | Critical | Stripe (external) | PCI-compliant | API keys rotated quarterly |
   | Session tokens | High | Redis | TLS only | Time-limited (24h) |
   | Application logs | Medium | CloudWatch | Server-side encryption | IAM roles |
   | Analytics data | Low | S3 | Default encryption | Public read (anonymized) |

   ## System Assets
   | Asset | Criticality | Exposure | Dependencies |
   |-------|------------|----------|--------------|
   | API Gateway | Critical | Public internet | Auth service, database |
   | Authentication Service | Critical | Internal only | Database, Redis |
   | Database (primary) | Critical | Private subnet | Backup service |
   | Admin Dashboard | High | VPN-only | API, Auth service |
   | Background Workers | Medium | Private subnet | Database, Queue |
   ```

1. **STRIDE Threat Modeling:**

   **S - Spoofing Identity:**

   ```markdown
   ## Spoofing Threats

   ### Threat 1: API Key Theft
   - **Description:** Attacker steals API key from client code or logs
   - **Impact:** Unauthorized access to customer data (HIGH)
   - **Likelihood:** Medium (keys often leaked in GitHub)
   - **Risk Score:** HIGH
   - **Mitigations:**
     - [ ] Implement API key rotation every 90 days
     - [ ] Add GitHub secret scanning
     - [ ] Require IP whitelisting for high-value keys
     - [ ] Implement rate limiting per key
   - **Residual Risk:** MEDIUM

   ### Threat 2: Session Token Hijacking
   - **Description:** Attacker intercepts session cookie via XSS or network sniffing
   - **Impact:** Account takeover (CRITICAL)
   - **Likelihood:** Low (if HTTPS enforced)
   - **Risk Score:** MEDIUM
   - **Mitigations:**
     - [ ] HttpOnly and Secure flags on all cookies
     - [ ] SameSite=Strict for CSRF protection
     - [ ] Short session timeouts (24 hours)
     - [ ] Bind sessions to IP address (optional, breaks mobile)
   - **Residual Risk:** LOW
   ```

   **T - Tampering with Data:**

   ```markdown
   ## Tampering Threats

   ### Threat 3: SQL Injection
   - **Description:** Attacker injects malicious SQL through user inputs
   - **Impact:** Data breach, data manipulation (CRITICAL)
   - **Likelihood:** Low (if parameterized queries used)
   - **Risk Score:** MEDIUM
   - **Mitigations:**
     - [ ] Use ORM or parameterized queries exclusively
     - [ ] Input validation on all user-supplied data
     - [ ] WAF rules for SQL injection patterns
     - [ ] Database user with minimal privileges
   - **Residual Risk:** LOW

   ### Threat 4: Message Queue Poisoning
   - **Description:** Attacker injects malicious jobs into queue
   - **Impact:** Remote code execution, data corruption (CRITICAL)
   - **Likelihood:** Low (if queue access controlled)
   - **Risk Score:** MEDIUM
   - **Mitigations:**
     - [ ] Message signing/verification (HMAC)
     - [ ] Queue access restricted to internal network
     - [ ] Job schema validation before processing
     - [ ] Sandboxed job execution environment
   - **Residual Risk:** LOW
   ```

   **R - Repudiation:**

   ```markdown
   ## Repudiation Threats

   ### Threat 5: Audit Log Tampering
   - **Description:** Attacker or insider modifies/deletes audit logs
   - **Impact:** Cannot prove unauthorized access occurred (HIGH)
   - **Likelihood:** Low (if logs are write-once)
   - **Risk Score:** MEDIUM
   - **Mitigations:**
     - [ ] Audit logs sent to immutable storage (S3 with versioning + object lock)
     - [ ] Separate AWS account for audit logs (cross-account access)
     - [ ] Cryptographic log signing (hash chain)
     - [ ] Real-time log forwarding to SIEM
   - **Residual Risk:** LOW

   ### Threat 6: Transaction Non-Repudiation
   - **Description:** Customer claims they didn't make a purchase
   - **Impact:** Revenue loss, dispute fees (MEDIUM)
   - **Likelihood:** Medium (common in e-commerce)
   - **Risk Score:** MEDIUM
   - **Mitigations:**
     - [ ] Log IP address, user agent, session ID for all transactions
     - [ ] Email confirmation for high-value purchases
     - [ ] Two-factor authentication for account changes
     - [ ] Audit trail of all order modifications
   - **Residual Risk:** MEDIUM (business risk)
   ```

   **I - Information Disclosure:**

   ```markdown
   ## Information Disclosure Threats

   ### Threat 7: API Response Information Leakage
   - **Description:** Error messages expose internal system details
   - **Impact:** Attacker learns technology stack, aids reconnaissance (MEDIUM)
   - **Likelihood:** High (common misconfiguration)
   - **Risk Score:** MEDIUM
   - **Mitigations:**
     - [ ] Generic error messages in production
     - [ ] Detailed errors logged internally only
     - [ ] Remove stack traces from API responses
     - [ ] Sanitize debug headers (X-Powered-By, Server)
   - **Residual Risk:** LOW

   ### Threat 8: Backup Data Exposure
   - **Description:** Database backups stored in misconfigured S3 bucket
   - **Impact:** Complete data breach (CRITICAL)
   - **Likelihood:** Low (if bucket policies correct)
   - **Risk Score:** MEDIUM
   - **Mitigations:**
     - [ ] Private S3 buckets (block public access)
     - [ ] Encrypted backups (AWS KMS)
     - [ ] Bucket policies restrict to specific IAM roles
     - [ ] Regular access audits (AWS Access Analyzer)
   - **Residual Risk:** LOW
   ```

   **D - Denial of Service:**

   ```markdown
   ## Denial of Service Threats

   ### Threat 9: API Rate Limit Bypass
   - **Description:** Attacker floods API with requests, degrading service
   - **Impact:** Service unavailable to legitimate users (HIGH)
   - **Likelihood:** High (common attack vector)
   - **Risk Score:** HIGH
   - **Mitigations:**
     - [ ] Rate limiting at multiple layers (CDN, API Gateway, application)
     - [ ] CAPTCHA for suspicious traffic patterns
     - [ ] Auto-scaling with upper limits
     - [ ] DDoS protection (Cloudflare, AWS Shield)
   - **Residual Risk:** MEDIUM

   ### Threat 10: Resource Exhaustion (slowloris)
   - **Description:** Slow HTTP attacks exhaust server connections
   - **Impact:** Service degradation (MEDIUM)
   - **Likelihood:** Medium
   - **Risk Score:** MEDIUM
   - **Mitigations:**
     - [ ] Connection timeouts (30 seconds max)
     - [ ] Reverse proxy with connection limits (nginx)
     - [ ] Traffic analysis and blocking (WAF rules)
     - [ ] Monitoring for connection pool exhaustion
   - **Residual Risk:** LOW
   ```

   **E - Elevation of Privilege:**

   ```markdown
   ## Elevation of Privilege Threats

   ### Threat 11: Insecure Direct Object Reference (IDOR)
   - **Description:** User modifies ID parameter to access other users' data
   - **Impact:** Unauthorized data access (HIGH)
   - **Likelihood:** Medium (common web vulnerability)
   - **Risk Score:** HIGH
   - **Mitigations:**
     - [ ] Authorization checks on all resource access
     - [ ] Use UUIDs instead of sequential IDs
     - [ ] Indirect object references (session-based mapping)
     - [ ] Automated IDOR testing in CI/CD
   - **Residual Risk:** LOW

   ### Threat 12: Container Escape
   - **Description:** Attacker breaks out of container to access host
   - **Impact:** Full infrastructure compromise (CRITICAL)
   - **Likelihood:** Very Low (requires kernel vulnerability)
   - **Risk Score:** LOW
   - **Mitigations:**
     - [ ] Run containers as non-root user
     - [ ] Seccomp and AppArmor profiles
     - [ ] Read-only root filesystems
     - [ ] Regular security updates for container runtime
   - **Residual Risk:** VERY LOW
   ```

1. **Data Flow Diagrams (DFD):**

   ```markdown
   # Level 0 DFD - System Context

   ```

   [Internet Users] --(HTTPS)--> [Load Balancer] --(HTTP)--> [API Servers]
   |
   +----------------------------+
   |
   +----------v-----------+
   | |
   [PostgreSQL] [Redis Cache]
   | |
   [Backup to S3] [Session Store]

   ```

   # Level 1 DFD - Authentication Flow

   ```

   [User] --1. POST /login--> [API Gateway] --2. Validate--> [Auth Service]
   |
   3\. Query credentials
   |
   [User Database]
   |
   4\. Return user record
   |
   [User] \<--5. JWT token---- [API Gateway] \<--Token---- [Auth Service]

   ```

   **Threat Analysis per Flow:**
   - Flow 1-2: TLS required, validate input size
   - Flow 2-3: Use parameterized queries (SQL injection prevention)
   - Flow 3-4: Encrypt PII in database (AES-256)
   - Flow 4-5: Sign JWT with strong secret, short expiry (1 hour)
   ```

1. **Attack Surface Mapping:**

   ```markdown
   # Attack Surface Inventory

   ## External Attack Surface (Public Internet)

   ### Web Application
   - **Entry Points:**
     - HTTPS endpoints: api.example.com/* (100+ endpoints)
     - GraphQL endpoint: api.example.com/graphql
     - Static assets: cdn.example.com/*
   - **Authentication:** Bearer tokens, API keys
   - **Input Vectors:** JSON POST bodies, query parameters, headers, file uploads
   - **Threats:** Injection, XSS, CSRF, authentication bypass

   ### DNS
   - **Entry Points:**
     - example.com, api.example.com, cdn.example.com
   - **Threats:** DNS hijacking, subdomain takeover, cache poisoning

   ### Email
   - **Entry Points:**
     - support@example.com (SPF/DKIM/DMARC configured)
   - **Threats:** Phishing, email spoofing, malware delivery

   ## Internal Attack Surface (Private Network)

   ### Database
   - **Entry Points:**
     - PostgreSQL port 5432 (internal VPC only)
   - **Access Control:** IAM-based, IP whitelisting
   - **Threats:** SQL injection (from compromised app), credential theft

   ### Message Queue
   - **Entry Points:**
     - RabbitMQ port 5672 (internal only)
   - **Access Control:** Username/password, TLS required
   - **Threats:** Message injection, queue poisoning

   ### Admin Tools
   - **Entry Points:**
     - Admin dashboard (VPN-only)
     - SSH access to EC2 instances (bastion host + MFA)
   - **Threats:** Credential compromise, privilege escalation

   ## Reduction Strategies

   - [ ] Remove unnecessary endpoints (found 12 unused endpoints)
   - [ ] Consolidate admin tools into single authenticated portal
   - [ ] Disable SSH, use AWS Systems Manager Session Manager instead
   - [ ] Implement API versioning to deprecate old attack surface
   - [ ] Rate limit all public endpoints
   ```

1. **DREAD Risk Scoring:**

   ```markdown
   # DREAD Methodology

   For each threat, score 1-10 on:
   - **D**amage potential
   - **R**eproducibility
   - **E**xploitability
   - **A**ffected users
   - **D**iscoverability

   ## Example: SQL Injection in User Search

   | Factor | Score | Justification |
   |--------|-------|---------------|
   | Damage | 10 | Complete database access, data breach |
   | Reproducibility | 10 | Always works if vulnerability exists |
   | Exploitability | 3 | Requires SQL knowledge, but common tools exist |
   | Affected Users | 10 | All users' data at risk |
   | Discoverability | 7 | SQLMap and scanners can find automatically |
   | **Total** | **40/50** | **HIGH RISK** |

   **Mitigation Priority:** IMMEDIATE (within 1 week)

   ## Risk Prioritization Matrix

   | Risk Score | Priority | SLA | Examples |
   |-----------|----------|-----|----------|
   | 40-50 | CRITICAL | 1 week | SQL injection, auth bypass |
   | 30-39 | HIGH | 1 month | IDOR, XSS with data access |
   | 20-29 | MEDIUM | 3 months | Information disclosure, CSRF |
   | 10-19 | LOW | 6 months | Minor info leaks, DoS (rate limited) |
   | 0-9 | INFORMATIONAL | Backlog | Theoretical vulnerabilities |
   ```

1. **Penetration Testing Integration:**

   ```markdown
   # Penetration Testing Workflow

   ## Frequency
   - **External Pentest:** Annually or after major releases
   - **Internal Pentest:** Annually
   - **Red Team Exercise:** Every 2 years

   ## Scope Definition

   ### In-Scope
   - api.example.com/*
   - admin.example.com/*
   - Mobile applications (iOS, Android)
   - Third-party integrations

   ### Out-of-Scope
   - Physical security
   - Social engineering (unless red team exercise)
   - Third-party services (AWS, Stripe, etc.)
   - Destructive testing (data deletion, permanent DoS)

   ## Engagement Process

   1. **Pre-Engagement (2 weeks before):**
      - [ ] Define scope and rules of engagement
      - [ ] Whitelist pentester IP addresses
      - [ ] Set up dedicated test accounts with realistic data
      - [ ] Notify security team and on-call engineers
      - [ ] Establish communication channel (Slack #pentest)

   2. **During Engagement (1-2 weeks):**
      - [ ] Daily standups with pentest team
      - [ ] Real-time vulnerability triage (critical findings → hotfix immediately)
      - [ ] Document findings in shared tracker
      - [ ] Provide application guidance as needed

   3. **Post-Engagement (1 week after):**
      - [ ] Receive final report with CVSS scores
      - [ ] Validate all findings in staging
      - [ ] Create remediation tickets with owners
      - [ ] Re-test fixes before sign-off
      - [ ] Share sanitized findings with engineering team for learning

   ## Findings Remediation SLA

   | CVSS Score | Severity | Remediation SLA |
   |-----------|----------|-----------------|
   | 9.0-10.0 | Critical | 7 days |
   | 7.0-8.9 | High | 30 days |
   | 4.0-6.9 | Medium | 90 days |
   | 0.1-3.9 | Low | 180 days |
   | 0.0 | Informational | Backlog |
   ```

1. **Threat Modeling Tools & Automation:**

   ```bash
   # OWASP Threat Dragon (open source threat modeling tool)
   docker run -p 3000:3000 owasp/threat-dragon

   # Microsoft Threat Modeling Tool (Windows only)
   # Download from: https://aka.ms/threatmodelingtool

   # Automated threat modeling from code
   # IriusRisk: https://www.iriusrisk.com/
   # Threagile: https://threagile.io/

   # STRIDE threat generator
   python scripts/stride_threat_generator.py \
     --dfd diagrams/authentication_flow.json \
     --output threats/authentication_threats.md

   # Attack surface analysis
   python scripts/attack_surface_mapper.py \
     --openapi api/openapi.yaml \
     --endpoints-output /tmp/attack_surface.csv

   # Dependency vulnerability scanning
   npm audit --json > npm-audit.json
   pip-audit --format json > pip-audit.json
   trivy image myapp:latest --format json > trivy-scan.json

   # Consolidate threat intel
   python scripts/consolidate_threat_intel.py \
     --stride threats/stride.json \
     --pentest reports/pentest-2025-09.pdf \
     --vulns npm-audit.json pip-audit.json trivy-scan.json \
     --output threat-model-2025-10.md
   ```

1. **Threat Intelligence Integration:**

   ```bash
   # Monitor CVE databases for dependencies
   curl https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=express \
     | jq '.vulnerabilities[] | {id: .cve.id, severity: .cve.metrics.cvssMetricV31[0].cvssData.baseSeverity}'

   # Check if your dependencies are affected
   safety check --json --key $SAFETY_API_KEY

   # Monitor security advisories
   gh api /repos/advisories --jq '.[] | select(.severity=="high" or .severity=="critical")'

   # OSINT monitoring for brand mentions in breach databases
   # (Use third-party service like Have I Been Pwned API)
   ```

**Threat Modeling Checklist:**

- [ ] Critical assets identified and classified
- [ ] Data flow diagrams created for key workflows
- [ ] STRIDE analysis completed for all entry points
- [ ] Attack surface mapped (external + internal)
- [ ] DREAD risk scores assigned to all threats
- [ ] Penetration testing scheduled (annually minimum)
- [ ] Threat modeling tools configured
- [ ] Threat intelligence feeds integrated
- [ ] Findings prioritized by risk score
- [ ] Mitigations assigned to owners with SLAs

**Deliverables:**

- Comprehensive threat model document
- Data flow diagrams (Level 0, Level 1, Level 2)
- Risk-scored threat inventory (STRIDE + DREAD)
- Attack surface reduction recommendations
- Penetration testing scope and schedule

### Phase 1 – Assess & Prioritize

- `security-auditor` reviews findings, classifies risk, and drafts remediation plan.
- `privacy-officer` assesses data protection implications using `commands/tools/workflow/privacy-impact-assessment.md`.

### Phase 2 – Implement Controls

- `developer-enablement-lead` coordinates code, configuration, or infrastructure changes.
- `architecture-council` reviews significant design updates.

### Phase 3 – Verify & Monitor

- `qa-strategist` validates fixes, including negative testing and regression coverage.
- `observability-incident-lead` ensures alerts detect policy violations or regressions.

### Phase 4 – Document & Institutionalize

- `content-designer` updates policy docs and runbooks.
- `maintenance-cadence.md` tool schedules recurring reviews and KPIs.

## Handoffs & Follow-Up

- Report status to leadership and auditors with evidence attachments.
- Integrate lessons learned into security training and onboarding.
