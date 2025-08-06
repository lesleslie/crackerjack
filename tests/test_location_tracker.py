"""Tests for location tracker module."""

import json
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from crackerjack.location_tracker import (
    LocationTracker,
    start_workflow,
    capture_location,
    verify_location,
    track_movement,
    finalize_movement,
    get_current_summary,
    print_current_location
)


class TestLocationTracker:
    """Test LocationTracker functionality."""

    def test_init(self):
        """Test LocationTracker initialization."""
        tracker = LocationTracker()
        
        assert tracker.log_dir.name == "crackerjack-location-tracking"
        assert tracker.current_workflow is None
        assert tracker.location_history == []

    def test_start_workflow(self):
        """Test starting a workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = LocationTracker()
            tracker.log_dir = Path(temp_dir) / "tracking"
            tracker.log_dir.mkdir()
            
            with patch('builtins.print'):
                workflow_id = tracker.start_workflow("test_workflow")
            
            assert workflow_id.startswith("test_workflow_")
            assert tracker.current_workflow == workflow_id
            
            # Check log file was created
            log_file = tracker.log_dir / f"{workflow_id}.json"
            assert log_file.exists()
            
            with open(log_file) as f:
                data = json.load(f)
            
            assert data["workflow_name"] == "test_workflow"
            assert data["workflow_id"] == workflow_id
            assert "started_at" in data
            assert data["steps"] == []

    def test_create_default_location(self):
        """Test creating default location dictionary."""
        tracker = LocationTracker()
        location = tracker._create_default_location()
        
        expected_keys = {
            "success", "error", "app_name", "window_title", 
            "window_count", "is_iterm", "iterm_info"
        }
        assert set(location.keys()) == expected_keys
        assert location["success"] is False
        assert location["app_name"] == "Unknown"
        assert location["window_title"] == "Unknown"
        assert location["window_count"] == 0
        assert location["is_iterm"] is False
        assert location["iterm_info"] is None

    def test_create_app_info_script(self):
        """Test creating AppleScript for app information."""
        tracker = LocationTracker()
        script = tracker._create_app_info_script()
        
        assert "System Events" in script
        assert "frontmost is true" in script
        assert "name of frontApp" in script
        assert "title of front window" in script

    def test_parse_app_info_result_success(self):
        """Test parsing successful AppleScript result."""
        tracker = LocationTracker()
        location = tracker._create_default_location()
        
        result = "TestApp|Test Window|2"
        parsed = tracker._parse_app_info_result(location, result)
        
        assert parsed["app_name"] == "TestApp"
        assert parsed["window_title"] == "Test Window"
        assert parsed["window_count"] == 2
        assert parsed["is_iterm"] is False
        assert parsed["success"] is True

    def test_parse_app_info_result_iterm(self):
        """Test parsing AppleScript result for iTerm2."""
        tracker = LocationTracker()
        location = tracker._create_default_location()
        
        with patch.object(tracker, 'get_iterm_details', return_value={"success": True}):
            result = "iTerm2|Terminal|1"
            parsed = tracker._parse_app_info_result(location, result)
        
        assert parsed["app_name"] == "iTerm2"
        assert parsed["is_iterm"] is True
        assert parsed["iterm_info"] == {"success": True}

    def test_parse_app_info_result_incomplete(self):
        """Test parsing incomplete AppleScript result."""
        tracker = LocationTracker()
        location = tracker._create_default_location()
        
        result = "OnlyApp"
        parsed = tracker._parse_app_info_result(location, result)
        
        assert parsed["app_name"] == "OnlyApp"
        assert parsed["window_title"] == "Unknown"
        assert parsed["window_count"] == 0

    @patch('subprocess.run')
    def test_get_frontmost_app_info_success(self, mock_run):
        """Test getting frontmost app info successfully."""
        tracker = LocationTracker()
        location = tracker._create_default_location()
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout="TestApp|Test Window|1"
        )
        
        result = tracker._get_frontmost_app_info(location)
        
        assert result["app_name"] == "TestApp"
        assert result["success"] is True
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_get_frontmost_app_info_failure(self, mock_run):
        """Test getting frontmost app info failure."""
        tracker = LocationTracker()
        location = tracker._create_default_location()
        
        mock_run.return_value = Mock(
            returncode=1,
            stderr="AppleScript error"
        )
        
        result = tracker._get_frontmost_app_info(location)
        
        assert "AppleScript failed" in result["error"]

    @patch('subprocess.run')
    def test_get_frontmost_app_info_timeout(self, mock_run):
        """Test handling timeout in app info retrieval."""
        tracker = LocationTracker()
        location = tracker._create_default_location()
        
        mock_run.side_effect = subprocess.TimeoutExpired("osascript", 5)
        
        result = tracker._get_frontmost_app_info(location)
        
        assert result["error"] == "AppleScript timeout"

    @patch('subprocess.run')
    def test_get_iterm_details_success(self, mock_run):
        """Test getting iTerm2 details successfully."""
        tracker = LocationTracker()
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout="1|2|3|4"
        )
        
        result = tracker.get_iterm_details()
        
        assert result["success"] is True
        assert result["current_window"] == 1
        assert result["current_tab"] == 2
        assert result["total_windows"] == 3
        assert result["total_tabs"] == 4

    @patch('subprocess.run')
    def test_get_iterm_details_failure(self, mock_run):
        """Test getting iTerm2 details failure."""
        tracker = LocationTracker()
        
        mock_run.return_value = Mock(returncode=1)
        
        result = tracker.get_iterm_details()
        
        assert result is None

    @patch('subprocess.run')
    def test_get_iterm_details_exception(self, mock_run):
        """Test exception handling in iTerm2 details."""
        tracker = LocationTracker()
        
        mock_run.side_effect = Exception("Test error")
        
        result = tracker.get_iterm_details()
        
        assert result["success"] is False
        assert "Test error" in result["error"]

    def test_verify_location_capture_success(self):
        """Test successful location verification."""
        tracker = LocationTracker()
        
        location = {
            "success": True,
            "app_name": "TestApp",
            "window_title": "Test Window",
            "is_iterm": False
        }
        
        verification = tracker.verify_location_capture(location)
        
        assert verification["capture_successful"] is True
        assert verification["app_detected"] is True
        assert verification["window_detected"] is True
        assert verification["overall_success"] is True

    def test_verify_location_capture_iterm(self):
        """Test location verification with iTerm2."""
        tracker = LocationTracker()
        
        location = {
            "success": True,
            "app_name": "iTerm2",
            "window_title": "Terminal",
            "is_iterm": True,
            "iterm_info": {"success": True}
        }
        
        verification = tracker.verify_location_capture(location)
        
        assert verification["iterm_details"] is True
        assert verification["overall_success"] is True

    def test_verify_location_capture_failure(self):
        """Test failed location verification."""
        tracker = LocationTracker()
        
        location = {
            "success": False,
            "app_name": "Unknown",
            "window_title": "Unknown",
            "is_iterm": False
        }
        
        verification = tracker.verify_location_capture(location)
        
        assert verification["capture_successful"] is False
        assert verification["app_detected"] is False
        assert verification["window_detected"] is False
        assert verification["overall_success"] is False

    @patch('builtins.print')
    def test_print_location_summary_basic(self, mock_print):
        """Test printing basic location summary."""
        tracker = LocationTracker()
        
        entry = {
            "step_name": "test_step",
            "location": {
                "app_name": "TestApp",
                "window_title": "Test Window",
                "is_iterm": False,
                "error": None
            },
            "verification": {
                "overall_success": True
            }
        }
        
        tracker.print_location_summary(entry)
        
        # Verify print was called with expected content
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("LOCATION SUMMARY (test_step)" in call for call in print_calls)
        assert any("App: TestApp" in call for call in print_calls)
        assert any("Window: Test Window" in call for call in print_calls)

    @patch('builtins.print')
    def test_print_location_summary_iterm(self, mock_print):
        """Test printing location summary for iTerm2."""
        tracker = LocationTracker()
        
        entry = {
            "step_name": "iterm_step",
            "location": {
                "app_name": "iTerm2",
                "window_title": "Terminal",
                "is_iterm": True,
                "error": None,
                "iterm_info": {
                    "success": True,
                    "current_window": 1,
                    "current_tab": 2,
                    "total_windows": 3
                }
            },
            "verification": {
                "overall_success": True
            }
        }
        
        tracker.print_location_summary(entry)
        
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("iTerm Window: 1" in call for call in print_calls)
        assert any("iTerm Tab: 2" in call for call in print_calls)

    def test_log_location_entry_no_workflow(self):
        """Test logging entry when no workflow is active."""
        tracker = LocationTracker()
        entry = {"test": "data"}
        
        # Should not raise an exception
        tracker.log_location_entry(entry)

    def test_log_location_entry_with_workflow(self):
        """Test logging entry with active workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = LocationTracker()
            tracker.log_dir = Path(temp_dir)
            tracker.current_workflow = "test_workflow"
            
            entry = {"step_name": "test", "data": "value"}
            tracker.log_location_entry(entry)
            
            log_file = tracker.log_dir / "test_workflow.json"
            assert log_file.exists()
            
            with open(log_file) as f:
                data = json.load(f)
            
            assert data["steps"] == [entry]

    @patch.object(LocationTracker, 'capture_location')
    def test_verify_expected_location_not_iterm(self, mock_capture):
        """Test verifying location when not in iTerm2."""
        tracker = LocationTracker()
        
        mock_capture.return_value = {
            "location": {
                "is_iterm": False,
                "app_name": "TestApp"
            }
        }
        
        result = tracker.verify_expected_location(1, 2)
        
        assert result["success"] is False
        assert "Not in iTerm2" in result["details"]

    @patch.object(LocationTracker, 'capture_location')
    def test_verify_expected_location_success(self, mock_capture):
        """Test successful location verification."""
        tracker = LocationTracker()
        
        mock_capture.return_value = {
            "location": {
                "is_iterm": True,
                "iterm_info": {
                    "success": True,
                    "current_window": 1,
                    "current_tab": 2
                }
            }
        }
        
        result = tracker.verify_expected_location(1, 2)
        
        assert result["success"] is True
        assert result["details"] == "Location matches expected"

    @patch.object(LocationTracker, 'capture_location')
    def test_verify_expected_location_mismatch(self, mock_capture):
        """Test location verification mismatch."""
        tracker = LocationTracker()
        
        mock_capture.return_value = {
            "location": {
                "is_iterm": True,
                "iterm_info": {
                    "success": True,
                    "current_window": 2,
                    "current_tab": 3
                }
            }
        }
        
        result = tracker.verify_expected_location(1, 2)
        
        assert result["success"] is False
        assert "Location mismatch" in result["details"]

    @patch('builtins.print')
    @patch.object(LocationTracker, 'capture_location')
    def test_track_movement(self, mock_capture, mock_print):
        """Test tracking movement between locations."""
        tracker = LocationTracker()
        
        mock_capture.return_value = {"test": "before"}
        
        result = tracker.track_movement("step1", "step2", "test action")
        
        assert result["from_step"] == "step1"
        assert result["to_step"] == "step2"
        assert result["action_description"] == "test action"
        assert result["before_location"] == {"test": "before"}
        assert result["after_location"] is None
        assert result["success"] is False

    @patch('builtins.print')
    @patch.object(LocationTracker, 'capture_location')
    @patch.object(LocationTracker, 'log_location_entry')
    def test_finalize_movement(self, mock_log, mock_capture, mock_print):
        """Test finalizing movement tracking."""
        tracker = LocationTracker()
        tracker.current_workflow = "test"
        
        movement_entry = {
            "to_step": "step2",
            "before_location": {
                "location": {"app_name": "App1", "window_title": "Window1"},
                "verification": {"overall_success": True}
            }
        }
        
        mock_capture.return_value = {
            "location": {"app_name": "App2", "window_title": "Window2"},
            "verification": {"overall_success": True}
        }
        
        result = tracker.finalize_movement(movement_entry)
        
        assert result["after_location"] is not None
        assert result["verification"]["location_changed"] is True
        assert result["verification"]["both_captures_successful"] is True
        assert result["success"] is True
        mock_log.assert_called_once()

    @patch.object(LocationTracker, 'get_current_location')
    def test_get_location_summary_success(self, mock_get_location):
        """Test getting location summary successfully."""
        tracker = LocationTracker()
        
        mock_get_location.return_value = {
            "success": True,
            "app_name": "TestApp",
            "window_title": "Test Window",
            "is_iterm": False
        }
        
        summary = tracker.get_location_summary()
        
        assert "TestApp" in summary
        assert "Test Window" in summary

    @patch.object(LocationTracker, 'get_current_location')
    def test_get_location_summary_iterm(self, mock_get_location):
        """Test getting location summary for iTerm2."""
        tracker = LocationTracker()
        
        mock_get_location.return_value = {
            "success": True,
            "app_name": "iTerm2",
            "is_iterm": True,
            "iterm_info": {
                "success": True,
                "current_window": 1,
                "current_tab": 2
            }
        }
        
        summary = tracker.get_location_summary()
        
        assert "iTerm2" in summary
        assert "(W1T2)" in summary

    @patch.object(LocationTracker, 'get_current_location')
    def test_get_location_summary_failure(self, mock_get_location):
        """Test getting location summary when capture fails."""
        tracker = LocationTracker()
        
        mock_get_location.return_value = {
            "success": False,
            "error": "Test error"
        }
        
        summary = tracker.get_location_summary()
        
        assert "❌" in summary
        assert "Test error" in summary


