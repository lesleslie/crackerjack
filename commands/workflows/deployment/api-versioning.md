______________________________________________________________________

title: API Versioning & Deprecation Workflow
owner: Delivery Operations
last_reviewed: 2025-10-01
related_tools:

- commands/tools/deployment/release-management.md
- commands/tools/monitoring/observability-lifecycle.md
- commands/tools/workflow/support-readiness.md
  risk: high
  status: active
  id: 01K6HMR2VXQWZ7N8KP4JT5YH6R

______________________________________________________________________

## API Versioning & Deprecation Workflow

[Extended thinking: Manage API evolution safely while maintaining backward compatibility, providing clear migration paths, and eventually sunsetting old versions without breaking customer integrations.]

## Overview

Use this workflow to introduce new API versions, communicate breaking changes, guide customers through migrations, and eventually deprecate old versions with minimal disruption.

## Prerequisites

- API versioning strategy documented (URL-based, header-based, or content negotiation)
- API documentation infrastructure (OpenAPI/Swagger)
- Analytics showing API endpoint usage by version
- Customer communication channels established

## Inputs

- `$ARGUMENTS` — API change description and business justification
- `$CHANGE_TYPE` — `backward_compatible`, `breaking_change`, `new_endpoint`, `deprecation`
- `$AFFECTED_VERSION` — current API version being modified
- `$NEW_VERSION` — new API version (if creating new version)

## Outputs

- Updated API specification (OpenAPI/Swagger)
- Deprecation timeline and migration guide
- Customer communication materials
- Version sunset schedule with usage metrics

## Phases

### Phase 0 – Prerequisites Validation

**Before starting API versioning work, validate current API state:**

1. **API Documentation Validation:**

   ```bash
   # Verify OpenAPI spec exists and is valid
   swagger-cli validate api/openapi.yaml || echo "ERROR: Invalid OpenAPI spec"

   # Check documentation is up to date
   diff <(curl -s https://api.example.com/openapi.json | jq -S) \
        <(cat api/openapi.yaml | yq -o json | jq -S) || \
        echo "WARNING: Deployed API doesn't match spec"

   # Verify all endpoints documented
   python scripts/check_undocumented_endpoints.py
   ```

1. **API Usage Analytics:**

   ```bash
   # Get endpoint usage by version (last 30 days)
   psql $ANALYTICS_DB -c "\
     SELECT api_version, endpoint, COUNT(*) as request_count \
     FROM api_requests \
     WHERE timestamp > NOW() - INTERVAL '30 days' \
     GROUP BY api_version, endpoint \
     ORDER BY request_count DESC \
     LIMIT 50;"

   # Identify active API consumers
   psql $ANALYTICS_DB -c "\
     SELECT DISTINCT api_key_id, api_version, \
            COUNT(*) as request_count, \
            MAX(timestamp) as last_seen \
     FROM api_requests \
     WHERE timestamp > NOW() - INTERVAL '30 days' \
     GROUP BY api_key_id, api_version \
     HAVING COUNT(*) > 100 \
     ORDER BY request_count DESC;"

   # Export to CSV for customer outreach
   psql $ANALYTICS_DB -c "\
     COPY (SELECT customer_email, api_version, COUNT(*) as request_count \
           FROM api_requests r JOIN customers c ON r.api_key_id = c.api_key_id \
           WHERE timestamp > NOW() - INTERVAL '30 days' \
           GROUP BY customer_email, api_version) \
     TO '/tmp/api_usage_by_customer.csv' CSV HEADER;"
   ```

1. **Breaking Change Detection:**

   ```bash
   # Use openapi-diff to detect breaking changes
   openapi-diff api/v1/openapi.yaml api/v2/openapi.yaml \
     --fail-on-incompatible || echo "WARNING: Breaking changes detected"

   # Categorize changes
   python scripts/analyze_api_changes.py \
     --old api/v1/openapi.yaml \
     --new api/v2/openapi.yaml \
     --output /tmp/api_change_report.json

   # Check for:
   # - Removed endpoints
   # - Removed request/response fields
   # - Changed required fields
   # - Changed data types
   # - Changed error codes
   ```

1. **Contract Testing Validation:**

   ```bash
   # Run consumer-driven contract tests
   pact verify --provider-base-url https://api-staging.example.com \
     --pact-broker-base-url $PACT_BROKER_URL

   # Check for contract violations
   [ $? -eq 0 ] || echo "ERROR: Contract violations detected"

   # Verify all major consumers have passing contracts
   pact-broker list-latest-pacts --broker-base-url $PACT_BROKER_URL
   ```

