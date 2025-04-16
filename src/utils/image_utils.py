from typing import List, Tuple, Optional
from pathlib import Path
import base64
from io import BytesIO
from PIL import Image

def validate_image(image_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """
    Validates image data to ensure it's a usable image.
    
    Args:
        image_bytes: Raw image bytes to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        img.verify()
        return True, None
    except Exception as e:
        return False, str(e)

def resize_image_if_needed(image_bytes: bytes, max_size_mb: float = 5.0) -> bytes:
    """
    Resizes an image if it exceeds the maximum size limit.
    
    Args:
        image_bytes: Raw image bytes
        max_size_mb: Maximum size in MB
        
    Returns:
        Potentially resized image bytes
    """
    max_bytes = max_size_mb * 1024 * 1024
    
    if len(image_bytes) <= max_bytes:
        return image_bytes
    
    img = Image.open(BytesIO(image_bytes))
    
    # Calculate scaling factor based on size
    scale_factor = (max_bytes / len(image_bytes)) ** 0.5
    
    # Resize image
    new_width = int(img.width * scale_factor)
    new_height = int(img.height * scale_factor)
    img_resized = img.resize((new_width, new_height), Image.LANCZOS)
    
    # Save to bytes
    output = BytesIO()
    img_resized.save(output, format=img.format)
    output.seek(0)
    
    return output.getvalue()

def encode_image_to_base64(image_bytes: bytes) -> str:
    """
    Encodes image bytes to a base64 string.
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        Base64 encoded string
    """
    return base64.b64encode(image_bytes).decode("utf-8")