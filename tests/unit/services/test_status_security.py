"""Unit tests for status security and authentication services."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time as time_module
from unittest.mock import Mock, patch

import pytest

import crackerjack.services.status_authentication as status_authentication_module
from crackerjack.services.status_authentication import (
    AccessDeniedError as AuthAccessDeniedError,
)
from crackerjack.services.status_authentication import (
    AccessLevel,
    AuthCredentials,
    AuthenticationError,
    AuthenticationMethod,
    ExpiredCredentialsError,
    StatusAuthenticator,
    authenticate_status_request,
)
from crackerjack.services.status_security_manager import (
    AccessDeniedError,
    RateLimitExceededError,
    ResourceLimitExceededError,
    StatusSecurityManager,
    get_status_security_manager,
    secure_status_operation,
    validate_status_request,
)


def _make_jwt(secret_key: str, payload: dict[str, object]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}

    def encode(part: dict[str, object]) -> str:
        raw = json.dumps(part, separators=(",", ":"), sort_keys=True).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    header_part = encode(header)
    payload_part = encode(payload)
    message = f"{header_part}.{payload_part}"
    signature = base64.b64encode(
        hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).digest(),
    ).decode().rstrip("=")
    return f"{message}.{signature}"


@pytest.fixture
def auth_logger() -> Mock:
    return Mock()


@pytest.fixture
def authenticator(auth_logger: Mock) -> StatusAuthenticator:
    with patch(
        "crackerjack.services.status_authentication.get_security_logger",
        return_value=auth_logger,
    ):
        return StatusAuthenticator(secret_key="test-secret", enable_local_only=True)


@pytest.fixture
def security_logger() -> Mock:
    return Mock()


@pytest.fixture
def security_manager(security_logger: Mock) -> StatusSecurityManager:
    with patch(
        "crackerjack.services.status_security_manager.get_security_logger",
        return_value=security_logger,
    ):
        return StatusSecurityManager(
            max_concurrent_requests=1,
            rate_limit_per_minute=1,
            max_resource_usage_mb=10,
            allowed_paths=set(),
        )


@pytest.mark.unit
@pytest.mark.security
class TestAuthCredentials:
    def test_expiry_and_access_checks(self) -> None:
        expired = AuthCredentials(
            client_id="client",
            access_level=AccessLevel.PUBLIC,
            method=AuthenticationMethod.API_KEY,
            expires_at=time_module.time() - 1,
            allowed_operations={"get_basic_status"},
        )

        assert expired.is_expired is True
        assert expired.has_operation_access("get_basic_status") is True
        assert expired.has_operation_access("get_server_stats") is False


@pytest.mark.unit
@pytest.mark.security
class TestStatusAuthenticator:
    def test_default_initialization_generates_secret_and_keys(self, auth_logger: Mock) -> None:
        with patch(
            "crackerjack.services.status_authentication.get_security_logger",
            return_value=auth_logger,
        ), patch(
            "crackerjack.services.status_authentication.secrets.token_urlsafe",
            side_effect=["generated-secret", "public-rand", "internal-rand", "admin-rand"],
        ):
            authenticator = StatusAuthenticator(secret_key=None, enable_local_only=False)

        assert authenticator.secret_key == "generated-secret"
        assert len(authenticator._api_keys) == 3

    def test_local_ip_grants_admin_access(self, authenticator: StatusAuthenticator, auth_logger: Mock) -> None:
        creds = authenticator.authenticate_request(
            client_ip="127.0.0.1",
            operation="get_debug_info",
        )

        assert creds.client_id == "local"
        assert creds.access_level is AccessLevel.ADMIN
        assert creds.method is AuthenticationMethod.LOCAL_ONLY
        auth_logger.log_security_event.assert_called_once()

    def test_anonymous_request_uses_default_access_level(
        self,
        authenticator: StatusAuthenticator,
        auth_logger: Mock,
    ) -> None:
        creds = authenticator.authenticate_request(operation="get_basic_status")

        assert creds.client_id == "anonymous"
        assert creds.access_level is AccessLevel.PUBLIC
        assert creds.method is AuthenticationMethod.API_KEY
        assert auth_logger.log_security_event.call_count == 1

    def test_validate_api_key_success_and_expired(
        self,
        authenticator: StatusAuthenticator,
        auth_logger: Mock,
    ) -> None:
        active = AuthCredentials(
            client_id="client",
            access_level=AccessLevel.INTERNAL,
            method=AuthenticationMethod.API_KEY,
        )
        expired = AuthCredentials(
            client_id="expired",
            access_level=AccessLevel.INTERNAL,
            method=AuthenticationMethod.API_KEY,
            expires_at=time_module.time() - 1,
        )
        authenticator._api_keys = {"active-key": active, "expired-key": expired}

        assert authenticator._validate_api_key("active-key", "get_service_status") is active

        with pytest.raises(ExpiredCredentialsError):
            authenticator._validate_api_key("expired-key", "get_service_status")

        auth_logger.log_security_event.assert_called()

    def test_parse_auth_header_variants(self, authenticator: StatusAuthenticator) -> None:
        api_key = AuthCredentials(
            client_id="api",
            access_level=AccessLevel.INTERNAL,
            method=AuthenticationMethod.API_KEY,
        )
        authenticator._api_keys = {"api-key": api_key}

        assert authenticator._parse_auth_header("ApiKey api-key", "get_service_status") is api_key

        jwt_payload = {
            "sub": "jwt-user",
            "access_level": AccessLevel.ADMIN.value,
            "exp": time_module.time() + 60,
            "operations": ["get_server_stats"],
        }
        jwt_token = _make_jwt(authenticator.secret_key, jwt_payload)
        jwt_creds = authenticator._parse_auth_header(f"Bearer {jwt_token}", "get_server_stats")
        assert jwt_creds.client_id == "jwt-user"
        assert jwt_creds.allowed_operations == {"get_server_stats"}

        timestamp = str(time_module.time())
        message = f"client-1: get_service_status: {timestamp}"
        signature = hmac.new(
            authenticator.secret_key.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        hmac_creds = authenticator._parse_auth_header(
            f"HMAC-SHA256 client-1: {timestamp}: {signature}",
            "get_service_status",
        )
        assert hmac_creds.client_id == "client-1"
        assert hmac_creds.method is AuthenticationMethod.HMAC_SIGNATURE

        with pytest.raises(AuthenticationError):
            authenticator._parse_auth_header("invalid", "get_basic_status")

    def test_authenticate_request_rejects_invalid_header(
        self,
        authenticator: StatusAuthenticator,
    ) -> None:
        with pytest.raises(AuthenticationError):
            authenticator.authenticate_request(
                auth_header="invalid",
                operation="get_basic_status",
            )

    def test_validation_failures_cover_error_paths(
        self,
        authenticator: StatusAuthenticator,
    ) -> None:
        with pytest.raises(AuthenticationError):
            authenticator._validate_jwt_token("not-a-jwt", "get_basic_status")

        jwt_payload = {"sub": "jwt-user", "access_level": AccessLevel.PUBLIC.value}
        jwt_token = _make_jwt(authenticator.secret_key, jwt_payload)
        bad_jwt = jwt_token.rsplit(".", 1)[0] + ".tampered"
        with pytest.raises(AuthenticationError):
            authenticator._validate_jwt_token(bad_jwt, "get_basic_status")

        expired_payload = {
            "sub": "jwt-user",
            "access_level": AccessLevel.PUBLIC.value,
            "exp": time_module.time() - 10,
        }
        expired_jwt = _make_jwt(authenticator.secret_key, expired_payload)
        with pytest.raises(ExpiredCredentialsError):
            authenticator._validate_jwt_token(expired_jwt, "get_basic_status")

        with pytest.raises(AuthenticationError):
            authenticator._validate_hmac_signature("bad-format", "get_basic_status")

        expired_timestamp = time_module.time() - 1000
        expired_message = f"client-1: get_basic_status: {expired_timestamp}"
        expired_signature = hmac.new(
            authenticator.secret_key.encode(),
            expired_message.encode(),
            hashlib.sha256,
        ).hexdigest()
        with pytest.raises(ExpiredCredentialsError):
            authenticator._validate_hmac_signature(
                f"client-1: {expired_timestamp}: {expired_signature}",
                "get_basic_status",
            )

    def test_validate_credentials_and_singleton_accessor(
        self,
        authenticator: StatusAuthenticator,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        expired = AuthCredentials(
            client_id="expired",
            access_level=AccessLevel.PUBLIC,
            method=AuthenticationMethod.API_KEY,
            expires_at=time_module.time() - 1,
        )

        with pytest.raises(ExpiredCredentialsError):
            authenticator._validate_credentials(expired, "get_basic_status")

        monkeypatch.setattr(status_authentication_module, "_authenticator", None)
        first = status_authentication_module.get_status_authenticator()
        second = status_authentication_module.get_status_authenticator()
        assert first is second

    def test_operation_access_and_key_management(
        self,
        authenticator: StatusAuthenticator,
    ) -> None:
        limited = AuthCredentials(
            client_id="limited",
            access_level=AccessLevel.PUBLIC,
            method=AuthenticationMethod.API_KEY,
            allowed_operations={"get_basic_status"},
        )

        with pytest.raises(AuthAccessDeniedError):
            authenticator._check_operation_access(limited, "get_service_status")

        with pytest.raises(AuthAccessDeniedError):
            authenticator._check_operation_access(
                AuthCredentials(
                    client_id="basic",
                    access_level=AccessLevel.PUBLIC,
                    method=AuthenticationMethod.API_KEY,
                ),
                "get_server_stats",
            )

        assert authenticator.is_operation_allowed("get_basic_status", AccessLevel.PUBLIC) is True
        assert authenticator.is_operation_allowed("get_server_stats", AccessLevel.PUBLIC) is False

        api_key = authenticator.add_api_key(
            client_id="New Client",
            access_level=AccessLevel.INTERNAL,
            allowed_operations={"get_service_status"},
        )
        assert api_key in authenticator._api_keys
        status = authenticator.get_auth_status()
        assert status["api_keys"]["total"] >= 4
        assert authenticator.revoke_api_key(api_key) is True
        assert authenticator.revoke_api_key(api_key) is False

    def test_authenticate_status_request_wrapper(
        self,
        authenticator: StatusAuthenticator,
    ) -> None:
        with patch(
            "crackerjack.services.status_authentication.get_status_authenticator",
            return_value=authenticator,
        ):
            creds = asyncio.run(
                authenticate_status_request(
                    client_ip="127.0.0.1",
                    operation="get_debug_info",
                ),
            )
            assert creds.client_id == "local"


@pytest.mark.unit
@pytest.mark.security
class TestStatusSecurityManager:
    def test_validate_request_happy_path_and_status(
        self,
        security_manager: StatusSecurityManager,
    ) -> None:
        security_manager.validate_request(
            "client-1",
            "get_basic_status",
            {"path": __file__},
        )

        status = security_manager.get_security_status()
        assert status["concurrent_requests"] == 0
        assert status["rate_limit_clients"] == 1
        assert status["recent_requests_per_minute"] == 1

    def test_validate_request_rejects_concurrency_limit(
        self,
        security_manager: StatusSecurityManager,
        security_logger: Mock,
    ) -> None:
        security_manager._concurrent_requests = 1

        with pytest.raises(ResourceLimitExceededError):
            security_manager.validate_request("client-1", "get_basic_status")

        security_logger.log_security_event.assert_called_once()

    def test_validate_request_rejects_rate_limit_and_prunes_old_requests(
        self,
        security_manager: StatusSecurityManager,
        security_logger: Mock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("crackerjack.services.status_security_manager.time.time", lambda: 100.0)
        security_manager._rate_limit_tracker["client-1"] = [1.0, 99.0]

        with pytest.raises(RateLimitExceededError):
            security_manager._check_rate_limit("client-1", "get_basic_status")

        assert security_manager._rate_limit_tracker["client-1"] == [99.0]
        security_logger.log_security_event.assert_called_once()

    def test_validate_request_rejects_path_traversal(
        self,
        security_manager: StatusSecurityManager,
    ) -> None:
        with pytest.raises(AccessDeniedError):
            security_manager.validate_request(
                "client-1",
                "get_basic_status",
                {"file_path": "../etc/passwd"},
            )

    def test_validate_file_path_with_allowed_and_denied_paths(
        self,
        security_logger: Mock,
        tmp_path,
    ) -> None:
        allowed_root = tmp_path / "allowed"
        allowed_root.mkdir()
        safe_file = allowed_root / "safe.txt"
        safe_file.write_text("ok")

        with patch(
            "crackerjack.services.status_security_manager.get_security_logger",
            return_value=security_logger,
        ):
            manager = StatusSecurityManager(allowed_paths={str(allowed_root)})

        manager._validate_file_path("client-1", "get_basic_status", str(safe_file))

        with pytest.raises(AccessDeniedError):
            manager._validate_file_path("client-1", "get_basic_status", "/etc/passwd")

    def test_validate_file_path_invalid_input(
        self,
        security_logger: Mock,
    ) -> None:
        with patch(
            "crackerjack.services.status_security_manager.get_security_logger",
            return_value=security_logger,
        ):
            manager = StatusSecurityManager(allowed_paths={"/tmp"})

        with patch("crackerjack.services.status_security_manager.Path.resolve", side_effect=ValueError("bad path")):
            with pytest.raises(AccessDeniedError):
                manager._validate_file_path("client-1", "get_basic_status", "bad-path")

    @pytest.mark.asyncio
    async def test_request_lock_lifecycle_and_timeout(
        self,
        security_manager: StatusSecurityManager,
    ) -> None:
        async with await security_manager.acquire_request_lock("client-1", "get_basic_status", timeout=0.1):
            assert security_manager._concurrent_requests == 1
            assert len(security_manager._active_requests) == 1

        assert security_manager._concurrent_requests == 0
        assert not security_manager._active_requests

        security_manager._concurrent_requests = 1
        with pytest.raises(ResourceLimitExceededError):
            await security_manager.acquire_request_lock("client-1", "get_basic_status", timeout=0.0)

    @pytest.mark.asyncio
    async def test_request_lock_timeout_sleeps_when_busy(
        self,
        security_manager: StatusSecurityManager,
    ) -> None:
        security_manager.max_concurrent_requests = 0

        with pytest.raises(ResourceLimitExceededError):
            await security_manager.acquire_request_lock("client-1", "get_basic_status", timeout=0.01)

    def test_release_missing_lock_is_noop(self, security_manager: StatusSecurityManager) -> None:
        security_manager._release_request_lock("missing", "client-1", "get_basic_status")
        assert security_manager._concurrent_requests == 0

    @pytest.mark.asyncio
    async def test_async_helpers_delegate_to_manager(self, security_manager: StatusSecurityManager) -> None:
        with patch(
            "crackerjack.services.status_security_manager.get_status_security_manager",
            return_value=security_manager,
        ):
            await validate_status_request("client-1", "get_basic_status")
            lock = await secure_status_operation("client-1", "get_basic_status", timeout=0.1)
            assert lock.request_id.startswith("client-1: get_basic_status:")
            await lock.__aexit__(None, None, None)

    def test_singleton_accessor(self) -> None:
        manager = get_status_security_manager()
        assert manager is get_status_security_manager()
