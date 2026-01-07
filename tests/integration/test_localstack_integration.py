import pytest
import requests
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))


@pytest.mark.integration
class TestLocalStackIntegration:
    BASE_URL = "http://localhost:8000/api/v1"
    TEST_IMAGES_DIR = Path(__file__).parent.parent / "test_images"
    
    @classmethod
    def setup_class(cls):
        cls.TEST_IMAGES_DIR.mkdir(exist_ok=True)
        cls._create_test_images()
        # Check if server is running
        try:
            requests.get("http://localhost:8000/health", timeout=2)
        except requests.exceptions.ConnectionError:
            pytest.skip("Server not running on localhost:8000")
    
    @classmethod
    def _create_test_images(cls):
        # Create tea.jpg with valid JPEG header
        tea_path = cls.TEST_IMAGES_DIR / "tea.jpg"
        jpeg_header = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        with open(tea_path, 'wb') as f:
            f.write(jpeg_header + b'\x00' * 1000)
        
        # Create coffee.jpg
        coffee_path = cls.TEST_IMAGES_DIR / "coffee.jpg"
        with open(coffee_path, 'wb') as f:
            f.write(jpeg_header + b'\x00' * 2000)
            
        # Create invalid text file
        text_path = cls.TEST_IMAGES_DIR / "test.txt"
        with open(text_path, 'w') as f:
            f.write("This is not an image")
    
    def test_health_check(self):
        response = requests.get("http://localhost:8000/health")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'environment' in data
        assert 'service' in data
    
    def test_upload_image_lifecycle(self):
        """
        Test the complete lifecycle: Upload -> Get -> List -> Delete
        """
        tea_path = self.TEST_IMAGES_DIR / "tea.jpg"
        
        # 1. Upload Image
        with open(tea_path, 'rb') as f:
            # API expects 'files' as the field name for list of files
            files = [('files', ('tea.jpg', f, 'image/jpeg'))]
            # API expects 'user_id' in form data
            data = {
                'user_id': 'integration_user',
                'title': 'Integration Test Tea',
                'category': 'post',
                'is_public': True
            }
            response = requests.post(f"{self.BASE_URL}/images", files=files, data=data)
        
        assert response.status_code == 200
        resp_json = response.json()
        assert resp_json['success'] is True
        assert len(resp_json['data']) == 1
        
        uploaded_image = resp_json['data'][0]
        assert uploaded_image['filename'] == 'tea.jpg'
        assert 'image_id' in uploaded_image
        image_id = uploaded_image['image_id']
        
        # 2. Get Image Details
        get_response = requests.get(f"{self.BASE_URL}/images/{image_id}")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data['image_id'] == image_id
        assert get_data['user_id'] == 'integration_user'
        assert 'presigned_url' in get_data
        assert get_data['presigned_url'].startswith('http')
        
        # 3. List Images
        list_response = requests.get(f"{self.BASE_URL}/images", params={'user_id': 'integration_user'})
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert list_data['count'] >= 1
        assert any(img['image_id'] == image_id for img in list_data['images'])
        
        # 4. Delete Image
        del_response = requests.delete(f"{self.BASE_URL}/images/{image_id}")
        assert del_response.status_code == 200
        
        # 5. Verify Deletion
        get_response_after = requests.get(f"{self.BASE_URL}/images/{image_id}")
        assert get_response_after.status_code == 404
    
    def test_upload_invalid_file_type(self):
        """Test uploading a non-image file."""
        text_file = self.TEST_IMAGES_DIR / "test.txt"
        
        with open(text_file, 'rb') as f:
            files = [('files', ('test.txt', f, 'text/plain'))]
            data = {'user_id': 'integration_user'}
            response = requests.post(f"{self.BASE_URL}/images", files=files, data=data)
        
        # API returns 200 but with error in data for the specific file
        assert response.status_code == 200
        resp_json = response.json()
        assert resp_json['success'] is False
        assert len(resp_json['data']) == 1
        assert resp_json['data'][0]['error'] is not None
    
    def test_upload_missing_required_fields(self):
        """Test upload without user_id."""
        tea_path = self.TEST_IMAGES_DIR / "tea.jpg"
        
        with open(tea_path, 'rb') as f:
            files = [('files', ('tea.jpg', f, 'image/jpeg'))]
            # Missing user_id
            response = requests.post(f"{self.BASE_URL}/images", files=files)
        
        # FastAPI returns 422 for missing required form fields
        assert response.status_code == 422
