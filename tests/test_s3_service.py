import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

sys.path.insert(0, 'src')

from src.services.s3_service import S3Service


class TestS3Service:
    
    @pytest.fixture
    def s3_service(self):
        with patch('services.s3_service.boto3.client'):
            service = S3Service()
            service.client = Mock()
            service.bucket_name = 'test-bucket'
            return service
    
    def test_upload_file_success(self, s3_service):
        file_content = b'test image content'
        file_key = 'images/test.jpg'
        content_type = 'image/jpeg'
        
        s3_service.client.put_object = Mock()
        
        result = s3_service.upload_file(file_key, file_content, content_type)
        
        assert result == f's3://test-bucket/{file_key}'
        s3_service.client.put_object.assert_called_once_with(
            Bucket='test-bucket',
            Key=file_key,
            Body=file_content,
            ContentType=content_type
        )
    
    def test_get_presigned_url(self, s3_service):
        file_key = 'images/test.jpg'
        expected_url = 'https://test-bucket.s3.amazonaws.com/test.jpg?signature=123'
        
        s3_service.client.generate_presigned_url = Mock(return_value=expected_url)
        
        result = s3_service.get_presigned_url(file_key)
        
        assert result == expected_url
        s3_service.client.generate_presigned_url.assert_called_once()
    
    def test_get_presigned_url_custom_expiration(self, s3_service):
        file_key = 'images/test.jpg'
        expiration = 7200
        
        s3_service.client.generate_presigned_url = Mock(return_value='url')
        
        s3_service.get_presigned_url(file_key, expiration)
        
        call_args = s3_service.client.generate_presigned_url.call_args
        assert call_args[1]['ExpiresIn'] == 7200
    
    def test_delete_file(self, s3_service):
        file_key = 'images/test.jpg'
        
        s3_service.client.delete_object = Mock()
        
        s3_service.delete_file(file_key)
        
        s3_service.client.delete_object.assert_called_once_with(
            Bucket='test-bucket',
            Key=file_key
        )
    
    def test_file_exists_true(self, s3_service):
        file_key = 'images/test.jpg'
        
        s3_service.client.head_object = Mock()
        
        result = s3_service.file_exists(file_key)
        
        assert result == True
    
    def test_file_exists_false(self, s3_service):
        file_key = 'images/nonexistent.jpg'
        
        s3_service.client.head_object = Mock(side_effect=Exception())
        
        result = s3_service.file_exists(file_key)
        
        assert result == False
