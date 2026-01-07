import sys
from unittest.mock import patch

from src.api.dependencies import get_s3_service, get_dynamodb_service


def test_get_services_return_instances():
    s3 = get_s3_service()
    db = get_dynamodb_service()
    # types check
    assert s3 is not None
    assert db is not None
