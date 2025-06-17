import json
import os
from app.config import Config

class FileManager:
    @staticmethod
    def load_captions():
        if not os.path.exists(Config.CAPTIONS_FILE):
            return {}
        
        with open(Config.CAPTIONS_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    
    @staticmethod
    def save_caption(filename: str, caption: str):
        captions = FileManager.load_captions()
        captions[filename] = caption
        with open(Config.CAPTIONS_FILE, 'w') as f:
            json.dump(captions, f)
    
    @staticmethod
    def mark_as_used(filename: str):
        with open(Config.USED_FILE, 'a') as f:
            f.write(filename + '\n')
    
    @staticmethod
    def get_unused_images(all_images: list[str]):
        if not os.path.exists(Config.USED_FILE):
            return all_images
        
        with open(Config.USED_FILE, 'r') as f:
            used = set(line.strip() for line in f if line.strip())
        
        return [img for img in all_images if img not in used]