import os
import hashlib
from fastapi import UploadFile, HTTPException
from ..core.config import get_settings
from typing import Tuple
import aiofiles
import mimetypes
from botocore.exceptions import ClientError

settings = get_settings()

class UploadService:
    MIME_TYPES = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'pdf': 'application/pdf'
    }

    @staticmethod
    async def validate_file(file: UploadFile, photo_only: bool = False) -> bool:
        """
        Validate file type and size
        If photo_only is True, only accept JPG and PNG files
        """
        # Check content length
        content_length = file.headers.get('content-length')
        if content_length and int(content_length) > settings.MAX_FILE_SIZE:
            return False
        
        # Get file extension
        extension = file.filename.split('.')[-1].lower()
        if extension not in settings.ALLOWED_EXTENSIONS:
            return False
            
        # Check MIME type
        mime_type = UploadService.MIME_TYPES.get(extension)
        if not mime_type:
            return False
            
        if photo_only and not mime_type.startswith('image/'):
            return False
            
        return True

    @staticmethod
    async def save_file(file: UploadFile, subfolder: str = "") -> Tuple[str, str]:
        """
        Save file and return URL and hash
        Optional subfolder parameter for organizing uploads
        """
        # Create hash of file content
        sha256_hash = hashlib.sha256()
        contents = await file.read()
        sha256_hash.update(contents)
        file_hash = sha256_hash.hexdigest()
        
        # Generate unique filename using hash
        file_extension = file.filename.split('.')[-1].lower()
        filename = f"{file_hash}.{file_extension}"
        
        if subfolder:
            filename = f"{subfolder}/{filename}"
        
        if settings.USE_S3:
            try:
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_REGION
                )
                
                s3_client.put_object(
                    Bucket=settings.AWS_BUCKET_NAME,
                    Key=filename,
                    Body=contents,
                    ContentType=file.content_type
                )
                
                file_url = f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{filename}"
            except ClientError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload to S3: {str(e)}"
                )
        else:
            # Save locally
            upload_dir = os.path.join(settings.UPLOAD_DIR, subfolder) if subfolder else settings.UPLOAD_DIR
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, filename)
            
            async with aiofiles.open(file_path, 'wb') as out_file:
                await out_file.write(contents)
            
            file_url = file_path
        
        await file.seek(0)
        return file_url, file_hash




