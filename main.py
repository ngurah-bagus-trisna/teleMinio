import os
import uuid
import io
import json
import logging
import threading
import random
import base64
import requests
from dotenv import load_dotenv
from PIL import Image
from flask import Flask, jsonify
from flask_cors import CORS
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from minio import Minio

# --- Setup logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Load & validate environment ---
load_dotenv()
required_vars = [
    'TELEGRAM_TOKEN', 'MINIO_ENDPOINT', 'MINIO_ACCESS_KEY',
    'MINIO_SECRET_KEY', 'AI_API_KEY', 'ALLOWED_CHAT_ID'
]
missing = [v for v in required_vars if not os.getenv(v)]
if missing:
    logger.error(f"Missing environment variables: {', '.join(missing)}")
    exit(1)

TELEGRAM_TOKEN   = os.getenv('TELEGRAM_TOKEN')
MINIO_ENDPOINT   = os.getenv('MINIO_ENDPOINT')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')
MINIO_BUCKET     = os.getenv('MINIO_BUCKET', 'photos')
AI_API_KEY       = os.getenv('AI_API_KEY')
ALLOWED_CHAT_ID  = int(os.getenv('ALLOWED_CHAT_ID'))

# --- Initialize MinIO client ---
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=True
)
if not minio_client.bucket_exists(MINIO_BUCKET):
    minio_client.make_bucket(MINIO_BUCKET)
    logger.info(f"Created bucket {MINIO_BUCKET}")

# --- Setup used.txt tracking ---
USED_FILE = os.path.join(os.getcwd(), 'used.txt')
if not os.path.exists(USED_FILE):
    open(USED_FILE, 'w').close()

# --- AI helper: generate caption with inline_data ---
def generate_description_from_url(image_url: str) -> str:
    # 1. Fetch headers for mime type
    try:
        head = requests.head(image_url, allow_redirects=True)
        mime = head.headers.get('Content-Type', 'image/jpeg')
        if not mime.startswith('image/'):
            mime = 'image/jpeg'
    except Exception:
        mime = 'image/jpeg'
    # 2. Download image bytes
    resp = requests.get(image_url)
    resp.raise_for_status()
    data = resp.content
    # 3. Base64 encode without line breaks
    b64 = base64.b64encode(data).decode('utf-8')
    # 4. Prepare payload for Gemini generateContent
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={AI_API_KEY}"
    )
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [
            {
                "parts": [
                    {"inline_data": {"mime_type": mime, "data": b64}},
                    {"text": "Caption this image in one sentence."}
                ]
            }
        ]
    }
    # 5. Call API
    try:
        r = requests.post(url, headers=headers, json=payload)
        r.raise_for_status()
        cand = r.json().get('candidates', [])
        if cand:
            return cand[0].get('content', {}).get('parts', [])[0].get('text', '').strip()
    except Exception as e:
        logger.error(f"Caption generation failed: {e}")
    return 'No caption available.'

# --- Flask app for HTTP /random endpoint ---
flask_app = Flask(__name__)
CORS(flask_app)

@flask_app.route('/random', methods=['GET'])
def random_photo_http():
    try:
        # List unused
        names = [obj.object_name for obj in minio_client.list_objects(MINIO_BUCKET,'',True)]
        with open(USED_FILE,'r') as f:
            used = set(line.strip() for line in f if line.strip())
        unused = [n for n in names if n not in used]
        if not unused:
            return jsonify(error="All photos used"), 404
        pick = random.choice(unused)
        with open(USED_FILE,'a') as f:
            f.write(pick+'\n')
        # Presigned URL
        img_url = minio_client.presigned_get_object(MINIO_BUCKET, pick)
        # Caption
        caption = generate_description_from_url(img_url)
        return jsonify(url=img_url, caption=caption)
    except Exception as e:
        logger.error(f"/random error: {e}")
        return jsonify(error=str(e)),500

# --- Run Flask server in background ---
threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=8000), daemon=True).start()
logger.info("Flask server running on port 8000")

# --- Telegram bot handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    await update.message.reply_text(
        "Send a photo to upload (3:2 crop) or use /random for captioned image."
    )

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    photo = update.message.photo[-1]
    file = await photo.get_file()
    data = await file.download_as_bytearray()
    img = Image.open(io.BytesIO(data))
    w,h = img.size; r=3/2
    if w/h>r:
        nw=int(h*r); left=(w-nw)//2; box=(left,0,left+nw,h)
    else:
        nh=int(w/r); top=(h-nh)//2; box=(0,top,w,top+nh)
    cropped=img.crop(box)
    buf=io.BytesIO(); cropped.save(buf,'JPEG',quality=90); buf.seek(0)
    name=f"{uuid.uuid4()}.jpg"
    minio_client.put_object(MINIO_BUCKET,name,buf,buf.getbuffer().nbytes,'image/jpeg')
    img_url = minio_client.presigned_get_object(MINIO_BUCKET,name)
    await update.message.reply_text(f"Uploaded! URL: {img_url}")

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    try:
        res = requests.get('http://localhost:8000/random')
        res.raise_for_status()
        data = res.json()
        await update.message.reply_text(json.dumps(data, ensure_ascii=False))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    open(USED_FILE,'w').close()
    await update.message.reply_text("Reset used photo list.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Telegram error: {context.error}")

# --- Main entrypoint ---
def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('random', random_command))
    app.add_handler(CommandHandler('reset', reset_command))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_error_handler(error_handler)
    app.run_polling()

if __name__ == '__main__':
    main()