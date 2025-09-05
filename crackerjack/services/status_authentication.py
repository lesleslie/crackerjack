"""
Status Authentication System for secure access control.

Provides authentication and authorization for status endpoints with
JWT tokens, API keys, role-based access control, and audit logging.
"""

import hashlib
import hmac
import json
import secrets
import time
import typing as t
from dataclasses import dataclass
from enum import Enum

from .security_logger import SecurityEventLevel, SecurityEventType, get_security_logger


class AccessLevel(str, Enum):
    """Access levels for status endpoints."""

    PUBLIC = "public"  # Basic system status
    INTERNAL = "internal"  # Internal service status
    ADMIN = "admin"  # Full administrative access
    DEBUG = "debug"  # Debug-level information


class AuthenticationMethod(str, Enum):
    """Supported authentication methods."""

    API_KEY = "api_key"
    JWT_TOKEN = "jwt_token"
    HMAC_SIGNATURE = "hmac_signature"
    LOCAL_ONLY = "local_only"


@dataclass
class AuthCredentials:
    """Authentication credentials for status access."""

    client_id: str
    access_level: AccessLevel
    method: AuthenticationMethod
    expires_at: float | None = None
    allowed_operations: set[str] | None = None

    @property
    def is_expired(self) -> bool:
        """Check if credentials are expired."""
        return self.expires_at is not None and time.time() > self.expires_at

    def has_operation_access(self, operation: str) -> bool:
        """Check if credentials allow specific operation."""
        return self.allowed_operations is None or operation in self.allowed_operations


class AuthenticationError(Exception):
    """Base authentication error."""

    pass


class AccessDeniedError(AuthenticationError):
    """Access denied error."""

    pass


class ExpiredCredentialsError(AuthenticationError):
    """Expired credentials error."""

    pass


