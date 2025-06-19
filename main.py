import os
import logging
from flask import Flask, jsonify, request
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

# Add this to your Config class in app/config.py
# API_KEY = os.getenv('API_KEY', 'default-secret-key')

# Flask setup
flask_app = Flask(__name__)
CORS(flask_app)

@flask_app.route('/random', methods=['GET'])
def random_photo_endpoint():
    from app.storage import MinIOStorage
    from app.utils import FileManager
    
    # Get API key from query parameter
    api_key = request.args.get('key')
    
    # Verify API key
    if not api_key or api_key != Config.API_KEY:
        logger.warning(f"Unauthorized access attempt with key: {api_key}")
        return jsonify(error="Unauthorized: Invalid API key"), 401
    
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