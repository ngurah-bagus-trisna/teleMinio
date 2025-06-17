import os
import uuid
import io
import logging
import threading
import random
from dotenv import load_dotenv
from PIL import Image
from flask import Flask, jsonify
from flask_cors import CORS
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from minio import Minio

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN   = os.getenv('TELEGRAM_TOKEN')
MINIO_ENDPOINT   = os.getenv('MINIO_ENDPOINT')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')
MINIO_BUCKET     = os.getenv('MINIO_BUCKET', 'photos')
ALLOWED_CHAT_ID  = int(os.getenv('ALLOWED_CHAT_ID', '0'))

# Initialize MinIO client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=True
)
# Ensure bucket exists
if not minio_client.bucket_exists(MINIO_BUCKET):
    minio_client.make_bucket(MINIO_BUCKET)
    logger.info(f"Created bucket {MINIO_BUCKET}")

# Setup Flask app for /random endpoint
flask_app = Flask(__name__)
CORS(flask_app)
USED_FILE = os.path.join(os.getcwd(), 'used.txt')
if not os.path.exists(USED_FILE):
    open(USED_FILE, 'w').close()

@flask_app.route('/random', methods=['GET'])
def random_photo():
    try:
        names = [obj.object_name for obj in minio_client.list_objects(MINIO_BUCKET, "", True)]
        if not names:
            return jsonify(error="No objects found"), 404
        with open(USED_FILE, 'r') as f:
            used = set(line.strip() for line in f if line.strip())
        unused = [n for n in names if n not in used]
        if not unused:
            return jsonify(error="All photos used"), 404
        pick = random.choice(unused)
        with open(USED_FILE, 'a') as f:
            f.write(pick + '\n')
        url = minio_client.presigned_get_object(MINIO_BUCKET, pick)
        return jsonify(url=url)
    except Exception as e:
        logger.error(f"Random photo error: {e}")
        return jsonify(error=str(e)), 500

# Run Flask server in background
threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=8000), daemon=True).start()
logger.info("Flask HTTP server started on port 8000")

# Telegram bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    logger.info(f"Received /start from chat_id={chat_id}")
    if chat_id != ALLOWED_CHAT_ID:
        logger.warning(f"Unauthorized /start from chat_id={chat_id}")
        return
    await update.message.reply_text("Send me a photo, and I'll upload it to MinIO storage!")

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    logger.info(f"Received photo from chat_id={chat_id}")
    if chat_id != ALLOWED_CHAT_ID:
        logger.warning(f"Unauthorized photo from chat_id={chat_id}")
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    data = await file.download_as_bytearray()
    logger.info(f"Downloaded photo, bytes={len(data)}")

    # Crop to 3:2 landscape
    img = Image.open(io.BytesIO(data))
    w, h = img.size
    target_ratio = 3/2  # 3:2 ratio
    if w / h > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        box = (left, 0, left + new_w, h)
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        box = (0, top, w, top + new_h)
    cropped_img = img.crop(box)

    # Encode to JPEG bytes
    out = io.BytesIO()
    cropped_img.save(out, format='JPEG', quality=90)
    out.seek(0)
    length = out.getbuffer().nbytes

    filename = f"{uuid.uuid4()}.jpg"
    logger.info(f"Uploading cropped to MinIO as {filename}")
    try:
        minio_client.put_object(
            MINIO_BUCKET,
            filename,
            data=out,
            length=length,
            content_type='image/jpeg'
        )
        url = minio_client.presigned_get_object(MINIO_BUCKET, filename)
        logger.info(f"Upload successful, URL={url}")
        await update.message.reply_text(f"Uploaded cropped! URL: {url}")
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        await update.message.reply_text(f"Upload failed: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if hasattr(update, 'effective_chat'):
        logger.error(f"Error in chat_id={update.effective_chat.id}: {context.error}")
    else:
        logger.error(f"Error: {context.error}")

# Main entrypoint
def main() -> None:
    logger.info("Starting Telegram bot and Flask server")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_error_handler(error_handler)
    app.run_polling()

if __name__ == '__main__':
    main()
