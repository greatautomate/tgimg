import os
from typing import Optional
from dataclasses import dataclass

@dataclass
class Config:
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_API_URL: str = "https://api.telegram.org"
    
    # BFL API
    BFL_API_KEY: str
    BFL_BASE_URL: str = "https://api.bfl.ai"
    
    # MongoDB
    MONGODB_URI: str
    DATABASE_NAME: str = "telegram_ai_bot"
    
    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = 10
    MAX_ACTIVE_TASKS: int = 5
    
    # Image Settings
    MAX_IMAGE_SIZE: int = 10 * 1024 * 1024  # 10MB
    SUPPORTED_FORMATS: list = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Deployment
    PORT: int = 8000
    ENVIRONMENT: str = "production"
    
    def __post_init__(self):
        if self.SUPPORTED_FORMATS is None:
            self.SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'webp']

def load_config() -> Config:
    """Load configuration from environment variables."""
    return Config(
        TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        BFL_API_KEY=os.getenv("BFL_API_KEY", ""),
        MONGODB_URI=os.getenv("MONGODB_URI", ""),
        DATABASE_NAME=os.getenv("DATABASE_NAME", "telegram_ai_bot"),
        MAX_REQUESTS_PER_MINUTE=int(os.getenv("MAX_REQUESTS_PER_MINUTE", "10")),
        MAX_ACTIVE_TASKS=int(os.getenv("MAX_ACTIVE_TASKS", "5")),
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        PORT=int(os.getenv("PORT", "8000")),
        ENVIRONMENT=os.getenv("ENVIRONMENT", "production")
    )


