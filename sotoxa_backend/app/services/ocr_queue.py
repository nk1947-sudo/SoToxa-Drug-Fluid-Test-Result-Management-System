from fastapi import BackgroundTasks
from typing import Optional
from ..db.mongodb import db
from bson import ObjectId
import logging
from .ocr_service import OCRService

class OCRQueue:
    MAX_RETRIES = 3

    @staticmethod
    async def process_in_background(
        background_tasks: BackgroundTasks,
        file_path: str,
        test_id: str
    ):
        """Add OCR processing to background tasks"""
        background_tasks.add_task(
            OCRQueue._process_and_update,
            file_path,
            test_id
        )

    @staticmethod
    async def _process_and_update(file_path: str, test_id: str, retry_count: int = 0):
        """Process OCR and update database with retry mechanism"""
        try:
            # Perform OCR
            ocr_text, ocr_data, confidence = await OCRService.process_image(file_path)
            
            # Log raw results
            logging.info(f"OCR Text for test_id {test_id}:\n{ocr_text}")
            logging.info(f"Extracted data for test_id {test_id}:\n{ocr_data}")
            logging.info(f"Confidence score: {confidence}")

            # Validate results and retry if needed
            if not OCRService._validate_results(ocr_data) and retry_count < OCRQueue.MAX_RETRIES:
                logging.warning(f"Retrying OCR for test_id {test_id}, attempt {retry_count + 1}")
                return await OCRQueue._process_and_update(file_path, test_id, retry_count + 1)

            # Update database
            update_result = await db.db["drug_tests"].update_one(
                {"_id": ObjectId(test_id)},
                {
                    "$set": {
                        "ocr_text": ocr_text,
                        "ocr_data": ocr_data,
                        "ocr_confidence": confidence,
                        "processing_status": "completed",
                        "retry_count": retry_count
                    }
                }
            )

            if update_result.modified_count == 0:
                logging.error(f"Failed to update OCR results for test_id: {test_id}")

        except Exception as e:
            logging.error(f"Background OCR processing failed for test_id {test_id}: {str(e)}")
            await db.db["drug_tests"].update_one(
                {"_id": ObjectId(test_id)},
                {
                    "$set": {
                        "processing_status": "failed",
                        "processing_error": str(e),
                        "retry_count": retry_count
                    }
                }
            )

