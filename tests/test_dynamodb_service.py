import pytest
import sys
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

sys.path.insert(0, 'src')

from src.services.dynamodb_service import DynamoDBService


class TestDynamoDBService:
    
    @pytest.fixture
    def dynamodb_service(self):
        with patch('services.dynamodb_service.boto3.resource'):
            service = DynamoDBService()
            service.table = Mock()
            return service
    
    def test_put_metadata(self, dynamodb_service):
        image_id = 'test-image-123'
        metadata = {
            'filename': 'test.jpg',
            'size': 1024,
            'content_type': 'image/jpeg'
        }
        
        dynamodb_service.table.put_item = Mock()
        
        dynamodb_service.put_metadata(image_id, metadata)
        
        dynamodb_service.table.put_item.assert_called_once()
        call_args = dynamodb_service.table.put_item.call_args[1]
        assert call_args['Item']['image_id'] == image_id
        assert 'created_at' in call_args['Item']
    
    def test_get_metadata_found(self, dynamodb_service):
        image_id = 'test-image-123'
        expected_item = {
            'image_id': image_id,
            'filename': 'test.jpg',
            'created_at': '2026-01-01T00:00:00'
        }
        
        dynamodb_service.table.get_item = Mock(return_value={'Item': expected_item})
        
        result = dynamodb_service.get_metadata(image_id)
        
        assert result == expected_item
    
    def test_get_metadata_not_found(self, dynamodb_service):
        dynamodb_service.table.get_item = Mock(return_value={})
        
        result = dynamodb_service.get_metadata('nonexistent')
        
        assert result is None

    def test_get_metadata_empty_input(self, dynamodb_service):
        # should not call DynamoDB when image_id is empty or blank
        dynamodb_service.table.get_item = Mock()
        result = dynamodb_service.get_metadata('')
        assert result is None
        assert dynamodb_service.table.get_item.call_count == 0
    
    def test_delete_metadata(self, dynamodb_service):
        image_id = 'test-image-123'
        
        dynamodb_service.table.delete_item = Mock()
        
        dynamodb_service.delete_metadata(image_id)
        
        dynamodb_service.table.delete_item.assert_called_once()
    
    def test_list_metadata(self, dynamodb_service):
        expected_items = [
            {'image_id': 'img1', 'filename': 'test1.jpg'},
            {'image_id': 'img2', 'filename': 'test2.jpg'}
        ]
        
        dynamodb_service.table.scan = Mock(return_value={'Items': expected_items})
        
        result = dynamodb_service.list_metadata(limit=50)
        
        # list_metadata now returns a dict with 'items' and optional 'last_evaluated_key'
        assert result.get('items') == expected_items
        assert result.get('last_evaluated_key') is None
        dynamodb_service.table.scan.assert_called_once_with(Limit=50)
    
    def test_list_metadata_empty(self, dynamodb_service):
        dynamodb_service.table.scan = Mock(return_value={})
        
        result = dynamodb_service.list_metadata()
        # Expect items list empty when no Items present
        assert result.get('items') == []

    def test_list_metadata_uses_gsi_query(self, dynamodb_service):
        expected_items = [{'image_id': 'i1'}]
        dynamodb_service.user_id_index_name = 'UserIdIndex'
        dynamodb_service.table.query = Mock(return_value={'Items': expected_items, 'LastEvaluatedKey': None})

        res = dynamodb_service.list_metadata(user_id='u1', limit=10)

        assert res['items'] == expected_items
        assert res['last_evaluated_key'] is None
        dynamodb_service.table.query.assert_called()

    def test_list_metadata_query_clienterror_falls_back_to_scan(self, dynamodb_service):
        dynamodb_service.user_id_index_name = 'UserIdIndex'
        dynamodb_service.table.query = Mock(side_effect=ClientError({'Error': {'Message': 'fail', 'Code': '500'}}, 'Query'))
        expected_scan_items = [{'image_id': 's1'}]
        dynamodb_service.table.scan = Mock(return_value={'Items': expected_scan_items, 'LastEvaluatedKey': None})

        res = dynamodb_service.list_metadata(user_id='u2', limit=5)

        assert res['items'] == expected_scan_items
        dynamodb_service.table.scan.assert_called()

    def test_init_detects_gsi_and_handles_describe_exception(self):
        # simulate describe_table returning a GSI with user_id
        from unittest.mock import patch
        client = Mock()
        client.describe_table.return_value = {
            'Table': {
                'GlobalSecondaryIndexes': [
                    {'IndexName': 'UserIdIndex', 'KeySchema': [{'AttributeName': 'user_id', 'KeyType': 'HASH'}]}
                ]
            }
        }

        resource_mock = Mock()
        resource_mock.Table.return_value = Mock()
        resource_mock.meta = Mock()
        resource_mock.meta.client = client

        with patch('src.services.dynamodb_service.boto3.resource', return_value=resource_mock):
            svc = DynamoDBService()
            assert svc.user_id_index_name == 'UserIdIndex'

        # simulate describe_table raising exception
        bad_client = Mock()
        bad_client.describe_table.side_effect = Exception('no describe')
        resource_bad = Mock()
        resource_bad.Table.return_value = Mock()
        resource_bad.meta = Mock()
        resource_bad.meta.client = bad_client

        with patch('src.services.dynamodb_service.boto3.resource', return_value=resource_bad):
            svc2 = DynamoDBService()
            # should not raise, just have no user_id_index_name
            assert svc2.user_id_index_name is None

    def test_put_and_delete_metadata_response_branches(self, dynamodb_service):
        # normal response with ResponseMetadata
        dynamodb_service.table.put_item = Mock(return_value={'ResponseMetadata': {'RequestId': 'r1'}})
        dynamodb_service.put_metadata('i1', {'a': 1})
        dynamodb_service.table.put_item.assert_called()

        # put_item returns an object without .get to trigger exception branch
        class NoGet:
            pass

        dynamodb_service.table.put_item = Mock(return_value=NoGet())
        # should not raise
        dynamodb_service.put_metadata('i2', {'a': 2})

        # delete_item normal path
        dynamodb_service.table.delete_item = Mock(return_value={'ResponseMetadata': {'RequestId': 'd1'}})
        dynamodb_service.delete_metadata('i1')
        dynamodb_service.table.delete_item.assert_called()

        # delete_item returns object without get to hit except branch
        dynamodb_service.table.delete_item = Mock(return_value=NoGet())
        dynamodb_service.delete_metadata('i3')

    def test_get_metadata_clienterror_raises(self, dynamodb_service):
        from botocore.exceptions import ClientError
        dynamodb_service.table.get_item = Mock(side_effect=ClientError({'Error': {'Message': 'fail'}}, 'GetItem'))
        with pytest.raises(ClientError):
            dynamodb_service.get_metadata('i-not')

    def test_list_metadata_scan_with_filters(self, dynamodb_service):
        # when no GSI and user_id absent, should scan with FilterExpression
        dynamodb_service.user_id_index_name = None
        expected = [{'image_id': 's1'}]
        dynamodb_service.table.scan = Mock(return_value={'Items': expected, 'LastEvaluatedKey': None})

        res = dynamodb_service.list_metadata(category='cat', is_public=True, filename_contains='foo', tags=['t1'], limit=5, exclusive_start_key={'image_id': 'k'})
        assert res['items'] == expected
        dynamodb_service.table.scan.assert_called()
