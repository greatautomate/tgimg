
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from .logger import get_logger

logger = get_logger(__name__)

class RateLimiter:
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[int, List[datetime]] = defaultdict(list)
        self.active_tasks: Dict[int, int] = defaultdict(int)
        self.max_active_tasks = 5
    
    async def is_allowed(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """Check if user is allowed to make a request."""
        now = datetime.utcnow()
        
        # Clean old requests
        cutoff = now - timedelta(seconds=self.time_window)
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id] 
            if req_time > cutoff
        ]
        
        # Check rate limit
        if len(self.requests[user_id]) >= self.max_requests:
            return False, f"Rate limit exceeded. Max {self.max_requests} requests per {self.time_window} seconds."
        
        # Check active tasks
        if self.active_tasks[user_id] >= self.max_active_tasks:
            return False, f"Too many active tasks. Max {self.max_active_tasks} concurrent tasks."
        
        # Record the request
        self.requests[user_id].append(now)
        return True, None
    
    def increment_active_tasks(self, user_id: int):
        """Increment active tasks for user."""
        self.active_tasks[user_id] += 1
        logger.debug(f"Active tasks for user {user_id}: {self.active_tasks[user_id]}")
    
    def decrement_active_tasks(self, user_id: int):
        """Decrement active tasks for user."""
        if self.active_tasks[user_id] > 0:
            self.active_tasks[user_id] -= 1
        logger.debug(f"Active tasks for user {user_id}: {self.active_tasks[user_id]}")
    
    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        """Get user's current rate limit stats."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.time_window)
        
        recent_requests = len([
            req_time for req_time in self.requests[user_id] 
            if req_time > cutoff
        ])
        
        return {
            "recent_requests": recent_requests,
            "max_requests": self.max_requests,
            "active_tasks": self.active_tasks[user_id],
            "max_active_tasks": self.max_active_tasks
        }


