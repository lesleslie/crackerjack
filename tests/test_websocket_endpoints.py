"""Tests for WebSocket endpoints HTML validity."""

import re
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from crackerjack.mcp.websocket.endpoints import register_endpoints
from crackerjack.mcp.websocket.jobs import JobManager


class TestWebSocketEndpoints:
    """Test WebSocket endpoints."""

    @pytest.fixture
    def job_manager(self, tmp_path):
        """Create a JobManager instance."""
        return JobManager(tmp_path)

    @pytest.fixture
    def app_with_endpoints(self, job_manager):
        """Create FastAPI app with registered endpoints."""
        app = FastAPI()
        with TemporaryDirectory() as temp_dir:
            progress_dir = Path(temp_dir)
            register_endpoints(app, job_manager, progress_dir)
            yield app

    @pytest.fixture
    def client(self, app_with_endpoints):
        """Create test client."""
        return TestClient(app_with_endpoints)

    def test_test_endpoint_returns_valid_html(self, client):
        """Test that /test endpoint returns valid HTML."""
        response = client.get("/test")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"

        html_content = response.text

        # Check for proper HTML structure
        assert html_content.strip().startswith("<!DOCTYPE html>")
        assert "<html>" in html_content
        assert "</html>" in html_content
        assert "<head>" in html_content and "</head>" in html_content
        assert "<body>" in html_content and "</body>" in html_content

        # Verify no malformed tags with spaces
        malformed_patterns = [
            r"< !",  # < !DOCTYPE
            r"< /",  # < /html
            r"< \w",  # < html, < head, etc.
        ]

        for pattern in malformed_patterns:
            matches = re.findall(
                pattern, html_content
            )  # REGEX OK: testing HTML validation patterns
            assert not matches, f"Found malformed HTML tags: {matches}"

    def test_test_endpoint_contains_expected_elements(self, client):
        """Test that test page contains expected interactive elements."""
        response = client.get("/test")
        html_content = response.text

        # Check for key page elements
        assert "WebSocket Test Page" in html_content
        assert "Check Status" in html_content
        assert "Get Latest Job" in html_content
        assert "Test WebSocket" in html_content
        assert "checkServerStatus()" in html_content
        assert "testWebSocket()" in html_content

        # Check for proper input field
        assert 'id="testJobId"' in html_content
        assert 'value="test-123"' in html_content

    def test_monitor_endpoint_returns_valid_html(self, client):
        """Test that /monitor/{job_id} endpoint returns valid HTML."""
        response = client.get("/monitor/test-job-123")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"

        html_content = response.text

        # Check for proper HTML structure
        assert html_content.strip().startswith("<!DOCTYPE html>")
        assert "<html>" in html_content
        assert "</html>" in html_content

        # Verify job ID is embedded correctly
        assert "test-job-123" in html_content
        assert "Crackerjack Job Monitor" in html_content

    def test_monitor_endpoint_invalid_job_id(self, client):
        """Test that invalid job ID returns error page."""
        # Job IDs with special characters should be rejected
        response = client.get("/monitor/invalid@job#id")

        assert response.status_code == 400
        assert "Invalid job ID" in response.text

    def test_status_endpoint_returns_json(self, client):
        """Test that status endpoint returns JSON, not HTML."""
        response = client.get("/")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

        # Should be JSON, not HTML
        json_data = response.json()
        assert "status" in json_data
        assert isinstance(json_data, dict)

    def test_latest_job_endpoint_returns_json(self, client):
        """Test that latest job endpoint returns JSON, not HTML."""
        response = client.get("/latest")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

        # Should be JSON, not HTML
        json_data = response.json()
        assert "status" in json_data
        assert isinstance(json_data, dict)
