"""
Utility functions for working with images.
"""
import base64
import io
from typing import Tuple, Optional
from PIL import Image


def encode_image_to_base64(image_bytes: bytes) -> str:
    """
    Encode an image as base64 string.
    
    Args:
        image_bytes: Raw bytes of the image file
        
    Returns:
        Base64 encoded string
    """
    return base64.b64encode(image_bytes).decode('utf-8')


def decode_base64_to_image(base64_string: str) -> bytes:
    """
    Decode a base64 string back to image bytes.
    
    Args:
        base64_string: Base64 encoded string
        
    Returns:
        Raw bytes of the image
    """
    return base64.b64decode(base64_string)


def validate_image(image_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """
    Validate that bytes represent a valid image.
    
    Args:
        image_bytes: Raw bytes of the image file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Try to open the image with PIL
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()  # Verify it's a valid image
        return True, None
    except Exception as e:
        return False, str(e)


def resize_image_if_needed(image_bytes: bytes, max_size_mb: float = 5.0) -> bytes:
    """
    Resize an image if it exceeds the maximum size.
    
    Args:
        image_bytes: Raw bytes of the image file
        max_size_mb: Maximum size in megabytes
        
    Returns:
        Raw bytes of the resized image (or original if no resize needed)
    """
    # Convert MB to bytes
    max_bytes = max_size_mb * 1024 * 1024
    
    # Check if resize is needed
    if len(image_bytes) <= max_bytes:
        return image_bytes
    
    # Calculate resize ratio
    ratio = (max_bytes / len(image_bytes)) ** 0.5
    
    # Open the image
    img = Image.open(io.BytesIO(image_bytes))
    
    # Calculate new dimensions
    new_width = int(img.width * ratio)
    new_height = int(img.height * ratio)
    
    # Resize the image
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Convert back to bytes
    output = io.BytesIO()
    img.save(output, format=img.format if img.format else 'JPEG', quality=85)
    output.seek(0)
    
    return output.read()


def get_image_dimensions(image_bytes: bytes) -> Tuple[int, int]:
    """
    Get the dimensions of an image.
    
    Args:
        image_bytes: Raw bytes of the image file
        
    Returns:
        Tuple of (width, height)
    """
    img = Image.open(io.BytesIO(image_bytes))
    return img.width, img.height