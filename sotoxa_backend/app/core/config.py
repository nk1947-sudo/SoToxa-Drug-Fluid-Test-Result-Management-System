from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Set
import os
import platform

class Settings(BaseSettings):
    # MongoDB settings
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "sotoxa_db"
    
    # File storage settings
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: Set[str] = {"jpg", "jpeg", "png", "pdf"}
    
    # JWT settings
    SECRET_KEY: str = "your-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # OCR settings
    OCR_CONFIDENCE_THRESHOLD: float = 60.0  # Lower threshold for more results
    TESSERACT_CMD: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    
    # S3 settings
    USE_S3: bool = False
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_BUCKET_NAME: str = ""
    AWS_REGION: str = "us-east-1"
    
    # PDF processing settings
    POPPLER_PATH: str = os.getenv('POPPLER_PATH', 
        r'C:\Program Files\poppler-xx\Library\bin' if platform.system() == "Windows" else None
    )
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()




