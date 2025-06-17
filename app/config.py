import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
    MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
    MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')
    MINIO_BUCKET = os.getenv('MINIO_BUCKET', 'photos')
    AI_API_KEY = os.getenv('AI_API_KEY')
    ALLOWED_CHAT_ID = int(os.getenv('ALLOWED_CHAT_ID'))
    
    USED_FILE = 'used.txt'
    CAPTIONS_FILE = 'captions.json'