1. **Version Strategy Validation:**

   ```bash
   # Verify versioning strategy is consistent
   # URL-based: /v1/users, /v2/users
   # Header-based: Accept: application/vnd.api.v2+json
   # Query param: /users?version=2

   # Check current versioning approach
   curl -I https://api.example.com/v1/users | grep -i version

   # Ensure version detection working
   curl https://api.example.com/users -H "Accept: application/vnd.api.v1+json" | jq '.version'
   curl https://api.example.com/users -H "Accept: application/vnd.api.v2+json" | jq '.version'
   ```

1. **Deprecation Policy Check:**

   ```bash
   # Verify deprecation policy documented
   [ -f "docs/api-deprecation-policy.md" ] || echo "ERROR: No deprecation policy"

   # Check minimum notice period defined
   grep -q "minimum.*notice.*period" docs/api-deprecation-policy.md || \
     echo "WARNING: No minimum notice period defined"

   # Standard policy should include:
   # - Minimum 6-12 months notice
   # - Multiple communication touchpoints
   # - Migration guide provided
   # - Monitoring of deprecated endpoint usage
   ```

**Validation Checklist:**

- [ ] OpenAPI specification exists and is valid
- [ ] API documentation matches deployed API
- [ ] All endpoints are documented
- [ ] API usage analytics available (by version, customer, endpoint)
- [ ] Active API consumers identified
- [ ] Breaking changes detected and categorized
- [ ] Contract tests passing for major consumers
- [ ] Versioning strategy documented and consistent
- [ ] Deprecation policy documented (6-12 month notice minimum)
- [ ] Customer communication plan prepared

**If any validation fails:**

1. **CRITICAL**: Missing OpenAPI spec, no analytics → Create before versioning
1. **HIGH**: Breaking changes in minor version, no deprecation policy → Establish policy first
1. **MEDIUM**: Documentation out of date → Update before announcing new version

### Phase 1 – API Change Design & Planning

**Agent:** `architecture-council` leads API design

1. **Classify API Change:**

   **Type A: Backward Compatible (Minor Version Bump)**

   - Adding new endpoints
   - Adding optional request parameters
   - Adding response fields
   - Adding new enum values
   - **Action:** Safe to deploy to existing version

   **Type B: Breaking Change (Major Version Bump)**

   - Removing endpoints
   - Removing request/response fields
   - Changing field types
   - Making optional fields required
   - Changing authentication mechanism
   - **Action:** Requires new major version

   **Type C: Deprecation**

   - Marking endpoints or fields for future removal
   - Providing migration path to replacement
   - **Action:** Update documentation, add deprecation headers

1. **Version Strategy Selection:**

   **URL-Based Versioning (Recommended for REST):**

   ```
   /v1/users          → Current version
   /v2/users          → New version
   /v2/users/{id}     → New version

   Pros: Clear, cacheable, easy to route
   Cons: URL duplication, not RESTful purist
   ```

   **Header-Based Versioning:**

   ```
   GET /users
   Accept: application/vnd.api.v1+json    → Version 1
   Accept: application/vnd.api.v2+json    → Version 2

   Pros: Clean URLs, follows REST principles
   Cons: Harder to test, caching complexity
   ```

   **Content Negotiation:**

   ```
   GET /users
   Accept: application/json; version=1     → Version 1
   Accept: application/json; version=2     → Version 2

   Pros: Flexible, follows HTTP standards
   Cons: Less discoverable, client complexity
   ```

   **Query Parameter (Not Recommended for Production):**

   ```
   /users?version=1    → Version 1
   /users?version=2    → Version 2

   Pros: Easy to test
   Cons: Caching issues, not RESTful, can be accidentally omitted
   ```

1. **Design New API Version:**

   - Use Task tool with `subagent_type="architecture-council"` to design new API contracts
   - Create OpenAPI specification for new version
   - Document all breaking changes
   - Provide request/response examples
   - Design migration path from old to new

1. **Backward Compatibility Strategy:**

   **Strategy 1: API Gateway Transformation**

   ```yaml
   # Kong/Tyk/AWS API Gateway can transform requests
   - Match: /v1/users
     Transform:
       Request:
         - Rename field: "username" → "user_name"
         - Add default: "status" = "active"
       Response:
         - Rename field: "user_name" → "username"
         - Remove field: "internal_id"
   ```

   **Strategy 2: Adapter Layer**

   ```python
   # V1 adapter translates to V2 internally
   @app.route("/v1/users", methods=["POST"])
   def create_user_v1():
       v1_request = request.json
       # Transform to V2 format
       v2_request = {
           "user_name": v1_request.get("username"),
           "email": v1_request.get("email"),
           "status": "active",  # Default for v1 users
       }
       # Call V2 logic
       result = create_user_v2(v2_request)
       # Transform response back to V1 format
       return {"id": result["id"], "username": result["user_name"]}
   ```

   **Strategy 3: Parallel Implementation**

   ```python
   # Maintain separate handlers
   @app.route("/v1/users", methods=["POST"])
   def create_user_v1():
       # V1 logic
       return UserV1Schema().dump(user)


   @app.route("/v2/users", methods=["POST"])
   def create_user_v2():
       # V2 logic with new features
       return UserV2Schema().dump(user)
   ```

