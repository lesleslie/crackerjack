______________________________________________________________________

title: Auth Implementation
owner: Developer Enablement Guild
last_reviewed: 2025-02-06
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6EEXBZT6D7K1WJN0QS3MA0N
  category: development/api

______________________________________________________________________

## Authentication Implementation

You are an authentication and security expert specializing in implementing secure authentication systems across web, mobile, and API platforms. Design and implement comprehensive authentication solutions with modern security practices.

## Context

The user needs to implement secure authentication systems including user registration, login flows, session management, multi-factor authentication, and authorization controls.

## Requirements

$ARGUMENTS

## Instructions

### 1. Authentication Architecture Design

Use Task tool with subagent_type="authentication-specialist" to design the authentication system:

Prompt: "Design authentication system for: $ARGUMENTS. Include:

1. Authentication flow design (login, registration, password recovery)
1. Session management strategy (JWT vs server-side sessions)
1. Multi-factor authentication implementation
1. OAuth/SSO integration requirements
1. Security best practices and threat mitigation"

### 2. Backend Implementation

Use Task tool with subagent_type="architecture-council" for server-side implementation:

Prompt: "Implement backend authentication for: $ARGUMENTS. Focus on:

1. User model and database schema design
1. Authentication middleware and route protection
1. Password hashing and validation
1. Token generation and validation
1. API security and rate limiting"

### 3. Frontend Integration

Use Task tool with subagent_type="frontend-developer" for client-side implementation:

Prompt: "Implement frontend authentication for: $ARGUMENTS. Include:

1. Authentication forms and validation
1. Token storage and management
1. Authentication state management
1. Route protection and redirects
1. User experience and error handling"

### 4. Authentication Implementation Patterns

**JWT-Based Authentication System**

```python
# auth_service.py
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class AuthenticationService:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire = timedelta(minutes=15)
        self.refresh_token_expire = timedelta(days=7)

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    def generate_tokens(
        self, user_id: str, user_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """Generate access and refresh tokens"""
        now = datetime.utcnow()

        # Access token payload
        access_payload = {
            "user_id": user_id,
            "email": user_data.get("email"),
            "roles": user_data.get("roles", []),
            "iat": now,
            "exp": now + self.access_token_expire,
            "type": "access",
        }

        # Refresh token payload
        refresh_payload = {
            "user_id": user_id,
            "iat": now,
            "exp": now + self.refresh_token_expire,
            "type": "refresh",
        }

        access_token = jwt.encode(
            access_payload, self.secret_key, algorithm=self.algorithm
        )
        refresh_token = jwt.encode(
            refresh_payload, self.secret_key, algorithm=self.algorithm
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": int(self.access_token_expire.total_seconds()),
        }

    def verify_token(
        self, token: str, token_type: str = "access"
    ) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Verify token type
            if payload.get("type") != token_type:
                return None

            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.utcnow().timestamp() > exp:
                return None

            return payload

        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None

    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """Generate new access token using refresh token"""
        payload = self.verify_token(refresh_token, "refresh")
        if not payload:
            return None

        # Get user data for new access token
        user_id = payload["user_id"]
        user_data = self.get_user_data(user_id)

        if not user_data:
            return None

        # Generate new access token only
        now = datetime.utcnow()
        access_payload = {
            "user_id": user_id,
            "email": user_data.get("email"),
            "roles": user_data.get("roles", []),
            "iat": now,
            "exp": now + self.access_token_expire,
            "type": "access",
        }

        access_token = jwt.encode(
            access_payload, self.secret_key, algorithm=self.algorithm
        )

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": int(self.access_token_expire.total_seconds()),
        }
```

**Multi-Factor Authentication**

