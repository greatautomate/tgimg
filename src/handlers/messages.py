
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from .commands import CommandHandlers
from ..utils.logger import get_logger

logger = get_logger(__name__)

class MessageHandlers:
    def __init__(self, command_handlers: CommandHandlers):
        self.commands = command_handlers
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages as generation prompts."""
        text = update.message.text.strip()
        
        # Skip if it's a command
        if text.startswith('/'):
            return
        
        # Skip very short messages
        if len(text) < 3:
            await update.message.reply_text(
                "Please provide a more detailed description for image generation!\n\n"
                "Example: `a beautiful sunset over mountains`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Skip very long messages
        if len(text) > 500:
            await update.message.reply_text(
                "⚠️ Your prompt is too long! Please keep it under 500 characters.\n\n"
                f"Current length: {len(text)} characters",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Treat as generation prompt
        user = update.effective_user
        
        # Rate limiting
        allowed, error_msg = await self.commands.rate_limiter.is_allowed(user.id)
        if not allowed:
            await update.message.reply_text(f"⚠️ {error_msg}")
            return
        
        try:
            # Send initial message
            status_message = await update.message.reply_text(
                "🎨 **Generating your image...**\n\n"
                f"**Prompt:** {text}\n"
                "⏳ This may take a few moments...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Increment active tasks
            self.commands.rate_limiter.increment_active_tasks(user.id)
            
            # Start generation in background
            task = asyncio.create_task(
                self.commands._generate_image_task(user.id, text, status_message, update)
            )
            
            # Store task reference
            self.commands.pending_tasks[user.id] = task
            
        except Exception as e:
            logger.error(f"Error handling text message: {e}")
            await update.message.reply_text(
                "❌ Sorry, something went wrong. Please try again later."
            )
    
    async def handle_photo_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages for editing."""
        user = update.effective_user
        
        # Check if there's a caption with instructions
        caption = update.message.caption or ""
        
        if not caption:
            # Provide options for what to do with the image
            keyboard_markup = [
                [{"text": "✨ Enhance Quality", "callback_data": f"enhance_uploaded:{update.message.message_id}"}],
                [{"text": "🎨 Edit Style", "callback_data": f"edit_uploaded:{update.message.message_id}"}],
                [{"text": "📝 Describe Image", "callback_data": f"describe:{update.message.message_id}"}]
            ]
            
            await update.message.reply_text(
                "📸 **Image Received!**\n\n"
                "What would you like to do with this image?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup={"inline_keyboard": keyboard_markup}
            )
            return
        
        # If there's a caption, treat it as an edit instruction
        await self._handle_image_edit(update, context, caption)
    
    async def _handle_image_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE, instruction: str):
        """Handle image editing with instruction."""
        user = update.effective_user
        
        # Rate limiting
        allowed, error_msg = await self.commands.rate_limiter.is_allowed(user.id)
        if not allowed:
            await update.message.reply_text(f"⚠️ {error_msg}")
            return
        
        try:
            status_message = await update.message.reply_text(
                "🎨 **Editing your image...**\n\n"
                f"**Instruction:** {instruction}\n"
                "⏳ This may take a few moments...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Get the photo
            photo = update.message.photo[-1]  # Get largest size
            file = await context.bot.get_file(photo.file_id)
            
            # For now, we'll use the instruction as a generation prompt
            # In a real implementation, you'd use image-to-image editing
            edit_prompt = f"{instruction}, high quality, detailed"
            
            self.commands.rate_limiter.increment_active_tasks(user.id)
            
            # Start editing task
            task = asyncio.create_task(
                self.commands._generate_image_task(user.id, edit_prompt, status_message, update)
            )
            
            self.commands.pending_tasks[user.id] = task
            
        except Exception as e:
            logger.error(f"Error handling image edit: {e}")
            await update.message.reply_text(
                "❌ Sorry, something went wrong. Please try again later."
            )
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user = query.from_user
        
        try:
            if data == "quick_generate":
                await query.edit_message_text(
                    "🎨 **Quick Generate**\n\n"
                    "Send me a message describing what you want to create!\n\n"
                    "Example: `a beautiful sunset over mountains`",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif data == "help":
                await self.commands.help_command(update, context)
            
            elif data == "settings":
                await self.commands.settings_command(update, context)
            
            elif data.startswith("regenerate:"):
                prompt = data.split(":", 1)[1]
                # Create a fake update to reuse generation logic
                class FakeMessage:
                    text = f"/generate {prompt}"
                
                class FakeUpdate:
                    message = FakeMessage()
                    effective_user = user
                    effective_chat = query.message.chat
                
                fake_update = FakeUpdate()
                context.args = prompt.split()
                await self.commands.generate_command(fake_update, context)
            
            elif data.startswith("enhance:"):
                task_id = data.split(":", 1)[1]
                # Get the task record to find the image
                task_record = await self.commands.db.get_task_record(task_id)
                
                if task_record and task_record.result_url:
                    await query.edit_message_text(
                        "✨ **Enhancing Image...**\n\n"
                        "⏳ Please wait...",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    # Start enhancement
                    enhancement_prompt = "high quality, detailed, professional, enhanced, 4k resolution"
                    self.commands.rate_limiter.increment_active_tasks(user.id)
                    
                    task = asyncio.create_task(
                        self.commands._enhance_image_task(user.id, enhancement_prompt, query.message, update)
                    )
                    
                    self.commands.pending_tasks[user.id] = task
            
            elif data == "examples":
                examples_text = """
🎨 **Example Prompts**

**Nature & Landscapes:**
• `a serene mountain lake at sunset with reflection`
• `mystical forest with glowing mushrooms and fairy lights`
• `desert oasis with palm trees and clear blue water`

**Characters & People:**
• `friendly robot character in colorful cartoon style`
• `elegant woman in Victorian dress, oil painting style`
• `wise old wizard with long beard and magical staff`

**Architecture & Cities:**
• `futuristic cyberpunk city with neon lights at night`
• `cozy cottage in English countryside with garden`
• `ancient temple ruins covered in jungle vines`

**Abstract & Artistic:**
• `swirling galaxies in deep space, cosmic art style`
• `geometric patterns in vibrant rainbow colors`
• `watercolor painting of blooming cherry blossoms`

**Animals:**
• `majestic eagle soaring over mountain peaks`
• `cute cat wearing astronaut helmet in space`
• `colorful tropical fish swimming in coral reef`

Try any of these or create your own! 🚀
                """
                
                await query.edit_message_text(
                    examples_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            
            else:
                await query.edit_message_text(
                    "🤖 This feature is coming soon!\n\n"
                    "Use `/generate <prompt>` to create images.",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        except Exception as e:
            logger.error(f"Error handling callback query: {e}")
            await query.edit_message_text(
                "❌ Sorry, something went wrong. Please try again."
            )


