
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ..database.service import DatabaseService
from ..services.ai_service import BFLAPIService
from ..services.image_service import ImageService
from ..utils.rate_limiter import RateLimiter
from ..utils.logger import get_logger
from ..database.models import TaskRecord, ImageRecord

logger = get_logger(__name__)

class CommandHandlers:
    def __init__(self, db_service: DatabaseService, ai_service: BFLAPIService, 
                 image_service: ImageService, rate_limiter: RateLimiter):
        self.db = db_service
        self.ai = ai_service
        self.image_service = image_service
        self.rate_limiter = rate_limiter
        self.pending_tasks = {}
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        
        try:
            # Create or get user
            await self.db.get_or_create_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            
            welcome_text = """
🎨 **Welcome to AI Image Generator Bot!**

I can help you create amazing images using AI. Here's what I can do:

**Commands:**
• `/generate <prompt>` - Generate images from text
• `/enhance` - Enhance image quality (reply to image)
• `/history` - View your recent generations
• `/settings` - Manage your preferences
• `/help` - Show this help message

**Quick Start:**
Just send me a message like: `/generate a beautiful sunset over mountains`

Or send me an image and I'll help you edit it!

Let's create something amazing! ✨
            """
            
            keyboard = [
                [InlineKeyboardButton("🎨 Generate Image", callback_data="quick_generate")],
                [InlineKeyboardButton("📖 Help", callback_data="help"),
                 InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                welcome_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await update.message.reply_text(
                "Sorry, something went wrong. Please try again later."
            )
    
    async def generate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /generate command."""
        user = update.effective_user
        
        # Check if prompt is provided
        if not context.args:
            await update.message.reply_text(
                "Please provide a prompt!\n\n"
                "Example: `/generate a beautiful sunset over mountains`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        prompt = " ".join(context.args)
        
        # Rate limiting
        allowed, error_msg = await self.rate_limiter.is_allowed(user.id)
        if not allowed:
            await update.message.reply_text(f"⚠️ {error_msg}")
            return
        
        try:
            # Send initial message
            status_message = await update.message.reply_text(
                "🎨 **Generating your image...**\n\n"
                f"**Prompt:** {prompt}\n"
                "⏳ This may take a few moments...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Increment active tasks
            self.rate_limiter.increment_active_tasks(user.id)
            
            # Start generation in background
            task = asyncio.create_task(
                self._generate_image_task(user.id, prompt, status_message, update)
            )
            
            # Store task reference
            self.pending_tasks[user.id] = task
            
        except Exception as e:
            logger.error(f"Error in generate command: {e}")
            await update.message.reply_text(
                "❌ Sorry, something went wrong. Please try again later."
            )
    
    async def _generate_image_task(self, user_id: int, prompt: str, 
                                 status_message, update: Update):
        """Background task for image generation."""
        try:
            # Get user preferences
            user = await self.db.get_or_create_user(user_id)
            
            # Start generation
            task_id, polling_url = await self.ai.generate_image(
                prompt=prompt,
                width=1024,
                height=1024
            )
            
            # Save task record
            task_record = TaskRecord(
                user_id=user_id,
                task_id=task_id,
                task_type="generation",
                status="Pending",
                prompt=prompt
            )
            await self.db.save_task_record(task_record)
            
            # Update status message
            await status_message.edit_text(
                "🎨 **Generating your image...**\n\n"
                f"**Prompt:** {prompt}\n"
                "🔄 Processing... Please wait...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Poll for result
            result = await self.ai.poll_for_result(task_id, polling_url, timeout=300)
            status = result.get("status")
            
            if status == "Ready":
                # Get image URL
                image_url = result.get("result", {}).get("sample")
                
                if image_url:
                    # Update task status
                    await self.db.update_task_status(task_id, "Ready", image_url)
                    
                    # Save image record
                    image_record = ImageRecord(
                        user_id=user_id,
                        prompt=prompt,
                        image_url=image_url,
                        task_id=task_id,
                        metadata={"width": 1024, "height": 1024}
                    )
                    await self.db.save_image_record(image_record)
                    
                    # Update usage stats
                    await self.db.increment_usage_stats(user_id, "total_generations")
                    
                    # Send final message with image
                    keyboard = [
                        [InlineKeyboardButton("🔄 Generate Again", callback_data=f"regenerate:{prompt}")],
                        [InlineKeyboardButton("✨ Enhance", callback_data=f"enhance:{task_id}"),
                         InlineKeyboardButton("📝 Edit", callback_data=f"edit:{task_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await status_message.delete()
                    await update.effective_chat.send_photo(
                        photo=image_url,
                        caption=f"🎨 **Generated Image**\n\n**Prompt:** {prompt}",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=reply_markup
                    )
                else:
                    await status_message.edit_text(
                        "❌ **Generation Failed**\n\n"
                        "No image was returned. Please try again.",
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            elif status in ["Error", "Failed", "Content Moderated"]:
                error_msg = result.get("error", "Unknown error occurred")
                await self.db.update_task_status(task_id, status, error_message=error_msg)
                
                await status_message.edit_text(
                    f"❌ **Generation Failed**\n\n"
                    f"**Error:** {error_msg}\n\n"
                    "Please try with a different prompt.",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            else:
                await status_message.edit_text(
                    "⏰ **Generation Timeout**\n\n"
                    "The generation is taking longer than expected. "
                    "Please try again with a simpler prompt.",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        except Exception as e:
            logger.error(f"Error in generation task: {e}")
            await status_message.edit_text(
                "❌ **Generation Failed**\n\n"
                "An unexpected error occurred. Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        finally:
            # Decrement active tasks
            self.rate_limiter.decrement_active_tasks(user_id)
            
            # Remove from pending tasks
            if user_id in self.pending_tasks:
                del self.pending_tasks[user_id]
    
    async def enhance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /enhance command."""
        user = update.effective_user
        
        # Check if replying to an image
        if not update.message.reply_to_message or not update.message.reply_to_message.photo:
            await update.message.reply_text(
                "Please reply to an image with `/enhance` to improve its quality!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Rate limiting
        allowed, error_msg = await self.rate_limiter.is_allowed(user.id)
        if not allowed:
            await update.message.reply_text(f"⚠️ {error_msg}")
            return
        
        try:
            status_message = await update.message.reply_text(
                "✨ **Enhancing your image...**\n\n"
                "⏳ This may take a few moments...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Get the largest photo
            photo = update.message.reply_to_message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            
            # For now, we'll generate an enhanced version using a prompt
            # In a real implementation, you'd use BFL's image enhancement API
            enhancement_prompt = "high quality, detailed, professional, enhanced, 4k resolution"
            
            self.rate_limiter.increment_active_tasks(user.id)
            
            # Start enhancement task
            task = asyncio.create_task(
                self._enhance_image_task(user.id, enhancement_prompt, status_message, update)
            )
            
            self.pending_tasks[user.id] = task
            
        except Exception as e:
            logger.error(f"Error in enhance command: {e}")
            await update.message.reply_text(
                "❌ Sorry, something went wrong. Please try again later."
            )
    
    async def _enhance_image_task(self, user_id: int, prompt: str, 
                                status_message, update: Update):
        """Background task for image enhancement."""
        try:
            # Start enhancement (using generation for now)
            task_id, polling_url = await self.ai.generate_image(
                prompt=prompt,
                width=1024,
                height=1024
            )
            
            # Poll for result
            result = await self.ai.poll_for_result(task_id, polling_url, timeout=300)
            status = result.get("status")
            
            if status == "Ready":
                image_url = result.get("result", {}).get("sample")
                
                if image_url:
                    # Save image record
                    image_record = ImageRecord(
                        user_id=user_id,
                        prompt="Image Enhancement",
                        image_url=image_url,
                        task_id=task_id,
                        image_type="enhancement"
                    )
                    await self.db.save_image_record(image_record)
                    
                    # Update usage stats
                    await self.db.increment_usage_stats(user_id, "total_enhancements")
                    
                    await status_message.delete()
                    await update.effective_chat.send_photo(
                        photo=image_url,
                        caption="✨ **Enhanced Image**\n\nYour image has been enhanced!",
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                await status_message.edit_text(
                    "❌ **Enhancement Failed**\n\n"
                    "Please try again later.",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        except Exception as e:
            logger.error(f"Error in enhancement task: {e}")
            await status_message.edit_text(
                "❌ **Enhancement Failed**\n\n"
                "An unexpected error occurred.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        finally:
            self.rate_limiter.decrement_active_tasks(user_id)
            if user_id in self.pending_tasks:
                del self.pending_tasks[user_id]
    
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command."""
        user = update.effective_user
        
        try:
            images = await self.db.get_user_images(user.id, limit=10)
            
            if not images:
                await update.message.reply_text(
                    "📝 **No History Found**\n\n"
                    "You haven't generated any images yet!\n"
                    "Use `/generate <prompt>` to create your first image.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            history_text = "📖 **Your Recent Images**\n\n"
            
            for i, image in enumerate(images[:5], 1):
                created_at = image.created_at.strftime("%Y-%m-%d %H:%M")
                prompt = image.prompt[:50] + "..." if len(image.prompt) > 50 else image.prompt
                history_text += f"**{i}.** {prompt}\n🕒 {created_at}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("🎨 Generate New", callback_data="quick_generate")],
                [InlineKeyboardButton("📊 Usage Stats", callback_data="stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                history_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error in history command: {e}")
            await update.message.reply_text(
                "❌ Sorry, couldn't retrieve your history. Please try again later."
            )
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command."""
        user = update.effective_user
        
        try:
            user_data = await self.db.get_or_create_user(user.id)
            stats = self.rate_limiter.get_user_stats(user.id)
            
            settings_text = f"""
⚙️ **Settings & Stats**

**Current Preferences:**
• Default Style: {user_data.preferences.get("default_style", "realistic")}
• Image Quality: {user_data.preferences.get("image_quality", "high")}
• Notifications: {'✅' if user_data.preferences.get('notifications', True) else '❌'}

**Usage Statistics:**
• Total Generations: {user_data.usage_stats.get('total_generations', 0)}
• Total Enhancements: {user_data.usage_stats.get('total_enhancements', 0)}
• Total Edits: {user_data.usage_stats.get('total_edits', 0)}

**Rate Limits:**
• Requests: {stats['recent_requests']}/{stats['max_requests']} per minute
• Active Tasks: {stats['active_tasks']}/{stats['max_active_tasks']}
            """
            
            keyboard = [
                [InlineKeyboardButton("🎨 Style Settings", callback_data="style_settings")],
                [InlineKeyboardButton("🔔 Notifications", callback_data="toggle_notifications")],
                [InlineKeyboardButton("📊 Detailed Stats", callback_data="detailed_stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                settings_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error in settings command: {e}")
            await update.message.reply_text(
                "❌ Sorry, couldn't load settings. Please try again later."
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = """
🤖 **AI Image Generator Bot - Help**

**Commands:**
• `/start` - Start the bot and see welcome message
• `/generate <prompt>` - Generate images from text description
• `/enhance` - Enhance image quality (reply to an image)
• `/history` - View your recent image generations
• `/settings` - View and manage your preferences
• `/help` - Show this help message

**How to Use:**

**1. Generate Images:**
Just type `/generate` followed by your description:
• `/generate a beautiful sunset over mountains`
• `/generate futuristic city with flying cars`
• `/generate cute cat wearing a wizard hat`

**2. Enhance Images:**
Reply to any image with `/enhance` to improve its quality.

**3. Quick Generation:**
You can also just send a message starting with your description, and I'll understand!

**Tips for Better Results:**
• Be specific and descriptive
• Include style keywords (realistic, artistic, cartoon, etc.)
• Mention lighting, colors, and mood
• Keep prompts under 500 characters

**Rate Limits:**
• 10 requests per minute
• 5 concurrent generations
• Images expire after 10 minutes (download quickly!)

**Need Help?**
If you encounter any issues, please try again or contact support.

Happy creating! 🎨✨
        """
        
        keyboard = [
            [InlineKeyboardButton("🎨 Try Generate", callback_data="quick_generate")],
            [InlineKeyboardButton("📖 Examples", callback_data="examples")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )


