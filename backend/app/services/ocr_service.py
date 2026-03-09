"""
OCR Service - Local Tesseract OCR fallback for scanned PDFs
"""
import re
from typing import Optional, Tuple

try:
    from pdf2image import convert_from_path
    from PIL import Image, ImageEnhance, ImageFilter
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

class OCRService:
    MIN_TEXT_LENGTH = 800
    MIN_WORD_COUNT = 150
    MAX_OCR_PAGES = 5
    OCR_TIMEOUT_SECONDS = 45 
    OCR_DPI = 300
    
    EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    PHONE_PATTERN = r'(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}|\+\d{1,3}[-.\s]?\d{6,14}'
    
    def __init__(self):
        self.ocr_available = OCR_AVAILABLE
    
    def is_available(self) -> bool:
        return self.ocr_available
    
    def needs_ocr(self, text: str, email: Optional[str] = None, phone: Optional[str] = None) -> bool:
        if len(text.strip()) < self.MIN_TEXT_LENGTH: return True
        if len(text.split()) < self.MIN_WORD_COUNT: return True
        if not email and not re.search(self.EMAIL_PATTERN, text): return True
        if not phone and not re.search(self.PHONE_PATTERN, text): return True
        return False
    
    def extract_text_with_ocr(self, pdf_path: str, max_pages: Optional[int] = None) -> Tuple[Optional[str], str, str]:
        if not self.ocr_available: return None, "ocr_unavailable", "low"
        max_pages = max_pages or self.MAX_OCR_PAGES
        
        try:
            images = convert_from_path(pdf_path, dpi=self.OCR_DPI, first_page=1, last_page=max_pages)
            if len(images) > max_pages: return None, "ocr_unavailable", "low"
            
            all_text = []
            for image in images:
                processed_image = self._preprocess_image(image)
                page_text = pytesseract.image_to_string(
                    processed_image, 
                    lang='eng+ind', 
                    config='--oem 3 --psm 3',
                    timeout=self.OCR_TIMEOUT_SECONDS
                )
                all_text.append(page_text)
                del processed_image
            
            cleaned_text = self._clean_ocr_text('\n\n'.join(all_text))
            confidence = self._calculate_ocr_confidence(cleaned_text)
            return cleaned_text, "ocr", confidence
            
        except RuntimeError: 
            return None, "ocr_unavailable", "low"
        except Exception as e:
            print(f"OCR Error: {str(e)}")
            return None, "ocr_unavailable", "low"
            
    def _preprocess_image(self, image: 'Image.Image') -> 'Image.Image':
        if image.mode != 'L': image = image.convert('L')
        image = ImageEnhance.Contrast(image).enhance(2.0).filter(ImageFilter.SHARPEN)
        image = image.point(lambda p: p > 200 and 255)
        w, h = image.size
        if w < 1500: image = image.resize((int(w * (1500/w)), int(h * (1500/w))), Image.LANCZOS)
        return image
        
    def _clean_ocr_text(self, text: str) -> str:
        if not text: return ""
        lines = [line for line in text.split('\n') if line.strip() and not re.match(r'^\s*(?:Page\s*)?\d+\s*(?:of\s*\d+)?\s*$', line, re.IGNORECASE)]
        result = '\n'.join(lines)
        return re.sub(r'\n{3,}', '\n\n', re.sub(r'[ \t]+', ' ', result)).strip()
        
    def _calculate_ocr_confidence(self, text: str) -> str:
        if not text: return "low"
        score = 0
        word_count = len(text.split())
        if word_count >= 150: score += 2
        elif word_count >= 50: score += 1
        if score >= 2: return "high"
        return "low"
    
    def get_pdf_page_count(self, pdf_path: str) -> int:
        try:
            from pypdf import PdfReader
            return len(PdfReader(pdf_path).pages)
        except Exception:
            return 0
    
    def should_skip_ocr(self, pdf_path: str) -> bool:
        return self.get_pdf_page_count(pdf_path) > self.MAX_OCR_PAGES

ocr_service = OCRService()