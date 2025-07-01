
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pymongo import MongoClient
from bson import ObjectId

@dataclass
class User:
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    preferences: Dict[str, Any] = None
    usage_stats: Dict[str, Any] = None
    created_at: datetime = None
    updated_at: datetime = None
    _id: Optional[ObjectId] = None
    
    def __post_init__(self):
        if self.preferences is None:
            self.preferences = {
                "default_style": "realistic",
                "image_quality": "high",
                "notifications": True
            }
        if self.usage_stats is None:
            self.usage_stats = {
                "total_generations": 0,
                "total_edits": 0,
                "total_enhancements": 0,
                "last_used": None
            }
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self._id:
            data["_id"] = self._id
        return data

@dataclass
class ImageRecord:
    user_id: int
    prompt: str
    image_url: str
    task_id: str
    metadata: Dict[str, Any] = None
    image_type: str = "generation"  # generation, edit, enhancement
    created_at: datetime = None
    _id: Optional[ObjectId] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self._id:
            data["_id"] = self._id
        return data

@dataclass
class TaskRecord:
    user_id: int
    task_id: str
    task_type: str
    status: str
    prompt: Optional[str] = None
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    _id: Optional[ObjectId] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self._id:
            data["_id"] = self._id
        return data


