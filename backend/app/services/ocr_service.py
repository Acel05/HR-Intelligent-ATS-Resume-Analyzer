"""
OCR Service - Local Tesseract OCR fallback for scanned PDFs
Provides enterprise-grade OCR capabilities without cloud APIs
"""
import re
import io
import threading
from typing import Optional, Tuple, Dict, Any
from contextlib import contextmanager

try:
    from pdf2image import convert_from_path
    from PIL import Image, ImageEnhance, ImageFilter
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


class TimeoutError(Exception):
    pass


class OCRService:
    MIN_TEXT_LENGTH = 800
    MIN_WORD_COUNT = 150
    MAX_OCR_PAGES = 5
    OCR_TIMEOUT_SECONDS = 45 # Waktu ditingkatkan untuk binarization handling
    OCR_DPI = 300
    
    EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    PHONE_PATTERN = r'(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}|\+\d{1,3}[-.\s]?\d{6,14}'
    
    def __init__(self):
        self.ocr_available = OCR_AVAILABLE
    
    def is_available(self) -> bool:
        return self.ocr_available
    
    def needs_ocr(self, text: str, email: Optional[str] = None, phone: Optional[str] = None) -> bool:
        if len(text.strip()) < self.MIN_TEXT_LENGTH:
            return True
        word_count = len(text.split())
        if word_count < self.MIN_WORD_COUNT:
            return True
        if not email and not re.search(self.EMAIL_PATTERN, text):
            return True
        if not phone and not re.search(self.PHONE_PATTERN, text):
            return True
        return False
    
    def extract_text_with_ocr(self, pdf_path: str, max_pages: Optional[int] = None) -> Tuple[Optional[str], str, str]:
        if not self.ocr_available:
            return None, "ocr_unavailable", "low"
        
        max_pages = max_pages or self.MAX_OCR_PAGES
        
        try:
            result = self._run_ocr_with_timeout(pdf_path, max_pages)
            if result is None:
                return None, "ocr_unavailable", "low"
            
            extracted_text, page_count = result
            cleaned_text = self._clean_ocr_text(extracted_text)
            confidence = self._calculate_ocr_confidence(cleaned_text)
            
            return cleaned_text, "ocr", confidence
            
        except TimeoutError:
            return None, "ocr_unavailable", "low"
        except Exception as e:
            print(f"OCR Error: {str(e)}")
            return None, "ocr_unavailable", "low"
    
    def _run_ocr_with_timeout(self, pdf_path: str, max_pages: int) -> Optional[Tuple[str, int]]:
        result = {"text": None, "pages": 0, "error": None}
        
        def ocr_worker():
            try:
                images = convert_from_path(
                    pdf_path,
                    dpi=self.OCR_DPI,
                    first_page=1,
                    last_page=max_pages
                )
                
                if len(images) > max_pages:
                    result["error"] = "too_many_pages"
                    return
                
                all_text = []
                for i, image in enumerate(images[:max_pages]):
                    processed_image = self._preprocess_image(image)
                    # PSM 3 is typically much better for resumes (Fully automatic page segmentation)
                    page_text = pytesseract.image_to_string(
                        processed_image,
                        lang='eng+ind',
                        config='--oem 3 --psm 3'
                    )
                    all_text.append(page_text)
                    del processed_image
                    del image
                
                result["text"] = '\n\n'.join(all_text)
                result["pages"] = len(images)
            except Exception as e:
                result["error"] = str(e)
        
        thread = threading.Thread(target=ocr_worker)
        thread.daemon = True
        thread.start()
        thread.join(timeout=self.OCR_TIMEOUT_SECONDS)
        
        if thread.is_alive():
            raise TimeoutError("OCR processing exceeded timeout")
        
        if result["error"]:
            if result["error"] == "too_many_pages":
                return None
            raise Exception(result["error"])
        
        if result["text"] is None:
            return None
        
        return result["text"], result["pages"]
    
    def _preprocess_image(self, image: 'Image.Image') -> 'Image.Image':
        if image.mode != 'L':
            image = image.convert('L')
        
        # Ekstrim kontras & filter binarization
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        image = image.filter(ImageFilter.SHARPEN)
        
        # Binarization untuk menghilangkan shadow (bayangan kertas saat di scan)
        threshold = 200
        image = image.point(lambda p: p > threshold and 255)
        
        width, height = image.size
        if width < 1500:
            scale = 1500 / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            image = image.resize((new_width, new_height), Image.LANCZOS)
        
        return image
    
    def _clean_ocr_text(self, text: str) -> str:
        if not text:
            return ""
        
        lines = text.split('\n')
        cleaned_lines = []
        seen_lines = set()
        
        page_number_pattern = re.compile(r'^\s*(?:Page\s*)?\d+\s*(?:of\s*\d+)?\s*$', re.IGNORECASE)
        header_footer_patterns = [
            re.compile(r'^\s*confidential\s*$', re.IGNORECASE),
            re.compile(r'^\s*resume\s*$', re.IGNORECASE),
            re.compile(r'^\s*curriculum\s*vitae\s*$', re.IGNORECASE),
            re.compile(r'^\s*cv\s*$', re.IGNORECASE),
        ]
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                if cleaned_lines and cleaned_lines[-1] != '':
                    cleaned_lines.append('')
                continue
            
            if page_number_pattern.match(stripped):
                continue
            
            skip = False
            for pattern in header_footer_patterns:
                if pattern.match(stripped):
                    skip = True
                    break
            if skip:
                continue
            
            line_key = stripped.lower()
            if line_key in seen_lines and len(stripped) < 50:
                continue
            seen_lines.add(line_key)
            
            cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)
        result = re.sub(r'[ \t]+', ' ', result)
        return result.strip()
    
    def _calculate_ocr_confidence(self, text: str) -> str:
        if not text:
            return "low"
        score = 0
        word_count = len(text.split())
        if word_count >= 300: score += 3
        elif word_count >= 150: score += 2
        elif word_count >= 50: score += 1
        if re.search(self.EMAIL_PATTERN, text): score += 2
        if re.search(self.PHONE_PATTERN, text): score += 1
        
        skill_keywords = ['experience', 'education', 'skills', 'python', 'java', 'javascript', 'developer', 'engineer', 'manager', 'analyst', 'project', 'team', 'company', 'university', 'bachelor', 'master', 'degree', 'certified', 'professional']
        text_lower = text.lower()
        skill_matches = sum(1 for kw in skill_keywords if kw in text_lower)
        if skill_matches >= 8: score += 3
        elif skill_matches >= 5: score += 2
        elif skill_matches >= 2: score += 1
        
        if score >= 7: return "high"
        elif score >= 4: return "medium"
        else: return "low"
    
    def get_pdf_page_count(self, pdf_path: str) -> int:
        try:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            return len(reader.pages)
        except Exception:
            return 0
    
    def should_skip_ocr(self, pdf_path: str) -> bool:
        page_count = self.get_pdf_page_count(pdf_path)
        return page_count > self.MAX_OCR_PAGES

ocr_service = OCRService()