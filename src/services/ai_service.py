
import asyncio
import aiohttp
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

class BFLAPIService:
    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.BFL_BASE_URL
        self.api_key = config.BFL_API_KEY
        
    async def generate_image(self, prompt: str, **kwargs) -> Tuple[str, Optional[str]]:
        """
        Generate image using BFL API.
        Returns (task_id, polling_url)
        """
        endpoint = f"{self.base_url}/v1/flux-pro-1.1"
        
        headers = {
            "accept": "application/json",
            "x-key": self.api_key,
            "content-type": "application/json"
        }
        
        payload = {
            "prompt": prompt,
            "width": kwargs.get("width", 1024),
            "height": kwargs.get("height", 1024),
            "prompt_upsampling": kwargs.get("prompt_upsampling", False),
            "seed": kwargs.get("seed"),
            "safety_tolerance": kwargs.get("safety_tolerance", 2),
            "output_format": kwargs.get("output_format", "jpeg")
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, headers=headers, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        task_id = result.get("id")
                        polling_url = result.get("polling_url")
                        
                        logger.info(f"Image generation initiated. Task ID: {task_id}")
                        return task_id, polling_url
                    
                    elif response.status == 429:
                        error_msg = "Rate limit exceeded. Please try again later."
                        logger.warning(f"Rate limit exceeded: {await response.text()}")
                        raise Exception(error_msg)
                    
                    elif response.status == 402:
                        error_msg = "Insufficient credits. Please check your BFL account."
                        logger.warning(f"Insufficient credits: {await response.text()}")
                        raise Exception(error_msg)
                    
                    else:
                        error_text = await response.text()
                        logger.error(f"API request failed: {response.status} - {error_text}")
                        raise Exception(f"API request failed: {response.status}")
                        
        except aiohttp.ClientError as e:
            logger.error(f"Network error during image generation: {e}")
            raise Exception("Network error occurred. Please try again.")
        except Exception as e:
            logger.error(f"Unexpected error during image generation: {e}")
            raise
    
    async def get_result(self, task_id: str, polling_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Get result from BFL API.
        """
        url = polling_url or f"{self.base_url}/v1/get_result"
        
        headers = {
            "accept": "application/json",
            "x-key": self.api_key
        }
        
        params = {"id": task_id}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.debug(f"Got result for task {task_id}: {result.get("status")}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to get result: {response.status} - {error_text}")
                        raise Exception(f"Failed to get result: {response.status}")
                        
        except aiohttp.ClientError as e:
            logger.error(f"Network error getting result: {e}")
            raise Exception("Network error occurred. Please try again.")
        except Exception as e:
            logger.error(f"Unexpected error getting result: {e}")
            raise
    
    async def poll_for_result(self, task_id: str, polling_url: Optional[str] = None, 
                            timeout: int = 300) -> Dict[str, Any]:
        """
        Poll for result with timeout.
        """
        start_time = datetime.utcnow()
        
        while True:
            try:
                result = await self.get_result(task_id, polling_url)
                status = result.get("status")
                
                if status == "Ready":
                    logger.info(f"Task {task_id} completed successfully")
                    return result
                
                elif status in ["Error", "Failed", "Content Moderated"]:
                    logger.warning(f"Task {task_id} failed with status: {status}")
                    return result
                
                elif status in ["Pending", "Request Moderated"]:
                    # Check timeout
                    elapsed = (datetime.utcnow() - start_time).total_seconds()
                    if elapsed > timeout:
                        logger.warning(f"Task {task_id} timed out after {timeout} seconds")
                        return {"status": "Timeout", "error": "Request timed out"}
                    
                    # Wait before next poll
                    await asyncio.sleep(2)
                    continue
                
                else:
                    logger.warning(f"Unknown status for task {task_id}: {status}")
                    return result
                    
            except Exception as e:
                logger.error(f"Error polling for result: {e}")
                return {"status": "Error", "error": str(e)}
    
    async def enhance_image(self, image_url: str, **kwargs) -> Tuple[str, Optional[str]]:
        """
        Enhance image quality using BFL API.
        Note: This would use a different endpoint for image enhancement
        """
        # This is a placeholder - you'd need to implement based on BFL's image enhancement API
        # For now, we'll use the same generation endpoint with an enhancement prompt
        
        enhancement_prompt = f"High quality, enhanced, detailed, professional photograph"
        return await self.generate_image(enhancement_prompt, **kwargs)


