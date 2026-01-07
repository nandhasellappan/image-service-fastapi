import pytest
import sys
from unittest.mock import patch, MagicMock
from src.utils.helpers import (
    generate_image_id,
    get_current_timestamp,
    generate_s3_key,
    validate_file_extension,
    validate_image_content
)


class TestHelpers:
    
    def test_generate_image_id(self):
        image_id = generate_image_id()
        assert image_id.startswith('img_')
        assert len(image_id) == 16
    
    def test_generate_image_id_uniqueness(self):
        id1 = generate_image_id()
        id2 = generate_image_id()
        assert id1 != id2
    
    def test_get_current_timestamp(self):
        timestamp = get_current_timestamp()
        assert timestamp.endswith('Z')
        assert 'T' in timestamp
    
    def test_generate_s3_key(self):
        key = generate_s3_key('user123', 'img_abc', 'jpg')
        assert key == 'images/user123/img_abc.jpg'
    
    def test_validate_file_extension_valid_jpg(self):
        result = validate_file_extension('photo.jpg')
        assert result == 'jpg'
    
    def test_validate_file_extension_valid_png(self):
        result = validate_file_extension('image.png')
        assert result == 'png'
    
    def test_validate_file_extension_invalid(self):
        result = validate_file_extension('document.pdf')
        assert result is None
    
    def test_validate_file_extension_no_extension(self):
        result = validate_file_extension('noextension')
        assert result is None
    
    def test_validate_file_extension_case_insensitive(self):
        result = validate_file_extension('photo.JPG')
        assert result == 'jpg'
    
    @patch('src.utils.helpers.Image')
    def test_validate_image_content_valid_jpeg(self, mock_image):
        mock_img = MagicMock()
        mock_img.format = 'JPEG'
        mock_image.open.return_value.__enter__.return_value = mock_img
        
        jpeg_bytes = b'fake_jpeg'
        result = validate_image_content(jpeg_bytes)
        assert result == True
    
    @patch('src.utils.helpers.Image')
    def test_validate_image_content_valid_png(self, mock_image):
        mock_img = MagicMock()
        mock_img.format = 'PNG'
        mock_image.open.return_value.__enter__.return_value = mock_img
        
        png_bytes = b'fake_png'
        result = validate_image_content(png_bytes)
        assert result == True
    
    def test_validate_image_content_invalid(self):
        invalid_bytes = b'This is not an image'
        result = validate_image_content(invalid_bytes)
        assert result == False
    
    def test_validate_image_content_empty(self):
        result = validate_image_content(b'')
        assert result == False