```python
# mfa_service.py
import pyotp
import qrcode
from io import BytesIO
import base64
from typing import Dict, Any, Optional


class MFAService:
    def __init__(self):
        self.issuer_name = "YourApp"

    def generate_secret(self) -> str:
        """Generate TOTP secret for user"""
        return pyotp.random_base32()

    def generate_qr_code(self, user_email: str, secret: str) -> str:
        """Generate QR code for TOTP setup"""
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user_email, issuer_name=self.issuer_name
        )

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)

        # Convert to base64 image
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")

        return base64.b64encode(buffer.getvalue()).decode()

    def verify_totp(self, secret: str, token: str) -> bool:
        """Verify TOTP token"""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)

    def generate_backup_codes(self, count: int = 10) -> list[str]:
        """Generate backup codes for account recovery"""
        import secrets

        return [f"{secrets.randbelow(10**8):08d}" for _ in range(count)]

    def verify_backup_code(self, user_backup_codes: list[str], code: str) -> bool:
        """Verify backup code and remove from available codes"""
        if code in user_backup_codes:
            user_backup_codes.remove(code)
            return True
        return False
```

**OAuth Integration**

```python
# oauth_service.py
import requests
from urllib.parse import urlencode
from typing import Dict, Any, Optional


class OAuthService:
    def __init__(self, provider_config: Dict[str, str]):
        self.client_id = provider_config["client_id"]
        self.client_secret = provider_config["client_secret"]
        self.redirect_uri = provider_config["redirect_uri"]
        self.auth_url = provider_config["auth_url"]
        self.token_url = provider_config["token_url"]
        self.user_info_url = provider_config["user_info_url"]

    def get_authorization_url(self, state: str, scopes: list[str] = None) -> str:
        """Generate OAuth authorization URL"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
        }

        if scopes:
            params["scope"] = " ".join(scopes)

        return f"{self.auth_url}?{urlencode(params)}"

    def exchange_code_for_token(self, code: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access token"""
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
            "grant_type": "authorization_code",
        }

        response = requests.post(self.token_url, data=data)

        if response.status_code == 200:
            return response.json()

        return None

    def get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get user information using access token"""
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(self.user_info_url, headers=headers)

        if response.status_code == 200:
            return response.json()

        return None
```

### 5. Frontend Authentication Components

**React Authentication Hook**

```typescript
// useAuth.ts
import { useState, useEffect, useContext, createContext } from 'react';

interface User {
  id: string;
  email: string;
  roles: string[];
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  register: (email: string, password: string, userData: any) => Promise<void>;
  refreshToken: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const login = async (email: string, password: string) => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      throw new Error('Login failed');
    }

    const { access_token, refresh_token, user } = await response.json();
    
    // Store tokens securely
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    
    setUser(user);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
  };

  const refreshToken = async () => {
    const refresh_token = localStorage.getItem('refresh_token');
    if (!refresh_token) return;

    const response = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${refresh_token}`,
        'Content-Type': 'application/json',
      },
    });

    if (response.ok) {
      const { access_token } = await response.json();
      localStorage.setItem('access_token', access_token);
    } else {
      logout();
    }
  };

  // Auto-refresh token before expiration
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      // Decode token to check expiration
      const payload = JSON.parse(atob(token.split('.')[1]));
      const now = Date.now() / 1000;
      
      if (payload.exp - now < 300) { // Refresh if expires in 5 minutes
        refreshToken();
      }
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, register, refreshToken }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

**HTMX Authentication Integration**

```html
<!-- auth-components.html -->
<div id="auth-container">
  <!-- Login Form -->
  <form hx-post="/api/auth/login" 
        hx-trigger="submit"
        hx-target="#auth-result"
        hx-swap="innerHTML">
    <div>
      <label for="email">Email:</label>
      <input type="email" name="email" required>
    </div>
    <div>
      <label for="password">Password:</label>
      <input type="password" name="password" required>
    </div>
    <button type="submit">Login</button>
  </form>
  
  <div id="auth-result"></div>
</div>

<!-- Protected Content -->
<div hx-get="/api/protected/content"
     hx-trigger="load"
     hx-headers='{"Authorization": "Bearer ${getAccessToken()}"}'
     hx-swap="innerHTML">
  Loading...
</div>

<script>
function getAccessToken() {
  return localStorage.getItem('access_token');
}

// Intercept 401 responses for token refresh
document.body.addEventListener('htmx:responseError', function(evt) {
  if (evt.detail.xhr.status === 401) {
    refreshTokenAndRetry(evt.detail.requestConfig);
  }
});

async function refreshTokenAndRetry(originalConfig) {
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) {
    window.location.href = '/login';
    return;
  }

  try {
    const response = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${refreshToken}`,
        'Content-Type': 'application/json',
      },
    });

    if (response.ok) {
      const { access_token } = await response.json();
      localStorage.setItem('access_token', access_token);
      
      // Retry original request
      htmx.ajax(originalConfig.verb, originalConfig.path, {
        target: originalConfig.target,
        headers: { 'Authorization': `Bearer ${access_token}` }
      });
    } else {
      window.location.href = '/login';
    }
  } catch (error) {
    window.location.href = '/login';
  }
}
</script>
```

### 6. Security Configuration

**Rate Limiting and Security Middleware**

```python
# security_middleware.py
from flask import request, jsonify, g
from functools import wraps
import time
from collections import defaultdict


