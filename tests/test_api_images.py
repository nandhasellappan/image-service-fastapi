import pytest
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock, PropertyMock
from fastapi import HTTPException, UploadFile, Header
from botocore.exceptions import ClientError
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from src.api.routes.images import upload_image, get_image, delete_image, list_images, s3_service, dynamodb_service, _sanitize_image_id, bulk_delete, _get_token_user, _get_api_token_from_secrets, settings
import src.api.routes.images as images_route_module
from src.models.schemas import BulkDeleteRequest
from src.config import settings

class TestImagesAPI:
    
    @pytest.mark.asyncio
    async def test_upload_image_success(self):
        """Test successful image upload."""
        # Patch at the service module level
        with patch('src.api.routes.images.s3_service') as mock_s3, \
             patch('src.api.routes.images.dynamodb_service') as mock_dynamodb:
            
            # Setup service mocks
            mock_s3.upload_file.return_value = 's3://bucket/images/test.jpg'
            mock_s3.get_presigned_url.return_value = 'https://presigned-url.com'
            mock_dynamodb.put_metadata.return_value = None
                        
            # Create upload file
            file_content = b'fake image content'
            upload_file = Mock(spec=UploadFile)
            upload_file.filename = 'test.jpg'
            upload_file.content_type = 'image/jpeg'
            upload_file.size = len(file_content)
            upload_file.read = AsyncMock(return_value=file_content)
            
            # Call function (upload_image expects a list of files and user_id form param)
            result = await upload_image([upload_file], user_id='tester', tags=None)
            
            # Assertions: API returns a list of results and a summary message
            assert result['success'] is True
            assert 'files uploaded' in result['message']
            assert isinstance(result['data'], list)
            item = result['data'][0]
            assert item['filename'] == 'test.jpg'
            assert item['content_type'] == 'image/jpeg'
            assert item['file_size'] == len(file_content)
            assert 'image_id' in item
            
            # Verify services were called
            assert mock_s3.upload_file.call_count >= 1
            assert mock_dynamodb.put_metadata.call_count == 1
            assert mock_s3.get_presigned_url.call_count >= 0
    
    @pytest.mark.asyncio
    async def test_upload_image_invalid_type(self):
        
        upload_file = Mock(spec=UploadFile)
        upload_file.filename = 'document.pdf'
        upload_file.content_type = 'application/pdf'
        
        result = await upload_image([upload_file], user_id='tester', tags=None)
        # invalid file should be reported in per-file result
        assert result['success'] is False
        assert result['data'][0]['error'] is not None
    
    @pytest.mark.asyncio
    async def test_upload_image_s3_error(self):
        """Test upload with S3 error."""
        with patch('src.api.routes.images.s3_service') as mock_s3, \
             patch('src.api.routes.images.dynamodb_service') as mock_dynamodb:
            
            # Mock S3 to raise an error
            mock_s3.upload_file.side_effect = Exception('S3 Error')
                        
            upload_file = Mock(spec=UploadFile)
            upload_file.filename = 'test.jpg'
            upload_file.content_type = 'image/jpeg'
            upload_file.size = 100
            upload_file.read = AsyncMock(return_value=b'fake image')
            
            res = await upload_image([upload_file], user_id='tester', tags=None)
            assert res['success'] is False
            assert res['data'][0]['error'] is not None
    
    @patch('src.api.routes.images.dynamodb_service')
    @patch('src.api.routes.images.s3_service')
    def test_get_image_success(self, mock_s3, mock_dynamodb):
        
        image_id = 'images/test.jpg'
        metadata = {
            'image_id': image_id,
            'filename': 'test.jpg',
            's3_url': 's3://bucket/images/test.jpg'
        }
        
        mock_dynamodb.get_metadata.return_value = metadata
        mock_s3.get_presigned_url.return_value = 'https://presigned-url.com'
        
        result = get_image(image_id)
        
        assert result['filename'] == 'test.jpg'
        assert 'presigned_url' in result
        mock_dynamodb.get_metadata.assert_called_once_with(image_id)
    
    def test_get_image_not_found(self):
        
        with patch.object(dynamodb_service, 'get_metadata', return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                get_image('nonexistent')
            
            assert exc_info.value.status_code == 404
            assert exc_info.value.detail == 'Image not found'
    
    @patch('src.api.routes.images.s3_service')
    @patch('src.api.routes.images.dynamodb_service')
    def test_delete_image_success(self, mock_dynamodb, mock_s3):
        
        image_id = 'images/test.jpg'
        
        mock_s3.file_exists.return_value = True
        mock_s3.delete_file.return_value = None
        mock_dynamodb.delete_metadata.return_value = None
        
        mock_dynamodb.get_metadata.return_value = {'image_id': image_id, 'filename': 'test.jpg', 's3_key': image_id}
        result = delete_image(image_id)
        
        assert result['message'] == 'Image deleted successfully'
        mock_s3.file_exists.assert_called_once_with(image_id)
        mock_s3.delete_file.assert_called_once_with(image_id)
        mock_dynamodb.delete_metadata.assert_called_once_with(image_id)
    
    @patch('src.api.routes.images.s3_service')
    @patch('src.api.routes.images.dynamodb_service')
    def test_delete_image_not_found(self, mock_dynamodb, mock_s3):
        mock_dynamodb.get_metadata.return_value = None
        mock_s3.file_exists.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            delete_image('nonexistent')

        assert exc_info.value.status_code == 404
    
    @patch('src.api.routes.images.s3_service')
    @patch('src.api.routes.images.dynamodb_service')
    def test_delete_image_error(self, mock_dynamodb, mock_s3):
        mock_dynamodb.get_metadata.return_value = {'image_id': 'images/test.jpg', 's3_key': 'images/test.jpg'}
        mock_s3.file_exists.return_value = True
        mock_s3.delete_file.side_effect = Exception('Delete error')

        with pytest.raises(HTTPException) as exc_info:
            delete_image('images/test.jpg')

        assert exc_info.value.status_code == 500
    
    @patch('src.api.routes.images.dynamodb_service')
    def test_list_images_success(self, mock_dynamodb):
        
        items = [
            {'image_id': 'img1', 'filename': 'test1.jpg'},
            {'image_id': 'img2', 'filename': 'test2.jpg'}
        ]
        
        # list_metadata returns a dict with 'items'
        mock_dynamodb.list_metadata.return_value = {'items': items, 'last_evaluated_key': None}
        
        result = list_images(limit=50, tags=None)
        
        assert result['count'] == 2
        assert result['images'] == items
        # ensure list_metadata was called with limit=50
        assert mock_dynamodb.list_metadata.called
        called_kwargs = mock_dynamodb.list_metadata.call_args[1]
        assert called_kwargs.get('limit') == 50
    
    @patch('src.api.routes.images.dynamodb_service')
    def test_list_images_error(self, mock_dynamodb):        
        
        mock_dynamodb.list_metadata.side_effect = Exception('DynamoDB error')
        
        with pytest.raises(HTTPException) as exc_info:
            list_images(tags=None)
        
        assert exc_info.value.status_code == 500


def test_sanitize_image_id_braced():
    assert _sanitize_image_id('{image_id=abc-123}') == 'abc-123'
    assert _sanitize_image_id('{abc-123}') == 'abc-123'
    assert _sanitize_image_id('image_id=xyz') == 'xyz'


def test_get_image_uses_sanitized_id():
    with patch('src.api.routes.images.dynamodb_service') as mock_dynamo, \
         patch('src.api.routes.images.s3_service') as mock_s3:
        mock_dynamo.get_metadata.return_value = {'image_id': 'abc-123', 'filename': 'f.jpg', 's3_key': 'k'}
        mock_s3.get_presigned_url.return_value = 'https://ex'
        res = get_image('{image_id=abc-123}')
        mock_dynamo.get_metadata.assert_called_once_with('abc-123')
        assert res['image_id'] == 'abc-123'


def test_delete_image_uses_sanitized_id():
    with patch('src.api.routes.images.dynamodb_service') as mock_dynamo, \
         patch('src.api.routes.images.s3_service') as mock_s3:
        mock_dynamo.get_metadata.return_value = {'image_id': 'del-1', 'filename': 'f.jpg', 's3_key': 'k'}
        mock_s3.file_exists.return_value = True
        mock_s3.delete_file.return_value = None
        mock_dynamo.delete_metadata.return_value = None
        res = delete_image('{del-1}')
        mock_dynamo.get_metadata.assert_called_once_with('del-1')
        assert res['message'] == 'Image deleted successfully'


def test_bulk_delete_success_and_forbidden():
    # success path
    req = BulkDeleteRequest(user_id='u1', image_ids=['i1', 'i2'])
    with patch('src.api.routes.images.dynamodb_service') as mock_dynamo, \
         patch('src.api.routes.images.s3_service') as mock_s3:
        # first two items owned by u1
        mock_dynamo.get_metadata.side_effect = [
            {'image_id': 'i1', 'user_id': 'u1', 's3_key': 'k1'},
            {'image_id': 'i2', 'user_id': 'u1', 's3_key': 'k2'},
        ]
        mock_s3.file_exists.return_value = True
        mock_s3.delete_file.return_value = None
        mock_dynamo.delete_metadata.return_value = None

        results = bulk_delete(req, current_user='u1')
        assert set(results['deleted']) == {'i1', 'i2'}

    # forbidden path
    req2 = BulkDeleteRequest(user_id='u2', image_ids=['i3'])
    with patch('src.api.routes.images.dynamodb_service') as mock_dynamo, \
         patch('src.api.routes.images.s3_service') as mock_s3:
        mock_dynamo.get_metadata.return_value = {'image_id': 'i3', 'user_id': 'someone_else', 's3_key': 'k3'}
        results = bulk_delete(req2, current_user='not_admin')
        assert results['failed'][0]['reason'] == 'forbidden'


@pytest.mark.asyncio
async def test_upload_invalid_filename():
    upload_file = Mock(spec=UploadFile)
    upload_file.filename = ''
    upload_file.content_type = 'image/jpeg'
    upload_file.read = AsyncMock(return_value=b'123')

    res = await upload_image([upload_file], user_id='u1', tags=None)
    # should return failure result for file
    assert res['data'][0]['error'] is not None


@pytest.mark.asyncio
async def test_upload_extension_not_allowed(monkeypatch):
    upload_file = Mock(spec=UploadFile)
    upload_file.filename = 'test.bmp'
    upload_file.content_type = 'image/bmp'
    upload_file.read = AsyncMock(return_value=b'123')

    monkeypatch.setattr(settings, 'allowed_extensions', {'png'})

    res = await upload_image([upload_file], user_id='u1', tags=None)
    assert 'extension' in str(res['data'][0]['error']).lower()


@pytest.mark.asyncio
async def test_upload_file_too_large(monkeypatch):
    upload_file = Mock(spec=UploadFile)
    upload_file.filename = 'large.jpg'
    upload_file.content_type = 'image/jpeg'
    # Return enough bytes to exceed the limit set below (10 bytes)
    upload_file.read = AsyncMock(return_value=b'test' * 10)

    monkeypatch.setattr('src.api.routes.images.settings.max_file_size', 10)

    from unittest.mock import patch as patchobj
    with patchobj('src.api.routes.images.s3_service') as mock_s3, patchobj('src.api.routes.images.dynamodb_service') as mock_db:
        mock_s3.upload_file.return_value = 's3://bucket/large.jpg'
        res = await upload_image([upload_file], user_id='u1', tags=None, title=None, description=None, category=None)
        # ensure upload was blocked by size check
        assert mock_s3.upload_file.call_count == 0
        assert 'exceeds' in str(res['data'][0]['error']).lower()


@pytest.mark.asyncio
async def test_upload_db_failure_rolls_back_s3():
    upload_file = Mock(spec=UploadFile)
    upload_file.filename = 'ok.jpg'
    upload_file.content_type = 'image/jpeg'
    upload_file.read = AsyncMock(return_value=b'123')

    with patch('src.api.routes.images.s3_service') as mock_s3, patch('src.api.routes.images.dynamodb_service') as mock_db:
        mock_s3.upload_file.return_value = 's3://bucket/ok.jpg'
        # simulate DB failure
        mock_db.put_metadata.side_effect = Exception('DB fail')

        res = await upload_image([upload_file], user_id='u1', tags=None)
        # ensure rollback attempted
        assert mock_s3.delete_file.called
        assert res['data'][0]['error'] is not None


def test_sanitize_image_id_none():
    assert _sanitize_image_id(None) is None
    assert _sanitize_image_id("") == ""


@pytest.mark.asyncio
async def test_upload_validations():
    # Empty user_id
    with pytest.raises(HTTPException) as exc:
        await upload_image([Mock(spec=UploadFile)], user_id="", tags=None)
    assert exc.value.status_code == 400
    assert "user_id" in exc.value.detail

    # Empty files list
    with pytest.raises(HTTPException) as exc:
        await upload_image([], user_id="u1", tags=None)
    assert exc.value.status_code == 400
    assert "At least one file" in exc.value.detail

    # Max files
    files = [Mock(spec=UploadFile) for _ in range(11)]
    with pytest.raises(HTTPException) as exc:
        await upload_image(files, user_id="u1", tags=None)
    assert exc.value.status_code == 400
    assert "Maximum" in exc.value.detail

    # Empty content (size 0)
    f = Mock(spec=UploadFile)
    f.filename = "empty.jpg"
    f.content_type = "image/jpeg"
    f.read = AsyncMock(return_value=b"")
    
    res = await upload_image([f], user_id="u1", tags=None)
    assert res['data'][0]['error'] == "Empty file"


@pytest.mark.asyncio
async def test_upload_tags_parsing():
    f = Mock(spec=UploadFile)
    f.filename = "t.jpg"
    f.content_type = "image/jpeg"
    f.read = AsyncMock(return_value=b"123")
    
    with patch('src.api.routes.images.s3_service') as s3, \
         patch('src.api.routes.images.dynamodb_service') as db:
        s3.upload_file.return_value = "s3://url"
        db.put_metadata.return_value = None
        
        await upload_image([f], user_id="u1", tags=" tag1 , tag2 ")
        
        args = db.put_metadata.call_args[0]
        assert args[1]['tags'] == ['tag1', 'tag2']


@pytest.mark.asyncio
async def test_upload_rollback_failure():
    f = Mock(spec=UploadFile)
    f.filename = "f.jpg"
    f.content_type = "image/jpeg"
    f.read = AsyncMock(return_value=b"123")
    
    with patch('src.api.routes.images.s3_service') as s3, \
         patch('src.api.routes.images.dynamodb_service') as db:
        s3.upload_file.return_value = "s3://url"
        db.put_metadata.side_effect = Exception("DB Fail")
        s3.delete_file.side_effect = Exception("S3 Delete Fail")
        
        res = await upload_image([f], user_id="u1", tags=None, title=None, description=None, category=None)
        assert res['data'][0]['error'] == "DB Fail"


@pytest.mark.asyncio
async def test_upload_outer_exception():
    with patch('src.api.routes.images.datetime') as mock_dt:
        mock_dt.utcnow.side_effect = Exception("Global Fail")
        with pytest.raises(HTTPException) as exc:
            await upload_image([Mock()], user_id="u1")
        assert exc.value.status_code == 500


def test_delete_image_s3_missing():
    with patch('src.api.routes.images.dynamodb_service') as db, \
         patch('src.api.routes.images.s3_service') as s3:
        db.get_metadata.return_value = {'image_id': 'i1', 's3_key': 'k1'}
        s3.file_exists.return_value = False
        
        with pytest.raises(HTTPException) as exc:
            delete_image('i1')
        assert exc.value.status_code == 404
        assert "S3" in exc.value.detail


def test_list_images_edge_cases():
    with patch('src.api.routes.images.dynamodb_service') as db, \
         patch('src.api.routes.images.s3_service') as s3:
        
        # Invalid JSON key
        db.list_metadata.return_value = {'items': []}
        list_images(last_evaluated_key="{invalid", tags=None)
        assert db.list_metadata.call_args[1]['exclusive_start_key'] is None
        
        # Presigned url failure
        db.list_metadata.return_value = {'items': [{'image_id': 'i1'}]}
        s3.get_presigned_url.side_effect = Exception("Sign fail")
        
        res = list_images(tags=None)
        assert 'presigned_url' not in res['images'][0]


def test_get_token_user():
    # No auth
    with pytest.raises(HTTPException) as exc:
        _get_token_user(authorization=None, x_api_key=None)
    assert exc.value.status_code == 401
    
    # Bearer
    with patch('src.api.routes.images.settings.api_token', 'secret'):
        assert _get_token_user(authorization="Bearer u1:secret", x_api_key=None) == "u1"
        
        # Invalid secret
        with pytest.raises(HTTPException):
            _get_token_user(authorization="Bearer u1:wrong", x_api_key=None)
            
        # Admin
        assert _get_token_user(authorization="Bearer secret", x_api_key=None) == "admin"
        
        # X-API-KEY
        assert _get_token_user(x_api_key="u1:secret", authorization=None) == "u1"


def test_bulk_delete_edge_cases():
    req = BulkDeleteRequest(user_id='u1', image_ids=['i1', 'i2', 'i3'])
    with patch('src.api.routes.images.dynamodb_service') as db, \
         patch('src.api.routes.images.s3_service') as s3:
        
        def get_meta_side_effect(iid):
            if iid == 'i1': return None
            if iid == 'i2': return {'image_id': 'i2', 'user_id': 'u1', 's3_key': 'k2'}
            if iid == 'i3': raise Exception("Generic")
            return None
            
        db.get_metadata.side_effect = get_meta_side_effect
        s3.file_exists.return_value = True
        s3.delete_file.side_effect = Exception("S3 Fail")
        
        res = bulk_delete(req, current_user='u1')
        
        failed_ids = {x['image_id']: x['reason'] for x in res['failed']}
        assert 'i1' in failed_ids and failed_ids['i1'] == 'not_found'
        assert 'i2' in res['deleted']
        assert 'i3' in failed_ids


def test_list_images_with_tags():
    with patch('src.api.routes.images.dynamodb_service') as db:
        db.list_metadata.return_value = {'items': []}
        list_images(tags="tag1, tag2")
        args = db.list_metadata.call_args[1]
        assert args['tags'] == ['tag1', 'tag2']


def test_list_images_valid_last_evaluated_key():
    with patch('src.api.routes.images.dynamodb_service') as db:
        db.list_metadata.return_value = {'items': []}
        valid_key = json.dumps({"image_id": "123"})
        list_images(last_evaluated_key=valid_key, tags=None)
        assert db.list_metadata.call_args[1]['exclusive_start_key'] == {"image_id": "123"}


def test_get_token_user_invalid_auth_header():
    with pytest.raises(HTTPException) as exc:
        _get_token_user(authorization="Basic user:pass", x_api_key=None)
    assert exc.value.status_code == 401


class TestSecretManagement:
    """Tests for secret retrieval and token management."""

    def setup_method(self):
        # Reset the global cache before each test
        images_route_module._API_TOKEN_CACHE = None

    def test_get_api_token_from_secrets_caching(self):
        with patch('src.api.routes.images.boto3.session.Session') as mock_session_cls:
            mock_client = Mock()
            mock_session = Mock()
            mock_session.client.return_value = mock_client
            mock_session_cls.return_value = mock_session
            
            mock_client.get_secret_value.return_value = {'SecretString': '{"api_token": "cached_token"}'}
            
            # First call
            token1 = _get_api_token_from_secrets()
            assert token1 == "cached_token"
            assert mock_client.get_secret_value.call_count == 1
            
            # Second call - should use cache and not call boto3 again
            token2 = _get_api_token_from_secrets()
            assert token2 == "cached_token"
            assert mock_client.get_secret_value.call_count == 1

    def test_get_api_token_from_secrets_parsing_variants(self):
        with patch('src.api.routes.images.boto3.session.Session') as mock_session_cls:
            mock_client = Mock()
            mock_session_cls.return_value.client.return_value = mock_client
            
            # Case 1: Valid JSON with api_token
            mock_client.get_secret_value.return_value = {'SecretString': '{"api_token": " t1 "}'}
            assert _get_api_token_from_secrets() == " t1 "
            
            # Reset cache
            images_route_module._API_TOKEN_CACHE = None
            
            # Case 2: JSON without api_token key (fallback to full string)
            mock_client.get_secret_value.return_value = {'SecretString': '{"other": "val"}'}
            assert _get_api_token_from_secrets() == '{"other": "val"}'
            
            images_route_module._API_TOKEN_CACHE = None
            
            # Case 3: Not JSON (fallback to raw string)
            mock_client.get_secret_value.return_value = {'SecretString': 'raw_secret'}
            assert _get_api_token_from_secrets() == "raw_secret"

    def test_get_api_token_from_secrets_exceptions(self):
        with patch('src.api.routes.images.boto3.session.Session') as mock_session_cls:
            mock_client = Mock()
            mock_session_cls.return_value.client.return_value = mock_client
            
            # ClientError
            mock_client.get_secret_value.side_effect = ClientError({'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Not Found'}}, 'GetSecretValue')
            with patch('src.api.routes.images.settings.api_token', 'fallback_token'):
                assert _get_api_token_from_secrets() == "fallback_token"
            
            images_route_module._API_TOKEN_CACHE = None
            
            # Generic Exception
            mock_client.get_secret_value.side_effect = Exception("Unexpected Error")
            with patch('src.api.routes.images.settings.api_token', 'fallback_token_2'):
                assert _get_api_token_from_secrets() == "fallback_token_2"

    def test_get_api_token_from_secrets_environment_branches(self):
        with patch('src.api.routes.images.boto3.session.Session') as mock_session_cls:
            mock_session = Mock()
            mock_session_cls.return_value = mock_session
            
            # Patch the settings object directly in the module to avoid import mismatches
            with patch('src.api.routes.images.settings') as mock_settings:
                mock_settings.aws_region = 'us-east-1'
                mock_settings.aws_access_key_id = 'test'
                mock_settings.aws_secret_access_key = 'test'
                mock_settings.api_token = 'fallback'

                # 1. LocalStack = True
                mock_settings.is_localstack = True
                mock_settings.endpoint_url = 'http://local-test'
                
                mock_session.client.side_effect = Exception("Stop")
                _get_api_token_from_secrets()
                
                kwargs = mock_session.client.call_args[1]
                assert kwargs.get('endpoint_url') == 'http://local-test'
                
                images_route_module._API_TOKEN_CACHE = None
                
                # 2. LocalStack = False
                mock_settings.is_localstack = False
                
                mock_session.client.side_effect = Exception("Stop")
                _get_api_token_from_secrets()
                
                kwargs = mock_session.client.call_args[1]
                assert 'endpoint_url' not in kwargs

    def test_get_token_user_missing_system_token(self):
        # Mock _get_api_token_from_secrets to return None (simulating failure + no fallback)
        with patch('src.api.routes.images._get_api_token_from_secrets', return_value=None):
            with pytest.raises(HTTPException) as exc:
                _get_token_user(authorization=None, x_api_key="user:secret")
            assert exc.value.status_code == 401