1. **Migration Guide Creation:**

   ````markdown
   # Migration Guide: API v1 → v2

   ## Breaking Changes

   ### 1. User Creation Endpoint

   **What Changed:**
   - Field `username` renamed to `user_name`
   - Field `status` now required (previously defaulted to "active")
   - Response includes new field `created_at`

   **v1 Request:**
   ```json
   POST /v1/users
   {
     "username": "john_doe",
     "email": "john@example.com"
   }
   ````

   **v2 Request:**

   ```json
   POST /v2/users
   {
     "user_name": "john_doe",
     "email": "john@example.com",
     "status": "active"
   }
   ```

   **Migration Code (JavaScript):**

   ```javascript
   // Before (v1)
   const response = await fetch('https://api.example.com/v1/users', {
     method: 'POST',
     body: JSON.stringify({ username: 'john_doe', email: 'john@example.com' })
   });

   // After (v2)
   const response = await fetch('https://api.example.com/v2/users', {
     method: 'POST',
     body: JSON.stringify({
       user_name: 'john_doe',  // Renamed field
       email: 'john@example.com',
       status: 'active'  // Now required
     })
   });
   ```

   ### 2. Authentication Changes

   **What Changed:**

   - API keys now required in header (not query param)
   - Header name changed from `X-API-Key` to `Authorization: Bearer <token>`

   **Before (v1):**

   ```bash
   curl https://api.example.com/v1/users?api_key=abc123
   ```

   **After (v2):**

   ```bash
   curl https://api.example.com/v2/users \
     -H "Authorization: Bearer abc123"
   ```

   ## Deprecation Timeline

   | Date | Milestone |
   |------|-----------|
   | 2025-10-01 | v2 released, v1 enters maintenance mode |
   | 2025-11-01 | Deprecation warnings added to v1 responses |
   | 2026-01-01 | v1 marked deprecated, migration guide prominent |
   | 2026-04-01 | v1 sunset announced (3 months notice) |
   | 2026-07-01 | v1 shut down |

   ## Testing Your Migration

   1. **Staging Environment:** Test against https://api-staging.example.com/v2
   1. **Contract Tests:** Download Postman collection or Pact contracts
   1. **Support:** Email api-support@example.com with questions

   ## Need Help?

   - [Interactive Migration Tool](https://example.com/api-migration-tool)
   - [v2 API Reference](https://docs.example.com/api/v2)
   - [Community Forum](https://community.example.com/api-v2)

   ```

   ```

**Planning Deliverables:**

- API change classification (backward compatible vs breaking)
- OpenAPI v2 specification
- Migration guide with code examples
- Deprecation timeline (6-12 months minimum)
- Communication plan

### Phase 2 – Implementation & Testing

**Agent:** `developer-enablement-lead` coordinates implementation

1. **Implement New API Version:**

   ```python
   # Example: Flask API versioning structure
   from flask import Flask, Blueprint

   app = Flask(__name__)

   # V1 Blueprint
   v1_api = Blueprint("v1", __name__, url_prefix="/v1")


   @v1_api.route("/users", methods=["GET"])
   def get_users_v1():
       # V1 logic
       users = User.query.all()
       return UserV1Schema(many=True).dump(users)


   # V2 Blueprint
   v2_api = Blueprint("v2", __name__, url_prefix="/v2")


   @v2_api.route("/users", methods=["GET"])
   def get_users_v2():
       # V2 logic with new features
       users = User.query.all()
       return UserV2Schema(many=True).dump(users)


   app.register_blueprint(v1_api)
   app.register_blueprint(v2_api)
   ```

1. **Add Deprecation Headers (for v1):**

   ```python
   from functools import wraps
   from datetime import datetime


   def deprecated_endpoint(sunset_date, replacement_url):
       def decorator(f):
           @wraps(f)
           def wrapped(*args, **kwargs):
               response = f(*args, **kwargs)
               # Add deprecation headers
               response.headers["Deprecation"] = "true"
               response.headers["Sunset"] = sunset_date.isoformat()
               response.headers["Link"] = f'<{replacement_url}>; rel="successor-version"'
               # Add deprecation warning in response body
               if isinstance(response.json, dict):
                   response.json["_deprecation"] = {
                       "deprecated": True,
                       "sunset_date": sunset_date.isoformat(),
                       "message": f"This endpoint will be removed on {sunset_date}. Migrate to {replacement_url}",
                       "migration_guide": "https://docs.example.com/api/v2/migration",
                   }
               return response

           return wrapped

       return decorator


   @app.route("/v1/users", methods=["GET"])
   @deprecated_endpoint(
       sunset_date=datetime(2026, 7, 1), replacement_url="https://api.example.com/v2/users"
   )
   def get_users_v1():
       users = User.query.all()
       return UserV1Schema(many=True).dump(users)
   ```

1. **Implement API Metrics & Monitoring:**

   ```python
   from prometheus_client import Counter, Histogram

   # Track API version usage
   api_requests_total = Counter(
       "api_requests_total", "Total API requests", ["version", "endpoint", "status"]
   )

   # Track response times by version
   api_request_duration = Histogram(
       "api_request_duration_seconds", "API request duration", ["version", "endpoint"]
   )


   @app.before_request
   def track_api_version():
       g.api_version = request.path.split("/")[1]  # Extract version from /v1/users
       g.start_time = time.time()


   @app.after_request
   def record_metrics(response):
       duration = time.time() - g.start_time
       api_request_duration.labels(
           version=g.api_version, endpoint=request.endpoint
       ).observe(duration)

       api_requests_total.labels(
           version=g.api_version, endpoint=request.endpoint, status=response.status_code
       ).inc()

       return response
   ```

1. **Contract Testing:**

   ```python
   # Pact consumer test (client-side)
   from pact import Consumer, Provider

   pact = Consumer('MyApp').has_pact_with(Provider('API'))

   pact.given('user exists') \
       .upon_receiving('a request for user details') \
       .with_request('GET', '/v2/users/123', headers={'Accept': 'application/json'}) \
       .will_respond_with(200, body={
           'id': 123,
           'user_name': 'john_doe',
           'email': 'john@example.com',
           'created_at': '2025-01-01T00:00:00Z'
       })

   # Pact provider test (server-side)
   # Verifies API actually returns what contract promises
   pact-verifier verify \
     --provider-base-url https://api-staging.example.com \
     --pact-broker-base-url $PACT_BROKER_URL \
     --provider-version v2.0.0
   ```

1. **Integration Testing:**

   ```bash
   # Test v1 still works
   pytest tests/api/v1/ --env staging

   # Test v2 new functionality
   pytest tests/api/v2/ --env staging

   # Test migration scenarios (calling both v1 and v2)
   pytest tests/api/migration/ --env staging

   # Test backward compatibility adapter (if using)
   pytest tests/api/backward_compat/ --env staging
   ```

1. **Performance Testing:**

   ```bash
   # Load test v2 to ensure no regressions
   k6 run --vus 50 --duration 10m tests/load/api_v2.js

   # Compare v1 vs v2 performance
   k6 run --vus 50 --duration 5m tests/load/api_v1.js --out json=v1_results.json
   k6 run --vus 50 --duration 5m tests/load/api_v2.js --out json=v2_results.json
   python scripts/compare_performance.py v1_results.json v2_results.json
   ```

**Implementation Checklist:**

- [ ] New API version implemented
- [ ] Deprecation headers added to old version
- [ ] API metrics tracking version usage
- [ ] Contract tests passing for v2
- [ ] Integration tests passing (v1, v2, migration)
- [ ] Performance tests show no regression
- [ ] OpenAPI spec published
- [ ] API documentation updated

### Phase 3 – Customer Communication & Migration Support

**Agent:** `customer-success-lead` manages customer migration

1. **Phased Communication Plan:**

   **T-180 days (6 months before sunset):**

   ```markdown
   Subject: Introducing API v2 - New Features & Improvements

   We're excited to announce API v2 with:
   - Improved performance (30% faster)
   - Better error messages
   - New webhook support
   - Enhanced filtering

   **Timeline:**
   - Today: v2 available, v1 enters maintenance mode
   - In 3 months: v1 marked deprecated
   - In 6 months: v1 sunset (removed)

   **Migration Guide:** https://docs.example.com/api/v2/migration

   **Questions?** Reply to this email or visit our forum.
   ```

   **T-90 days (3 months before sunset):**

   ```markdown
   Subject: ACTION REQUIRED: Migrate to API v2 by [Date]

   This is a reminder that API v1 will be deprecated in 3 months on [DATE].

   **Your Current Usage:**
   - Endpoints: /v1/users, /v1/orders
   - Request volume: 1,234 requests/day
   - Action required: Migrate to /v2/* endpoints

   **Migration Resources:**
   - [Migration Guide](...)
   - [Code Examples](...)
   - [Free Migration Workshop](...) - Register now!

   **Need Help?** Schedule 1-on-1 migration support: [Calendar Link]
   ```

   **T-30 days (1 month before sunset):**

   ```markdown
   Subject: URGENT: API v1 Sunset in 30 Days

   **FINAL NOTICE:** API v1 will be shut down on [DATE] in 30 days.

   **Your Status:**
   ❌ Still using v1 endpoints
   📊 1,234 requests/day will fail after [DATE]

   **Immediate Action Required:**
   1. Review migration guide: [Link]
   2. Update your integration
   3. Test against staging: https://api-staging.example.com/v2
   4. Deploy to production

   **Emergency Support:**
   - Email: api-emergency@example.com
   - Phone: 1-800-XXX-XXXX (24/7)
   - Live Chat: [Link]

   We're here to help you migrate successfully.
   ```

   **T-7 days (1 week before sunset):**

   ```markdown
   Subject: FINAL WARNING: API v1 Shuts Down in 7 Days

   API v1 will be PERMANENTLY DISABLED on [DATE] at [TIME UTC].

   We see you're still making requests to v1. After [DATE], these will return HTTP 410 Gone.

   **Last Chance Support:**
   - Dedicated migration engineer available today
   - Emergency migration hotline: 1-800-XXX-XXXX
   - Join emergency migration session: [Link]

   Don't let your integration break - migrate today.
   ```

1. **In-App Notifications:**

   ```python
   # Add deprecation warning to API responses
   @app.route("/v1/users", methods=["GET"])
   def get_users_v1():
       users = User.query.all()
       return {
           "data": UserV1Schema(many=True).dump(users),
           "_warning": {
               "code": "DEPRECATED_VERSION",
               "message": "API v1 is deprecated and will be removed on 2026-07-01",
               "days_until_sunset": (datetime(2026, 7, 1) - datetime.now()).days,
               "migration_guide": "https://docs.example.com/api/v2/migration",
               "support_email": "api-support@example.com",
           },
       }
   ```

1. **Usage Monitoring Dashboard:**

   ```python
   # Grafana dashboard showing v1 usage decline
   # Alerts when high-volume customers still on v1

   # Alert customers directly if still using v1 close to sunset
   def check_v1_usage_and_alert():
       sunset_date = datetime(2026, 7, 1)
       days_until_sunset = (sunset_date - datetime.now()).days

       if days_until_sunset <= 30:
           # Find customers still using v1
           customers = db.query("""
               SELECT customer_email, COUNT(*) as request_count
               FROM api_requests
               WHERE api_version = 'v1'
               AND timestamp > NOW() - INTERVAL '7 days'
               GROUP BY customer_email
               HAVING COUNT(*) > 100
           """)

           for customer in customers:
               send_urgent_migration_email(
                   email=customer["customer_email"],
                   request_count=customer["request_count"],
                   days_until_sunset=days_until_sunset,
               )
   ```

1. **Migration Support Resources:**

   - **Interactive Migration Tool:** Web UI showing side-by-side v1 vs v2 requests
   - **Code Examples:** GitHub repo with migration examples in popular languages
   - **Postman Collection:** Updated v2 collection with all endpoints
   - **Migration Workshops:** Live sessions walking through common scenarios
   - **Dedicated Support:** Engineering hours for high-value customers

**Communication Checklist:**

- [ ] Initial announcement sent (T-180 days)
- [ ] Migration guide published
- [ ] Deprecation reminder sent (T-90 days)
- [ ] Final warning sent (T-30 days)
- [ ] Emergency notice sent (T-7 days)
- [ ] In-app warnings displayed in v1 responses
- [ ] Usage monitoring dashboard created
- [ ] High-volume customers contacted personally
- [ ] Migration support resources prepared

### Phase 4 – Deprecation & Sunset

**Agent:** `release-manager` coordinates sunset

1. **Final Migration Push (T-14 days):**

   ```bash
   # Identify remaining v1 users
   psql $ANALYTICS_DB -c "\
     SELECT customer_email, api_key_id, COUNT(*) as request_count, MAX(timestamp) as last_request \
     FROM api_requests \
     WHERE api_version = 'v1' \
     AND timestamp > NOW() - INTERVAL '7 days' \
     GROUP BY customer_email, api_key_id \
     ORDER BY request_count DESC;" > /tmp/remaining_v1_users.csv

   # Personal outreach to top 10 customers
   python scripts/send_personal_migration_emails.py \
     --customer-file /tmp/remaining_v1_users.csv \
     --top-n 10 \
     --template templates/emergency_migration.html
   ```

1. **Sunset Day Checklist:**

   ```markdown
   **D-Day: [DATE]**

   **08:00 UTC - Pre-Sunset:**
   - [ ] Verify v2 healthy and stable
   - [ ] Final backup of v1 codebase
   - [ ] War room assembled
   - [ ] Customer support on high alert
   - [ ] Status page updated

   **10:00 UTC - Sunset Execution:**
   - [ ] Enable v1 read-only mode (HTTP 451)
   - [ ] Monitor error rates for 1 hour
   - [ ] Review support tickets

   **11:00 UTC - Full Shutdown:**
   - [ ] Disable v1 endpoints (HTTP 410 Gone)
   - [ ] Redirect v1 traffic to v2 (or error page)
   - [ ] Monitor customer impact

   **Post-Sunset (24 hours):**
   - [ ] Remove v1 routes from load balancer
   - [ ] Archive v1 code (don't delete yet)
   - [ ] Send post-sunset communication
   ```

1. **Sunset Implementation:**

   ```python
   # Option 1: Return HTTP 410 Gone
   @app.route("/v1/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
   def v1_sunset(path):
       return {
           "error": {
               "code": "API_VERSION_SUNSET",
               "message": "API v1 was retired on 2026-07-01",
               "migration_guide": "https://docs.example.com/api/v2/migration",
               "current_version": "v2",
               "support": "api-support@example.com",
           }
       }, 410


   # Option 2: Redirect to v2 (if semantically compatible)
   @app.route("/v1/<path:path>")
   def v1_redirect(path):
       return redirect(f"/v2/{path}", code=301)


   # Option 3: Gradual shutdown with rate limiting
   @app.route("/v1/<path:path>")
   @rate_limit("10 per day")  # Severely limit v1 usage
   def v1_limited(path):
       return {
           "warning": "API v1 is deprecated. This endpoint is rate-limited.",
           "data": handle_v1_request(path),
       }
   ```

1. **Post-Sunset Communication:**

   ```markdown
   Subject: API v1 Successfully Retired - Thank You

   Today we successfully retired API v1 after a 6-month migration period.

   **Migration Success:**
   - 98% of customers successfully migrated
   - Average migration time: 3 days
   - Zero reported data loss

   **What's Next:**
   - API v2 is now the stable version
   - v3 not planned for at least 18 months
   - We're committed to longer support windows going forward

   **For the 2% still on v1:**
   - Your requests now return HTTP 410
   - Emergency migration support: api-emergency@example.com
   - We'll work with you to migrate ASAP

   Thank you for your patience during this transition.
   ```

1. **Handle Stragglers:**

   ```python
   # Monitor 410 errors after sunset
   if days_since_sunset <= 30:
       # Be lenient with stragglers for 30 days
       # Provide emergency migration support
       # Consider temporary compatibility layer

       # Log all 410 responses
       logger.warning(
           f"v1 request after sunset from {request.headers.get('X-API-Key')}",
           extra={"endpoint": request.path, "customer_id": customer_id},
       )

       # Alert customer success team
       if request_count_today > 100:
           slack.send_message(
               channel="#api-sunset",
               message=f"Customer {customer_id} still heavily using v1 ({request_count_today} requests today)",
           )
   ```

**Sunset Checklist:**

- [ ] Final customer outreach completed (T-14 days)
- [ ] Support team briefed on sunset day procedures
- [ ] War room scheduled for sunset day
- [ ] v1 routes disabled (HTTP 410 or redirect)
- [ ] Error monitoring active for customer impact
- [ ] Post-sunset communication sent
- [ ] Straggler support plan active (30-day grace period)
- [ ] v1 code archived (not deleted)

## Rollback Procedures

### If Sunset Causes Major Issues

**Criteria for Rollback:**

- Critical customers unable to operate (>10% of revenue at risk)
- Mass customer confusion (>100 support tickets in first hour)
- Unexpected technical incompatibilities

**Rollback Steps:**

```bash
# 1. Re-enable v1 endpoints
kubectl rollout undo deployment/api-server

# 2. Update status page
curl -X POST https://statuspage.io/api/incidents \
  -d '{"message": "Temporarily re-enabled API v1 due to migration issues"}'

# 3. Communicate to customers
python scripts/send_email_blast.py \
  --template templates/v1_reenabled.html \
  --subject "API v1 Temporarily Re-enabled"

# 4. Extend sunset date
NEW_SUNSET_DATE="2026-10-01"
python scripts/update_deprecation_headers.py --sunset-date $NEW_SUNSET_DATE

# 5. Analyze what went wrong
python scripts/analyze_sunset_failures.py > /tmp/sunset_postmortem.md
```

**Post-Rollback Actions:**

- Extend timeline by 3-6 months
- Provide additional migration support
- Fix any compatibility issues discovered
- Re-communicate new sunset date

## Best Practices

### API Versioning Principles

1. **Semantic Versioning for APIs:**

   - **Major (v1 → v2):** Breaking changes
   - **Minor (v2.0 → v2.1):** Backward-compatible additions
   - **Patch (v2.1.0 → v2.1.1):** Bug fixes

1. **Minimize Breaking Changes:**

   - Add fields instead of changing types
   - Use optional parameters with defaults
   - Deprecate before removing
   - Version at API level, not per-endpoint

1. **Support N-1 Versions Minimum:**

   - Always support current + previous major version
   - Example: When v3 launches, support v3 and v2 (drop v1)

1. **Long Notice Periods:**

   - Consumer APIs: 12+ months notice
   - Internal APIs: 6+ months notice
   - Mobile apps: 18+ months (app store review delays)

1. **Monitor Actual Usage:**

   - Track version adoption rates
   - Identify blockers to migration
   - Extend timelines if needed

### Deprecation Timeline Template

| Stage | Timeline | Actions |
|-------|----------|---------|
| **Announcement** | T-180 days | New version released, announce deprecation |
| **Maintenance Mode** | T-180 to T-90 | v1 receives security fixes only, no new features |
| **Deprecated** | T-90 to T-30 | Add deprecation warnings, increase communication |
| **Final Warning** | T-30 to T-0 | Weekly reminders, personal outreach to stragglers |
| **Sunset** | T-0 | Disable old version, monitor closely |
| **Grace Period** | T+0 to T+30 | Emergency support for stragglers |
| **Archive** | T+30 | Move old version to archive, no longer accessible |

## Handoffs & Follow-Up

- Monitor API version adoption for 90 days post-sunset
- Conduct retrospective on migration process
- Update API versioning policy based on lessons learned
- Document migration patterns that worked well
- Share migration success stories with engineering team
- Plan next version timeline (minimum 18 months out)

______________________________________________________________________

**API Version Lifecycle:**

```
[Design] → [Alpha] → [Beta] → [GA] → [Maintenance] → [Deprecated] → [Sunset] → [Archived]
   │         │         │        │          │              │             │           │
   │         │         │        │          │              │             │           └─ Code preserved for reference
   │         │         │        │          │              │             └─ Endpoints return 410 Gone
   │         │         │        │          │              └─ Marked for removal, warnings added
   │         │         │        │          └─ Bug fixes only, no new features
   │         │         │        └─ Fully supported, production use
   │         │         └─ Feature complete, testing invited
   │         └─ Preview, may change
   └─ Internal only
```

**Remember:** Every breaking change breaks someone's code. Deprecate thoughtfully, communicate extensively, and provide generous timelines.
