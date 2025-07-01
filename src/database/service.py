
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from bson import ObjectId

from .models import User, ImageRecord, TaskRecord
from ..utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseService:
    def __init__(self, mongodb_uri: str, database_name: str):
        self.client = AsyncIOMotorClient(mongodb_uri)
        self.db = self.client[database_name]
        self.users = self.db.users
        self.images = self.db.images
        self.tasks = self.db.tasks
        
    async def initialize(self):
        """Initialize database indexes."""
        try:
            # Create indexes
            await self.users.create_index("telegram_id", unique=True)
            await self.images.create_index([("user_id", 1), ("created_at", -1)])
            await self.tasks.create_index([("user_id", 1), ("created_at", -1)])
            await self.tasks.create_index("task_id", unique=True)
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def get_or_create_user(self, telegram_id: int, **kwargs) -> User:
        """Get existing user or create new one."""
        try:
            user_data = await self.users.find_one({"telegram_id": telegram_id})
            
            if user_data:
                return User(**user_data)
            
            # Create new user
            user = User(telegram_id=telegram_id, **kwargs)
            result = await self.users.insert_one(user.to_dict())
            user._id = result.inserted_id
            
            logger.info(f"Created new user: {telegram_id}")
            return user
            
        except Exception as e:
            logger.error(f"Error getting/creating user {telegram_id}: {e}")
            raise
    
    async def update_user(self, telegram_id: int, update_data: Dict[str, Any]) -> bool:
        """Update user data."""
        try:
            update_data["updated_at"] = datetime.utcnow()
            result = await self.users.update_one(
                {"telegram_id": telegram_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating user {telegram_id}: {e}")
            return False
    
    async def increment_usage_stats(self, telegram_id: int, stat_type: str):
        """Increment usage statistics for user."""
        try:
            await self.users.update_one(
                {"telegram_id": telegram_id},
                {
                    "$inc": {f"usage_stats.{stat_type}": 1},
                    "$set": {
                        "usage_stats.last_used": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        except Exception as e:
            logger.error(f"Error updating usage stats for {telegram_id}: {e}")
    
    async def save_image_record(self, image_record: ImageRecord) -> str:
        """Save image generation record."""
        try:
            result = await self.images.insert_one(image_record.to_dict())
            logger.info(f"Saved image record for user {image_record.user_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error saving image record: {e}")
            raise
    
    async def get_user_images(self, telegram_id: int, limit: int = 10) -> List[ImageRecord]:
        """Get user's recent images."""
        try:
            cursor = self.images.find(
                {"user_id": telegram_id}
            ).sort("created_at", -1).limit(limit)
            
            images = []
            async for doc in cursor:
                images.append(ImageRecord(**doc))
            
            return images
        except Exception as e:
            logger.error(f"Error getting user images for {telegram_id}: {e}")
            return []
    
    async def save_task_record(self, task_record: TaskRecord) -> str:
        """Save task record."""
        try:
            result = await self.tasks.insert_one(task_record.to_dict())
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error saving task record: {e}")
            raise
    
    async def update_task_status(self, task_id: str, status: str, 
                               result_url: Optional[str] = None, 
                               error_message: Optional[str] = None) -> bool:
        """Update task status."""
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow()
            }
            
            if result_url:
                update_data["result_url"] = result_url
            if error_message:
                update_data["error_message"] = error_message
            
            result = await self.tasks.update_one(
                {"task_id": task_id},
                {"$set": update_data}
            )
            
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating task {task_id}: {e}")
            return False
    
    async def get_task_record(self, task_id: str) -> Optional[TaskRecord]:
        """Get task record by ID."""
        try:
            doc = await self.tasks.find_one({"task_id": task_id})
            return TaskRecord(**doc) if doc else None
        except Exception as e:
            logger.error(f"Error getting task {task_id}: {e}")
            return None
    
    async def cleanup_old_tasks(self, days: int = 7):
        """Clean up old task records."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            result = await self.tasks.delete_many({
                "created_at": {"$lt": cutoff_date}
            })
            logger.info(f"Cleaned up {result.deleted_count} old task records")
        except Exception as e:
            logger.error(f"Error cleaning up old tasks: {e}")
    
    async def close(self):
        """Close database connection."""
        self.client.close()