class StatusAuthenticator:
    """
    Authentication system for status endpoints.

    Features:
    - Multiple authentication methods (API keys, JWT, HMAC)
    - Role-based access control
    - Time-based credential expiration
    - Operation-level permissions
    - Comprehensive audit logging
    - Local-only access mode for development
    """

    def __init__(
        self,
        secret_key: str | None = None,
        default_access_level: AccessLevel = AccessLevel.PUBLIC,
        enable_local_only: bool = True,
    ):
        """
        Initialize status authenticator.

        Args:
            secret_key: Secret key for HMAC and JWT validation
            default_access_level: Default access level for unauthenticated requests
            enable_local_only: Allow local-only access for development
        """
        self.secret_key = secret_key or self._generate_secret_key()
        self.default_access_level = default_access_level
        self.enable_local_only = enable_local_only

        self.security_logger = get_security_logger()

        # Valid API keys and their associated credentials
        self._api_keys: dict[str, AuthCredentials] = {}

        # Access level requirements for operations
        self._operation_requirements: dict[str, AccessLevel] = {
            "get_basic_status": AccessLevel.PUBLIC,
            "get_service_status": AccessLevel.INTERNAL,
            "get_comprehensive_status": AccessLevel.INTERNAL,
            "get_server_stats": AccessLevel.ADMIN,
            "get_debug_info": AccessLevel.DEBUG,
            "restart_services": AccessLevel.ADMIN,
            "clear_cache": AccessLevel.ADMIN,
        }

        # Initialize with default API keys if none exist
        self._initialize_default_keys()

    def _generate_secret_key(self) -> str:
        """Generate a secure random secret key."""
        return secrets.token_urlsafe(32)

    def _initialize_default_keys(self) -> None:
        """Initialize with default API keys for different access levels."""

        # Generate default API keys for different access levels
        default_keys = {
            AccessLevel.PUBLIC: self._generate_api_key("public_default"),
            AccessLevel.INTERNAL: self._generate_api_key("internal_default"),
            AccessLevel.ADMIN: self._generate_api_key("admin_default"),
        }

        for level, api_key in default_keys.items():
            self._api_keys[api_key] = AuthCredentials(
                client_id=f"default_{level.value}",
                access_level=level,
                method=AuthenticationMethod.API_KEY,
            )

    def _generate_api_key(self, prefix: str = "ck") -> str:
        """Generate a secure API key with prefix."""
        random_part = secrets.token_urlsafe(32)
        return f"{prefix}_{random_part}"

    def authenticate_request(
        self,
        auth_header: str | None = None,
        client_ip: str | None = None,
        operation: str = "unknown",
    ) -> AuthCredentials:
        """
        Authenticate a status request.

        Args:
            auth_header: Authorization header value
            client_ip: Client IP address
            operation: Operation being requested

        Returns:
            AuthCredentials for the authenticated request

        Raises:
            AuthenticationError: If authentication fails
            AccessDeniedError: If access is denied
        """

        # Check for local-only access (development mode)
        if self.enable_local_only and client_ip:
            if client_ip in ("127.0.0.1", "::1", "localhost"):
                self.security_logger.log_security_event(
                    event_type=SecurityEventType.LOCAL_ACCESS_GRANTED,
                    level=SecurityEventLevel.INFO,
                    message=f"Local access granted for {operation}",
                    client_id="local",
                    operation=operation,
                    additional_data={"client_ip": client_ip},
                )

                return AuthCredentials(
                    client_id="local",
                    access_level=AccessLevel.ADMIN,  # Local gets admin access
                    method=AuthenticationMethod.LOCAL_ONLY,
                )

        # Parse authentication header
        if not auth_header:
            # Return default access level for unauthenticated requests
            credentials = AuthCredentials(
                client_id="anonymous",
                access_level=self.default_access_level,
                method=AuthenticationMethod.API_KEY,
            )
        else:
            credentials = self._parse_auth_header(auth_header, operation)

        # Validate credentials
        self._validate_credentials(credentials, operation)

        # Check operation permissions
        self._check_operation_access(credentials, operation)

        # Log successful authentication
        self.security_logger.log_security_event(
            event_type=SecurityEventType.AUTH_SUCCESS,
            level=SecurityEventLevel.INFO,
            message=f"Authentication successful for {operation}",
            client_id=credentials.client_id,
            operation=operation,
            additional_data={
                "access_level": credentials.access_level.value,
                "method": credentials.method.value,
                "client_ip": client_ip,
            },
        )

        return credentials

    def _parse_auth_header(self, auth_header: str, operation: str) -> AuthCredentials:
        """Parse authentication header and create credentials."""

        try:
            # Handle different authentication schemes
            if auth_header.startswith("Bearer "):
                # JWT token
                token = auth_header[7:]  # Remove "Bearer " prefix
                return self._validate_jwt_token(token, operation)

            elif auth_header.startswith("ApiKey "):
                # API key authentication
                api_key = auth_header[7:]  # Remove "ApiKey " prefix
                return self._validate_api_key(api_key, operation)

            elif auth_header.startswith("HMAC-SHA256 "):
                # HMAC signature authentication
                signature_data = auth_header[12:]  # Remove "HMAC-SHA256 " prefix
                return self._validate_hmac_signature(signature_data, operation)

            else:
                # Try as plain API key
                return self._validate_api_key(auth_header, operation)

        except Exception as e:
            self.security_logger.log_security_event(
                event_type=SecurityEventType.AUTH_FAILURE,
                level=SecurityEventLevel.WARNING,
                message=f"Authentication parsing failed: {e}",
                operation=operation,
            )
            raise AuthenticationError(f"Invalid authentication format: {e}")

    def _validate_api_key(self, api_key: str, operation: str) -> AuthCredentials:
        """Validate API key and return credentials."""

        if api_key in self._api_keys:
            credentials = self._api_keys[api_key]

            if credentials.is_expired:
                self.security_logger.log_security_event(
                    event_type=SecurityEventType.AUTH_EXPIRED,
                    level=SecurityEventLevel.WARNING,
                    message="API key expired",
                    client_id=credentials.client_id,
                    operation=operation,
                )
                raise ExpiredCredentialsError("API key expired")

            return credentials

        self.security_logger.log_security_event(
            event_type=SecurityEventType.AUTH_FAILURE,
            level=SecurityEventLevel.WARNING,
            message="Invalid API key",
            operation=operation,
            additional_data={
                "api_key_prefix": api_key[:8] if len(api_key) > 8 else api_key
            },
        )
        raise AuthenticationError("Invalid API key")

    def _validate_jwt_token(self, token: str, operation: str) -> AuthCredentials:
        """Validate JWT token and return credentials."""

        try:
            # Simple JWT validation (in production, use proper JWT library)
            parts = token.split(".")
            if len(parts) != 3:
                raise AuthenticationError("Invalid JWT format")

            # Decode header and payload (base64)
            import base64

            json.loads(base64.b64decode(parts[0] + "=="))
            payload = json.loads(base64.b64decode(parts[1] + "=="))
            signature = parts[2]

            # Validate signature with HMAC
            expected_signature = (
                base64.b64encode(
                    hmac.new(
                        self.secret_key.encode(),
                        f"{parts[0]}.{parts[1]}".encode(),
                        hashlib.sha256,
                    ).digest()
                )
                .decode()
                .rstrip("=")
            )

            if not hmac.compare_digest(signature, expected_signature):
                raise AuthenticationError("Invalid JWT signature")

            # Check expiration
            if "exp" in payload and time.time() > payload["exp"]:
                raise ExpiredCredentialsError("JWT token expired")

            # Extract credentials
            client_id = payload.get("sub", "jwt_user")
            access_level = AccessLevel(
                payload.get("access_level", AccessLevel.PUBLIC.value)
            )
            allowed_operations = payload.get("operations")

            return AuthCredentials(
                client_id=client_id,
                access_level=access_level,
                method=AuthenticationMethod.JWT_TOKEN,
                expires_at=payload.get("exp"),
                allowed_operations=set(allowed_operations)
                if allowed_operations
                else None,
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            self.security_logger.log_security_event(
                event_type=SecurityEventType.AUTH_FAILURE,
                level=SecurityEventLevel.WARNING,
                message=f"JWT validation failed: {e}",
                operation=operation,
            )
            raise AuthenticationError(f"Invalid JWT token: {e}")

    def _validate_hmac_signature(
        self, signature_data: str, operation: str
    ) -> AuthCredentials:
        """Validate HMAC signature and return credentials."""

        try:
            # Parse signature data: client_id:timestamp:signature
            parts = signature_data.split(":")
            if len(parts) != 3:
                raise AuthenticationError("Invalid HMAC signature format")

            client_id, timestamp_str, signature = parts
            timestamp = float(timestamp_str)

            # Check timestamp (prevent replay attacks)
            current_time = time.time()
            if abs(current_time - timestamp) > 300:  # 5 minute window
                raise ExpiredCredentialsError("HMAC signature timestamp too old")

            # Create expected signature
            message = f"{client_id}:{operation}:{timestamp_str}"
            expected_signature = hmac.new(
                self.secret_key.encode(),
                message.encode(),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                raise AuthenticationError("Invalid HMAC signature")

            return AuthCredentials(
                client_id=client_id,
                access_level=AccessLevel.INTERNAL,  # HMAC gets internal access
                method=AuthenticationMethod.HMAC_SIGNATURE,
            )

        except (ValueError, IndexError) as e:
            self.security_logger.log_security_event(
                event_type=SecurityEventType.AUTH_FAILURE,
                level=SecurityEventLevel.WARNING,
                message=f"HMAC validation failed: {e}",
                operation=operation,
            )
            raise AuthenticationError(f"Invalid HMAC signature: {e}")

    def _validate_credentials(
        self, credentials: AuthCredentials, operation: str
    ) -> None:
        """Validate credentials are still valid."""

        if credentials.is_expired:
            self.security_logger.log_security_event(
                event_type=SecurityEventType.AUTH_EXPIRED,
                level=SecurityEventLevel.WARNING,
                message="Credentials expired",
                client_id=credentials.client_id,
                operation=operation,
            )
            raise ExpiredCredentialsError("Credentials expired")

    def _check_operation_access(
        self, credentials: AuthCredentials, operation: str
    ) -> None:
        """Check if credentials have access to the requested operation."""

        # Check operation-specific permissions
        if not credentials.has_operation_access(operation):
            self.security_logger.log_security_event(
                event_type=SecurityEventType.ACCESS_DENIED,
                level=SecurityEventLevel.WARNING,
                message=f"Operation not allowed: {operation}",
                client_id=credentials.client_id,
                operation=operation,
                additional_data={
                    "access_level": credentials.access_level.value,
                    "allowed_operations": list(credentials.allowed_operations or []),
                },
            )
            raise AccessDeniedError(f"Operation not allowed: {operation}")

        # Check access level requirements
        required_level = self._operation_requirements.get(operation, AccessLevel.PUBLIC)
        if not self._has_sufficient_access_level(
            credentials.access_level, required_level
        ):
            self.security_logger.log_security_event(
                event_type=SecurityEventType.INSUFFICIENT_PRIVILEGES,
                level=SecurityEventLevel.WARNING,
                message=f"Insufficient access level for {operation}",
                client_id=credentials.client_id,
                operation=operation,
                additional_data={
                    "user_level": credentials.access_level.value,
                    "required_level": required_level.value,
                },
            )
            raise AccessDeniedError(f"Insufficient access level for {operation}")

    def _has_sufficient_access_level(
        self,
        user_level: AccessLevel,
        required_level: AccessLevel,
    ) -> bool:
        """Check if user access level meets requirements."""

        # Access level hierarchy
        level_hierarchy = {
            AccessLevel.PUBLIC: 0,
            AccessLevel.INTERNAL: 1,
            AccessLevel.ADMIN: 2,
            AccessLevel.DEBUG: 3,
        }

        user_level_num = level_hierarchy.get(user_level, 0)
        required_level_num = level_hierarchy.get(required_level, 0)

        return user_level_num >= required_level_num

    def is_operation_allowed(self, operation: str, access_level: AccessLevel) -> bool:
        """Check if an operation is allowed for the given access level."""
        required_level = self._operation_requirements.get(operation, AccessLevel.PUBLIC)
        return self._has_sufficient_access_level(access_level, required_level)

    def add_api_key(
        self,
        client_id: str,
        access_level: AccessLevel,
        expires_at: float | None = None,
        allowed_operations: set[str] | None = None,
    ) -> str:
        """
        Add a new API key.

        Args:
            client_id: Client identifier
            access_level: Access level for the key
            expires_at: Optional expiration timestamp
            allowed_operations: Optional set of allowed operations

        Returns:
            Generated API key
        """

        api_key = self._generate_api_key(client_id.replace(" ", "_").lower())

        credentials = AuthCredentials(
            client_id=client_id,
            access_level=access_level,
            method=AuthenticationMethod.API_KEY,
            expires_at=expires_at,
            allowed_operations=allowed_operations,
        )

        self._api_keys[api_key] = credentials

        self.security_logger.log_security_event(
            event_type=SecurityEventType.API_KEY_CREATED,
            level=SecurityEventLevel.INFO,
            message=f"API key created for {client_id}",
            client_id=client_id,
            operation="create_api_key",
            additional_data={
                "access_level": access_level.value,
                "expires_at": expires_at,
            },
        )

        return api_key

    def revoke_api_key(self, api_key: str) -> bool:
        """
        Revoke an API key.

        Args:
            api_key: API key to revoke

        Returns:
            True if key was revoked, False if not found
        """

        if api_key in self._api_keys:
            credentials = self._api_keys[api_key]
            del self._api_keys[api_key]

            self.security_logger.log_security_event(
                event_type=SecurityEventType.API_KEY_REVOKED,
                level=SecurityEventLevel.INFO,
                message=f"API key revoked for {credentials.client_id}",
                client_id=credentials.client_id,
                operation="revoke_api_key",
            )

            return True

        return False

    def get_auth_status(self) -> dict[str, t.Any]:
        """Get current authentication system status."""

        active_keys = len([k for k, c in self._api_keys.items() if not c.is_expired])
        expired_keys = len([k for k, c in self._api_keys.items() if c.is_expired])

        return {
            "authentication_enabled": True,
            "local_only_enabled": self.enable_local_only,
            "default_access_level": self.default_access_level.value,
            "api_keys": {
                "total": len(self._api_keys),
                "active": active_keys,
                "expired": expired_keys,
            },
            "supported_methods": [method.value for method in AuthenticationMethod],
            "access_levels": [level.value for level in AccessLevel],
            "operation_requirements": {
                op: level.value for op, level in self._operation_requirements.items()
            },
        }


# Global singleton instance
_authenticator: StatusAuthenticator | None = None


def get_status_authenticator() -> StatusAuthenticator:
    """Get the global status authenticator instance."""

    global _authenticator
    if _authenticator is None:
        _authenticator = StatusAuthenticator()
    return _authenticator


async def authenticate_status_request(
    auth_header: str | None = None,
    client_ip: str | None = None,
    operation: str = "unknown",
) -> AuthCredentials:
    """
    Convenience function for status request authentication.

    Args:
        auth_header: Authorization header value
        client_ip: Client IP address
        operation: Operation being requested

    Returns:
        AuthCredentials for the authenticated request

    Raises:
        AuthenticationError: If authentication fails
    """

    return get_status_authenticator().authenticate_request(
        auth_header, client_ip, operation
    )
