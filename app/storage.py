from minio import Minio
from app.config import Config
import logging

logger = logging.getLogger(__name__)

class MinIOStorage:
    def __init__(self):
        self.client = Minio(
            Config.MINIO_ENDPOINT,
            access_key=Config.MINIO_ACCESS_KEY,
            secret_key=Config.MINIO_SECRET_KEY,
            secure=True
        )
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        if not self.client.bucket_exists(Config.MINIO_BUCKET):
            self.client.make_bucket(Config.MINIO_BUCKET)
            logger.info(f"Created bucket {Config.MINIO_BUCKET}")
    
    def save_image(self, image_data: bytes, content_type='image/jpeg') -> str:
        from io import BytesIO
        import uuid
        
        filename = f"{uuid.uuid4()}.jpg"
        buffer = BytesIO(image_data)
        
        self.client.put_object(
            Config.MINIO_BUCKET,
            filename,
            buffer,
            len(image_data),
            content_type
        )
        return filename
    
    def get_image_url(self, filename: str) -> str:
        return f"https://{Config.MINIO_ENDPOINT}/{Config.MINIO_BUCKET}/{filename}"

    
    def list_images(self):
        return [
            obj.object_name 
            for obj in self.client.list_objects(Config.MINIO_BUCKET, '', True)
        ]