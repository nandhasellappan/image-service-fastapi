import pytest
import sys
from src.api.routes.health import health_check


class TestHealth:
    
    def test_health_check(self):
        
        
        result = health_check()
        
        assert result['status'] == 'healthy'
        assert result['environment'] == 'local'  # From config
        assert 'service' in result