class SecurityMiddleware:
    def __init__(self):
        self.rate_limits = defaultdict(list)
        self.failed_attempts = defaultdict(int)
        self.blocked_ips = set()

    def rate_limit(self, requests_per_minute: int = 60):
        """Rate limiting decorator"""

        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                client_ip = request.remote_addr
                now = time.time()

                # Clean old entries
                minute_ago = now - 60
                self.rate_limits[client_ip] = [
                    req_time
                    for req_time in self.rate_limits[client_ip]
                    if req_time > minute_ago
                ]

                # Check rate limit
                if len(self.rate_limits[client_ip]) >= requests_per_minute:
                    return jsonify({"error": "Rate limit exceeded"}), 429

                # Record request
                self.rate_limits[client_ip].append(now)

                return f(*args, **kwargs)

            return decorated_function

        return decorator

    def require_auth(self, f):
        """Authentication required decorator"""

        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get("Authorization")

            if not auth_header or not auth_header.startswith("Bearer "):
                return jsonify({"error": "Authentication required"}), 401

            token = auth_header.split(" ")[1]
            user_data = self.auth_service.verify_token(token)

            if not user_data:
                return jsonify({"error": "Invalid token"}), 401

            g.current_user = user_data
            return f(*args, **kwargs)

        return decorated_function

    def require_roles(self, roles: list[str]):
        """Role-based authorization decorator"""

        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not hasattr(g, "current_user"):
                    return jsonify({"error": "Authentication required"}), 401

                user_roles = g.current_user.get("roles", [])
                if not any(role in user_roles for role in roles):
                    return jsonify({"error": "Insufficient permissions"}), 403

                return f(*args, **kwargs)

            return decorated_function

        return decorator
```

## Output Format

1. **Authentication Architecture**: Complete system design with flow diagrams
1. **Backend Implementation**: Server-side authentication code with security measures
1. **Frontend Integration**: Client-side authentication with state management
1. **Security Configuration**: Rate limiting, CORS, and security headers setup
1. **OAuth Integration**: Third-party authentication provider setup
1. **Multi-Factor Authentication**: TOTP and backup code implementation
1. **Database Schema**: User and authentication-related table designs
1. **API Documentation**: Authentication endpoints with request/response examples
1. **Security Best Practices**: Implementation guidelines and threat mitigation
1. **Testing Strategy**: Authentication testing approaches and test cases

Focus on creating secure, scalable authentication systems that follow modern security best practices while providing excellent user experience.

Target: $ARGUMENTS

______________________________________________________________________

## Security Considerations

### Authentication & Authorization

- **API Authentication**: Implement proper authentication (OAuth 2.0, JWT, API keys)
- **Authorization Checks**: Validate user permissions before executing operations
- **Token Management**: Secure token storage, rotation, and expiration policies

```python
# Example: Secure API authentication
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
```

### Input Validation & Sanitization

- **Validate All Inputs**: Use schema validation (Pydantic, Joi, etc.)
- **SQL Injection Prevention**: Use parameterized queries, ORM with proper escaping
- **XSS Prevention**: Sanitize user input, implement Content Security Policy

```python
# Example: Input validation with Pydantic
from pydantic import BaseModel, validator, constr


