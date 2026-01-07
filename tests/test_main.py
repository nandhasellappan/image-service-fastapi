import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.main import app

class TestMain:
    
    def test_root_endpoint(self):
        """Test the root endpoint (Line 45)."""
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "environment" in data
        assert "version" in data

    @patch("src.main.logger")
    def test_middleware_logging(self, mock_logger):
        """Test that middleware logs requests (Lines 28-36)."""
        client = TestClient(app)
        
        # Making a request should trigger the middleware
        client.get("/")
        
        # Verify logger was called (Request start and completion)
        assert mock_logger.info.call_count >= 2

        # Verify content of logs: structured names 'request_start' and 'request_completed'
        log_messages = [call.args[0] for call in mock_logger.info.call_args_list]
        assert any(msg == 'request_start' or 'request_start' in str(msg) for msg in log_messages)
        assert any(msg == 'request_completed' or 'request_completed' in str(msg) for msg in log_messages)

    @patch("src.main.logger")
    def test_startup_shutdown_events(self, mock_logger):
        """Test startup and shutdown events (Lines 54, 59)."""
        # TestClient as context manager triggers startup and shutdown events
        with TestClient(app) as client:
            # Startup should have occurred upon entering context
            pass
        
        # Shutdown should have occurred upon exiting context
        
        log_messages = [call.args[0] for call in mock_logger.info.call_args_list]
        assert any("started - Environment" in msg for msg in log_messages)
        assert any("shutting down" in msg for msg in log_messages)