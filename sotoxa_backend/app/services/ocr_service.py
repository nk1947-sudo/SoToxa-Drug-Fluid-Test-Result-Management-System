import pytesseract
from PIL import Image, ImageEnhance, ImageOps
import re
from typing import Dict, Tuple, List
import pdf2image
import os
from concurrent.futures import ThreadPoolExecutor
import logging
from ..core.config import get_settings
import platform

settings = get_settings()

pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

class OCRService:
    # Update patterns specifically for SoToxa format
    DRUG_PATTERNS = {
    "THC": [
        r"\bTHC\s+(POSITIVE|NEGATIVE|POS|NEG)\b"
    ],
    "Cocaine": [
        r"\bCOC\s+(POSITIVE|NEGATIVE|POS|NEG)\b"
    ],
    "Opiates": [
        r"\bOPI\s+(POSITIVE|NEGATIVE|POS|NEG)\b"
    ],
    "Amphetamines": [
        r"\bAMP\s+(POSITIVE|NEGATIVE|POS|NEG)\b"
    ],
    "Methamphetamines": [
        r"\bMAMP\s+(POSITIVE|NEGATIVE|POS|NEG)\b"
    ],
    "Benzodiazepines": [
        r"\bBZO\s+(POSITIVE|NEGATIVE|POS|NEG)\b"
    ]
}


    @staticmethod
    def _preprocess_image(image: Image.Image) -> Image.Image:
        """Enhanced preprocessing for SoToxa prints"""
        # Convert to grayscale
        image = image.convert('L')
        
        # Auto-level the image
        image = ImageOps.autocontrast(image, cutoff=2)
        
        # Increase contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        
        # Increase brightness
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.2)
        
        # Increase sharpness
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)
        
        # Resize if needed
        if image.width < 1500 or image.height < 1500:
            ratio = 1500.0 / min(image.width, image.height)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        return image

    @staticmethod
    def _extract_result(text: str, patterns: List[str], default: str = "Not Found") -> str:
        """Try multiple patterns to extract drug test results"""
        text = text.upper()  # Convert to uppercase for better matching
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result = matches[0].strip().upper()
                # Normalize results
                if result in ['POS', 'POSITIVE']:
                    return 'Positive'
                elif result in ['NEG', 'NEGATIVE']:
                    return 'Negative'
        return default

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean and normalize OCR text"""
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Convert multiple spaces or special characters to single space
        text = re.sub(r'[^a-zA-Z0-9\s:-]', ' ', text)
        # Normalize common OCR mistakes
        text = text.replace('P0S', 'POS').replace('NEO', 'NEG')
        # Convert multiple spaces to single space
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def _validate_results(structured_data: Dict[str, str]) -> bool:
        """Validate that we have at least some valid results"""
        valid_results = [result for result in structured_data.values() 
                        if result != "Not Found"]
        return len(valid_results) > 0

    @staticmethod
    async def process_image(image_path: str) -> Tuple[str, Dict[str, str], float]:
        """Process image with OCR and extract drug test results"""
        try:
            # Load and preprocess image
            image = Image.open(image_path)
            processed_image = OCRService._preprocess_image(image)
            
            # Save preprocessed image for debugging
            debug_path = image_path + "_processed.jpg"
            processed_image.save(debug_path)
            logging.info(f"Saved preprocessed image to: {debug_path}")

            # Configure tesseract
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789:.-/ '

            # Perform OCR
            ocr_result = pytesseract.image_to_data(
                processed_image,
                output_type=pytesseract.Output.DICT,
                config=custom_config
            )

            # Extract text with confidence
            text_with_conf = [(text, float(conf)) 
                            for text, conf in zip(ocr_result['text'], ocr_result['conf'])
                            if float(conf) > settings.OCR_CONFIDENCE_THRESHOLD]

            # Join filtered text
            full_text = " ".join(text for text, _ in text_with_conf)
            full_text = OCRService._clean_text(full_text)

            # Log raw OCR output
            logging.info(f"Raw OCR text:\n{full_text}")
            
            # Calculate confidence
            confidences = [conf for _, conf in text_with_conf]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Extract results
            structured_data = {}
            for drug, patterns in OCRService.DRUG_PATTERNS.items():
                result = OCRService._extract_result(full_text, patterns)
                structured_data[drug] = result
                logging.info(f"Drug {drug}: Pattern match attempt on text: '{full_text}'")
                logging.info(f"Drug {drug}: Result: '{result}'")

            return full_text, structured_data, avg_confidence

        except Exception as e:
            logging.error(f"OCR processing failed for {image_path}: {str(e)}")
            raise









