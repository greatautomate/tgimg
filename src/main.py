import asyncio
import signal
import sys
from datetime import datetime
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from .config import load_config
from .database.service import DatabaseService
from .services.ai_service import BFLAPIService
from .services.image_service import ImageService
from .handlers.commands import CommandHandlers
from .handlers.messages import MessageHandlers
from .utils.rate_limiter import RateLimiter
from .utils.logger import configure_logging, get_logger

# Global variables for graceful shutdown
app = None
db_service = None
logger = None

async def setup_bot():
    """Set up the Telegram bot with all handlers."""
    global app, db_service, logger
    
    # Load configuration
    config = load_config()
    
    # Configure logging
    configure_logging(config.LOG_LEVEL)
    logger = get_logger(__name__)
    
    # Validate required configuration
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is required")
        sys.exit(1)
    
    if not config.BFL_API_KEY:
        logger.error("BFL_API_KEY is required")
        sys.exit(1)
    
    if not config.MONGODB_URI:
        logger.error("MONGODB_URI is required")
        sys.exit(1)
    
    try:
        # Initialize services
        logger.info("Initializing services...")
        
        db_service = DatabaseService(config.MONGODB_URI, config.DATABASE_NAME)
        await db_service.initialize()
        
        ai_service = BFLAPIService(config)
        image_service = ImageService(config.MAX_IMAGE_SIZE)
        rate_limiter = RateLimiter(
            max_requests=config.MAX_REQUESTS_PER_MINUTE,
            time_window=60
        )
        
        # Initialize handlers
        command_handlers = CommandHandlers(db_service, ai_service, image_service, rate_limiter)
        message_handlers = MessageHandlers(command_handlers)
        
        # Create application
        app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        
        # Add command handlers
        app.add_handler(CommandHandler("start", command_handlers.start_command))
        app.add_handler(CommandHandler("generate", command_handlers.generate_command))
        app.add_handler(CommandHandler("enhance", command_handlers.enhance_command))
        app.add_handler(CommandHandler("history", command_handlers.history_command))
        app.add_handler(CommandHandler("settings", command_handlers.settings_command))
        app.add_handler(CommandHandler("help", command_handlers.help_command))
        
        # Add message handlers
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handlers.handle_text_message))
        app.add_handler(MessageHandler(filters.PHOTO, message_handlers.handle_photo_message))
        
        # Add callback query handler
        app.add_handler(CallbackQueryHandler(message_handlers.handle_callback_query))
        
        # Error handler
        app.add_error_handler(error_handler)
        
        logger.info("Bot setup completed successfully")
        return app, config
        
    except Exception as e:
        logger.error(f"Failed to setup bot: {e}")
        if db_service:
            await db_service.close()
        sys.exit(1)

async def error_handler(update, context):
    """Handle errors during bot operation."""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ An unexpected error occurred. Please try again later."
            )
        except Exception:
            pass  # Don\"t crash on error handling errors

async def cleanup():
    """Cleanup resources on shutdown."""
    global app, db_service, logger
    
    if logger:
        logger.info("Shutting down bot...")
    
    if app:
        await app.shutdown()
    
    if db_service:
        await db_service.close()
    
    if logger:
        logger.info("Shutdown completed")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    asyncio.create_task(cleanup())
    sys.exit(0)

async def run_bot():
    """Run the bot with polling."""
    global app
    
    app, config = await setup_bot()
    
    logger.info("Starting bot in polling mode...")
    await app.run_polling(drop_pending_updates=True)

def main():
    """Main entry point."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the bot
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


