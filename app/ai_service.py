import base64
import requests
import logging
from PIL import Image
from io import BytesIO
from app.config import Config
from typing import Optional

logger = logging.getLogger(__name__)

class AIService:
    @staticmethod
    def compress_for_ai(image_data: bytes, max_size=1024, quality=85) -> bytes:
        """Compress image specifically for AI processing"""
        try:
            img = Image.open(BytesIO(image_data))
            
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size))
            
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            return buffer.getvalue()
        
        except Exception as e:
            logger.error(f"Image compression failed: {e}")
            return image_data
    
    @staticmethod
    def generate_caption(image_url: str, max_retries=3) -> Optional[str]:
        for attempt in range(max_retries):
            try:
                # Download original image
                resp = requests.get(image_url)
                resp.raise_for_status()
                original_data = resp.content
                
                # Compress only for AI processing
                compressed_data = AIService.compress_for_ai(original_data)
                b64 = base64.b64encode(compressed_data).decode('utf-8')
                
                payload = {
                    "contents": [{
                        "parts": [
                            {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                            {"text": "First, analyze the image thoroughly. Identify not just the visible objects or people, but interpret the atmosphere, emotion, and possible story behind the scene. Reflect on what’s implied, not just what’s shown — consider solitude, tension, routine, longing, or untold narratives within the frame. Then, based on that deep interpretation, generate a single mysterious and poetic caption in English (9–15 words). The caption should evoke curiosity, solitude, or a hidden story — as if something unspoken lingers just beyond the photo. Do not describe the objects directly in the caption. Avoid generic or literal lines. Do not include hashtags, emojis, or any extra explanation — only return the caption."}
                        ]
                    }]
                }
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={Config.AI_API_KEY}"
                response = requests.post(url, json=payload, timeout=30)
                response.raise_for_status()
                
                candidates = response.json().get('candidates', [])
                if candidates:
                    return candidates[0]['content']['parts'][0]['text'].strip()
                
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    logger.error(f"All attempts failed for {image_url}")
        
        return None