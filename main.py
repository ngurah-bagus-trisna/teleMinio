import logging
from flask import Flask, jsonify
from flask_cors import CORS
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from app.config import Config
from app.handlers import handle_photo_upload, handle_random_request
import threading
import random

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask setup
flask_app = Flask(__name__)
CORS(flask_app)

@flask_app.route('/random', methods=['GET'])
def random_photo_endpoint():
    from app.storage import MinIOStorage
    from app.utils import FileManager
    
    try:
        storage = MinIOStorage()
        all_images = storage.list_images()
        unused_images = FileManager.get_unused_images(all_images)
        
        if not unused_images:
            return jsonify(error="No unused photos available"), 404
        
        selected = random.choice(unused_images)
        FileManager.mark_as_used(selected)
        
        return jsonify({
            'url': storage.get_image_url(selected),
            'caption': FileManager.load_captions().get(selected, "No caption")
        })
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify(error=str(e)), 500

def run_flask():
    flask_app.run(host='0.0.0.0', port=8000)

def main():
    # Start Flask in background
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info("Flask server running on port 8000")
    
    # Setup Telegram bot
    app = Application.builder().token(Config.TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler('start', lambda u,c: u.message.reply_text(
        "Send a photo to upload (3:2 crop) or use /random for captioned image."
    )))
    app.add_handler(CommandHandler('random', handle_random_request))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_upload))
    
    app.run_polling()

if __name__ == '__main__':
    main()