class TestGlobalFunctions:
    """Test global convenience functions."""

    @patch('crackerjack.location_tracker._tracker')
    def test_start_workflow(self, mock_tracker):
        """Test global start_workflow function."""
        mock_tracker.start_workflow.return_value = "test_id"
        
        result = start_workflow("test")
        
        assert result == "test_id"
        mock_tracker.start_workflow.assert_called_once_with("test")

    @patch('crackerjack.location_tracker._tracker')
    def test_capture_location(self, mock_tracker):
        """Test global capture_location function."""
        mock_tracker.capture_location.return_value = {"test": "data"}
        
        result = capture_location("step")
        
        assert result == {"test": "data"}
        mock_tracker.capture_location.assert_called_once_with("step")

    @patch('crackerjack.location_tracker._tracker')
    def test_verify_location(self, mock_tracker):
        """Test global verify_location function."""
        mock_tracker.verify_expected_location.return_value = {"success": True}
        
        result = verify_location(1, 2)
        
        assert result is True
        mock_tracker.verify_expected_location.assert_called_once_with(1, 2)

    @patch('crackerjack.location_tracker._tracker')
    def test_track_movement(self, mock_tracker):
        """Test global track_movement function."""
        mock_tracker.track_movement.return_value = {"test": "data"}
        
        result = track_movement("from", "to", "action")
        
        assert result == {"test": "data"}
        mock_tracker.track_movement.assert_called_once_with("from", "to", "action")

    @patch('crackerjack.location_tracker._tracker')
    def test_finalize_movement(self, mock_tracker):
        """Test global finalize_movement function."""
        mock_tracker.finalize_movement.return_value = {"test": "data"}
        
        entry = {"test_entry": "data"}
        result = finalize_movement(entry)
        
        assert result == {"test": "data"}
        mock_tracker.finalize_movement.assert_called_once_with(entry)

    @patch('crackerjack.location_tracker._tracker')
    def test_get_current_summary(self, mock_tracker):
        """Test global get_current_summary function."""
        mock_tracker.get_location_summary.return_value = "test summary"
        
        result = get_current_summary()
        
        assert result == "test summary"
        mock_tracker.get_location_summary.assert_called_once()

    @patch('builtins.print')
    @patch('crackerjack.location_tracker.get_current_summary')
    def test_print_current_location(self, mock_summary, mock_print):
        """Test global print_current_location function."""
        mock_summary.return_value = "test location"
        
        print_current_location()
        
        mock_print.assert_called_once_with("📍 Current location: test location")


class TestIntegration:
    """Integration tests for location tracking."""

    def test_full_workflow_cycle(self):
        """Test a complete workflow cycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = LocationTracker()
            tracker.log_dir = Path(temp_dir)
            
            # Start workflow
            with patch('builtins.print'):
                workflow_id = tracker.start_workflow("integration_test")
            
            # Mock location capture
            with patch.object(tracker, 'get_current_location') as mock_location:
                mock_location.return_value = {
                    "success": True,
                    "app_name": "TestApp",
                    "window_title": "Test Window",
                    "window_count": 1,
                    "is_iterm": False,
                    "iterm_info": None,
                    "error": None
                }
                
                with patch('builtins.print'):
                    entry = tracker.capture_location("test_step")
            
            # Verify entry structure
            assert entry["step_name"] == "test_step"
            assert entry["location"]["app_name"] == "TestApp"
            assert entry["verification"]["overall_success"] is True
            
            # Check history
            assert len(tracker.location_history) == 1
            assert tracker.location_history[0] == entry
            
            # Verify log file
            log_file = tracker.log_dir / f"{workflow_id}.json"
            assert log_file.exists()
            
            with open(log_file) as f:
                data = json.load(f)
            
            assert len(data["steps"]) == 1
            assert data["steps"][0]["step_name"] == "test_step"

    def test_error_handling_robustness(self):
        """Test error handling in various scenarios."""
        tracker = LocationTracker()
        
        # Test with invalid log directory
        tracker.log_dir = Path("/invalid/path/that/does/not/exist")
        
        with patch('builtins.print'):
            # Should not crash
            tracker.log_location_entry({"test": "data"})
        
        # Test location capture with AppleScript failure
        with patch.object(tracker, '_get_frontmost_app_info') as mock_app_info:
            mock_app_info.side_effect = Exception("Test exception")
            
            location = tracker.get_current_location()
            
            assert location["success"] is False
            assert "Exception: Test exception" in location["error"]