class APIRequest(BaseModel):
    email: constr(regex=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    user_id: int

    @validator("user_id")
    def validate_user_id(cls, v):
        if v <= 0:
            raise ValueError("user_id must be positive")
        return v
```

### Rate Limiting & DDoS Protection

- **Implement Rate Limiting**: Prevent abuse with per-user/IP limits
- **Request Throttling**: Protect expensive endpoints
- **CAPTCHA for Public APIs**: Prevent automated abuse

```python
# Example: Rate limiting with slowapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


@app.post("/api/expensive-operation")
@limiter.limit("5/minute")
async def expensive_operation(request: Request):
    # Protected endpoint
    pass
```

### Data Protection

- **Encrypt Sensitive Data**: Encrypt PII at rest and in transit (TLS 1.3+)
- **Secure Secrets Management**: Use vaults (see `secrets-management.md`)
- **Data Minimization**: Only collect/store necessary data

### CORS & Security Headers

- **CORS Configuration**: Restrict allowed origins, methods, headers
- **Security Headers**: Implement HSTS, X-Content-Type-Options, X-Frame-Options

```python
# Example: CORS configuration
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://trusted-domain.com"],  # Never use "*" in production
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
```

______________________________________________________________________

______________________________________________________________________

## Testing & Validation

### Unit Testing API Endpoints

```python
# pytest example for FastAPI
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_user():
    response = client.post(
        "/users", json={"email": "test@example.com", "name": "Test User"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


def test_get_user():
    # Create user first
    create_resp = client.post(
        "/users", json={"email": "test@example.com", "name": "Test"}
    )
    user_id = create_resp.json()["id"]

    # Test GET endpoint
    response = client.get(f"/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["id"] == user_id


def test_authentication_required():
    response = client.get("/protected-endpoint")
    assert response.status_code == 401
```

### Integration Testing

```python
# Test with real database
@pytest.fixture(scope="module")
def test_db():
    # Setup test database
    engine = create_engine("sqlite:///test.db")
    Base.metadata.create_all(engine)
    yield engine
    # Teardown
    Base.metadata.drop_all(engine)
    os.remove("test.db")


def test_user_workflow(test_db):
    with TestClient(app) as client:
        # Create user
        user_resp = client.post("/users", json={"email": "test@example.com"})
        user_id = user_resp.json()["id"]

        # Create order for user
        order_resp = client.post(
            f"/users/{user_id}/orders",
            json={"items": [{"product_id": 1, "quantity": 2}]},
        )
        assert order_resp.status_code == 201

        # Verify order exists
        orders = client.get(f"/users/{user_id}/orders").json()
        assert len(orders) == 1
```

### Contract Testing

```typescript
// Pact consumer test
import { Pact } from '@pact-foundation/pact';

const provider = new Pact({
  consumer: 'MyApp',
  provider: 'APIService',
});

test('get user by id', async () => {
  await provider.addInteraction({
    state: 'user 123 exists',
    uponReceiving: 'a request for user 123',
    withRequest: {
      method: 'GET',
      path: '/users/123',
    },
    willRespondWith: {
      status: 200,
      body: { id: '123', email: 'user@example.com' },
    },
  });

  const user = await userService.getUser('123');
  expect(user.id).toBe('123');
});
```

### API Schema Validation

```python
# Validate OpenAPI schema
from openapi_spec_validator import validate_spec
import yaml


def test_openapi_schema_valid():
    with open("openapi.yaml") as f:
        spec = yaml.safe_load(f)
    validate_spec(spec)  # Raises if invalid


# Test response matches schema
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: int
    email: str
    name: str


def test_response_matches_schema():
    response = client.get("/users/123")
    user = UserResponse(**response.json())  # Validates structure
    assert user.id == 123
```

### Load Testing

```python
# locust load test
from locust import HttpUser, task, between


class APIUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def get_users(self):
        self.client.get("/users")

    @task(3)  # 3x more frequent
    def create_user(self):
        self.client.post(
            "/users",
            json={"email": f"user{self.id}@example.com", "name": f"User {self.id}"},
        )


# Run: locust -f locustfile.py --users 100 --spawn-rate 10
```

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
