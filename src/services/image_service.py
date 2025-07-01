
import io
import asyncio
import aiohttp
from typing import Optional, Tuple
from PIL import Image
from datetime import datetime

from ..utils.logger import get_logger

logger = get_logger(__name__)

class ImageService:
    def __init__(self, max_size: int = 10 * 1024 * 1024):
        self.max_size = max_size
    
    async def download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        if len(content) > self.max_size:
                            logger.warning(f"Image too large: {len(content)} bytes")
                            return None
                        return content
                    else:
                        logger.error(f"Failed to download image: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None
    
    def validate_image(self, image_data: bytes) -> Tuple[bool, Optional[str]]:
        """Validate image format and size."""
        try:
            if len(image_data) > self.max_size:
                return False, f"Image too large. Max size: {self.max_size // 1024 // 1024}MB"
            
            # Check if it's a valid image
            image = Image.open(io.BytesIO(image_data))
            format_name = image.format.lower() if image.format else None
            
            if format_name not in ["jpeg", "jpg", "png", "webp"]:
                return False, f"Unsupported format: {format_name}. Supported: JPEG, PNG, WebP"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error validating image: {e}")
            return False, "Invalid image file"
    
    def get_image_info(self, image_data: bytes) -> dict:
        """Get image information."""
        try:
            image = Image.open(io.BytesIO(image_data))
            return {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
                "size_bytes": len(image_data)
            }
        except Exception as e:
            logger.error(f"Error getting image info: {e}")
            return {}
    
    def resize_image(self, image_data: bytes, max_width: int = 1024, 
                    max_height: int = 1024) -> bytes:
        """Resize image while maintaining aspect ratio."""
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # Calculate new size
            ratio = min(max_width / image.width, max_height / image.height)
            if ratio < 1:
                new_width = int(image.width * ratio)
                new_height = int(image.height * ratio)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save to bytes
            output = io.BytesIO()
            image.save(output, format=image.format or 'JPEG', quality=85)
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            return image_data


