import os
import uuid
import io
import logging
import threading
import random
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from minio import Minio
from flask import Flask, jsonify

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
TELEGRAM_TOKEN    = os.getenv('TELEGRAM_TOKEN')
MINIO_ENDPOINT    = os.getenv('MINIO_ENDPOINT')  # e.g., 'play.min.io'
MINIO_ACCESS_KEY  = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY  = os.getenv('MINIO_SECRET_KEY')
MINIO_BUCKET      = os.getenv('MINIO_BUCKET', 'photos')
ALLOWED_CHAT_ID   = int(os.getenv('ALLOWED_CHAT_ID'))  # Only respond to this chat ID

# Initialize MinIO client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=True  # Set to False if not using TLS
)

# Ensure bucket exists
if not minio_client.bucket_exists(MINIO_BUCKET):
    minio_client.make_bucket(MINIO_BUCKET)
    logger.info("Created bucket: %s", MINIO_BUCKET)

# Setup Flask for /random endpoint
flask_app = Flask(__name__)
USED_FILE = os.path.join(os.getcwd(), 'used.txt')
# Ensure used.txt exists
def ensure_used_file():
    if not os.path.exists(USED_FILE):
        with open(USED_FILE, 'w'): pass
ensure_used_file()

@flask_app.route('/random', methods=['GET'])
def random_photo():
    try:
        # List all objects
        names = [obj.object_name for obj in minio_client.list_objects(MINIO_BUCKET, "", True)]
        if not names:
            return jsonify(error="No objects found"), 404
        # Read used set
        with open(USED_FILE, 'r') as f:
            used = set(line.strip() for line in f if line.strip())
        # Filter unused
        unused = [n for n in names if n not in used]
        if not unused:
            return jsonify(error="All photos used"), 404
        # Pick random
        pick = random.choice(unused)
        # Mark used
        with open(USED_FILE, 'a') as f:
            f.write(pick + '\n')
        # Generate presigned URL
        url = minio_client.presigned_get_object(MINIO_BUCKET, pick)
        return jsonify(url=url)
    except Exception as e:
        logger.error("Random photo error: %s", e)
        return jsonify(error=str(e)), 500

# Run Flask in background thread
def run_http():
    flask_app.run(host='0.0.0.0', port=8000)
threading.Thread(target=run_http, daemon=True).start()
logger.info("HTTP server started on port 8000")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when /start is issued."""
    chat_id = update.effective_chat.id
    logger.info("Received /start from chat_id=%s", chat_id)
    if chat_id != ALLOWED_CHAT_ID:
        logger.warning("Unauthorized /start from chat_id=%s", chat_id)
        return
    await update.message.reply_text(
        "Send me a photo, and I'll upload it to MinIO storage!"
    )

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photos: upload them to MinIO and reply with the URL."""
    chat_id = update.effective_chat.id
    logger.info("Received photo from chat_id=%s", chat_id)
    if chat_id != ALLOWED_CHAT_ID:
        logger.warning("Unauthorized photo message from chat_id=%s", chat_id)
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_bytes = await file.download_as_bytearray()
    logger.info("Downloaded photo, bytes=%d", len(file_bytes))

    file_stream = io.BytesIO(file_bytes)
    filename = f"{uuid.uuid4()}.jpg"
    logger.info("Uploading to MinIO as %s/%s", MINIO_BUCKET, filename)

    try:
        minio_client.put_object(
            MINIO_BUCKET,
            filename,
            data=file_stream,
            length=len(file_bytes),
            content_type='image/jpeg'
        )
        url = minio_client.presigned_get_object(MINIO_BUCKET, filename)
        logger.info("Upload successful, URL=%s", url)
        await update.message.reply_text(f"Uploaded! URL: {url}")
    except Exception as e:
        logger.error("Upload failed: %s", e)
        await update.message.reply_text(f"Upload failed: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by Updates."""
    if hasattr(update, 'effective_chat'):
        logger.error("Error in chat_id=%s: %s", update.effective_chat.id, context.error)
    else:
        logger.error("Error: %s", context.error)


def main() -> None:
    """Start the bot."""
    logger.info("Starting bot and HTTP server")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_error_handler(error_handler)
    app.run_polling()

if __name__ == '__main__':
    main()
