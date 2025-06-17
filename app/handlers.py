from telegram import Update
from telegram.ext import ContextTypes
from app.config import Config
from app.storage import MinIOStorage
from app.ai_service import AIService
from app.utils import FileManager
import logging
from PIL import Image
from io import BytesIO
import random

logger = logging.getLogger(__name__)

storage = MinIOStorage()

async def handle_photo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != Config.ALLOWED_CHAT_ID:
        return
    
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        data = await file.download_as_bytearray()
        
        # Process image (crop to 3:2 ratio)
        img = Image.open(BytesIO(data))
        w, h = img.size
        r = 3/2
        
        if w/h > r:
            new_width = int(h * r)
            left = (w - new_width) // 2
            box = (left, 0, left + new_width, h)
        else:
            new_height = int(w / r)
            top = (h - new_height) // 2
            box = (0, top, w, top + new_height)
        
        cropped = img.crop(box)
        
        # Save original quality to MinIO
        buffer = BytesIO()
        cropped.save(buffer, 'JPEG', quality=90)
        filename = storage.save_image(buffer.getvalue())
        image_url = storage.get_image_url(filename)
        
        # Generate and save caption
        try:
            caption = AIService.generate_caption(image_url)
            if caption:
                FileManager.save_caption(filename, caption)
                await update.message.reply_text(
                    f"✅ Uploaded!\n📷 URL: {image_url}\n📝 Caption: {caption}"
                )
            else:
                await update.message.reply_text(
                    f"✅ Uploaded!\n📷 URL: {image_url}\n⚠️ Failed to generate caption"
                )
        except Exception as e:
            logger.error(f"Caption generation error: {e}")
            await update.message.reply_text(f"✅ Uploaded! URL: {image_url}")
    
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        await update.message.reply_text("❌ Upload failed. Please try again.")

async def handle_random_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != Config.ALLOWED_CHAT_ID:
        return
    
    try:
        all_images = storage.list_images()
        unused_images = FileManager.get_unused_images(all_images)
        
        if not unused_images:
            await update.message.reply_text("No unused photos available.")
            return
        
        selected = random.choice(unused_images)
        FileManager.mark_as_used(selected)
        
        image_url = storage.get_image_url(selected)
        caption = FileManager.load_captions().get(selected, "No caption available")
        
        await update.message.reply_text(
            f"🎲 Random Photo\n📷 URL: {image_url}\n📝 Caption: {caption}"
        )
    
    except Exception as e:
        logger.error(f"Random command failed: {e}")
        await update.message.reply_text("❌ Failed to get random photo")