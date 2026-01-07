import pytest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, 'src')

from src.config import Settings


class TestConfig:
    
    def test_settings_local_environment(self):
        # Test default value when ENVIRONMENT is not set
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.environment == 'local'
        
        # Test when ENVIRONMENT is explicitly set
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}, clear=True):
            settings = Settings()
            assert settings.environment == 'development'
    
    def test_settings_localstack_endpoint(self):
        with patch.dict(os.environ, {'LOCALSTACK_ENDPOINT': 'http://localhost:4566'}, clear=True):
            settings = Settings()
            assert settings.localstack_endpoint == 'http://localhost:4566'
    
    @patch.dict(os.environ, {'ENVIRONMENT': 'local', 'LOCALSTACK_ENDPOINT': 'http://localhost:4566'})
    def test_is_localstack_true(self):
        settings = Settings()
        assert settings.is_localstack == True
    @patch.dict(os.environ, {'ENVIRONMENT': 'production'}, clear=True)
    def test_is_localstack_false(self):
        settings = Settings()
        assert settings.is_localstack == False
    
    @patch.dict(os.environ, {'ENVIRONMENT': 'local', 'LOCALSTACK_ENDPOINT': 'http://localhost:4566'})
    def test_endpoint_url_localstack(self):
        settings = Settings()
        assert settings.endpoint_url == 'http://localhost:4566'
