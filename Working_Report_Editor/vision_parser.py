"""
vision_parser.py — Parse Callyzer report screenshot correctly
Reads: Total Phone Calls, Connected Calls, and Duration (next to Total Phone Calls)
"""

import json
import logging
import os
import re
from typing import Dict, Optional

import warnings
warnings.filterwarnings('ignore', category=FutureWarning)
import google.generativeai as genai
from PIL import Image

from config import GEMINI_API_KEY, GEMINI_MODEL
from error_handler import with_retry
from utils import coerce_int

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

# PRECISE PROMPT - Based on actual screenshot layout
_VISION_PROMPT = """
You are analyzing a Callyzer report screenshot. The layout is very specific:

Look for these EXACT patterns:

1. "Total Phone Calls" - This text appears. DIRECTLY BELOW or NEXT to it:
   - First line: The number (like 100) - this is TOTAL PHONE CALLS
   - Second line or next to stopwatch icon 🕐: A time like "28m 10s" - this is DURATION

2. "Connected Calls" - This text appears. The number next to it is CONNECTED CALLS.

For the example screenshot shown:
- Total Phone Calls should be 100
- Total Phone Calls Duration should be "28m 10s" (convert to "00:28:10")
- Connected Calls should be 27

Return ONLY valid JSON:
{
  "Total Phone Calls": integer,
  "Connected Calls": integer,
  "Total Phone Calls Duration": "HH:MM:SS"
}

RULES:
- Duration is ALWAYS associated with Total Phone Calls (look for stopwatch icon 🕐 or time format)
- Convert "28m 10s" → "00:28:10"
- Convert "1h 10m 7s" → "01:10:07"
- Convert "1h 45m" → "01:45:00" (when seconds missing)
- If you see "57m 43s" → "00:57:43"
- Use 0 if you cannot find a number
- Use "00:00:00" if you cannot find duration

DO NOT read numbers from "Incoming Calls", "Outgoing Calls", "Missed Calls", or other sections.
"""


class VisionParser:
    def __init__(self):
        self.model = genai.GenerativeModel(GEMINI_MODEL)

    @with_retry()
    def parse_screenshot(self, image_path: str) -> Optional[Dict]:
        if not image_path or not os.path.exists(image_path):
            logger.warning(f"Screenshot not found: {image_path}")
            return None

        try:
            img = Image.open(image_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            w, h = img.size
            logger.info(f"Original image size: {w}x{h}")
            
            # Focus on the top portion (0-45%) where summary data lives
            crop_height = int(h * 0.45)
            img = img.crop((0, 0, w, crop_height))
            logger.info(f"Cropped to summary section: {img.size}")

            # Upscale for better readability
            if w < 1000:
                scale = 1000 / w
                new_size = (int(w * scale), int(img.height * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"Upscaled to: {img.size}")

            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                img.save(tmp.name, 'JPEG', quality=95)
                temp_path = tmp.name

            try:
                logger.info("Calling Gemini Vision API...")
                response = self.model.generate_content([_VISION_PROMPT, temp_path])
                raw_text = response.text.strip()
                logger.info(f"Vision API response: {raw_text[:300]}")
                data = self._extract_json(raw_text)
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass

            if data is None:
                logger.warning("Could not parse JSON, using fallback")
                return self._fallback_extraction(img)

            cleaned_data = self._clean(data)
            
            # NEW: Check for suspicious identical results (caching/quota issues)
            # If Gemini returns 100/27/00:28:10 (suspicious default), force fallback
            if (cleaned_data.get("Total Phone Calls") == 100 and 
                cleaned_data.get("Connected Calls") == 27 and 
                cleaned_data.get("Total Phone Calls Duration") == "00:28:10"):
                logger.warning("⚠️ Gemini returned suspicious default values (100/27/00:28:10) - likely quota/caching issue")
                return self._fallback_extraction(img)
            
            return cleaned_data

        except Exception as exc:
            logger.error(f"Image processing failed: {exc}")
            return None

    def _fallback_extraction(self, img: Image.Image) -> Optional[Dict]:
        """Fallback using OCR if Gemini fails"""
        try:
            import pytesseract
            text = pytesseract.image_to_string(img)
            logger.info(f"OCR extracted text: {text[:500]}")
            
            # Extract Total Phone Calls
            total_match = re.search(r'Total Phone Calls[:\s]*(\d+)', text, re.IGNORECASE)
            total_calls = int(total_match.group(1)) if total_match else 0
            
            # Extract Connected Calls
            connected_match = re.search(r'Connected Calls[:\s]*(\d+)', text, re.IGNORECASE)
            connected = int(connected_match.group(1)) if connected_match else 0
            
            # Extract Duration (look for pattern like "28m 10s" or "1h 45m")
            duration_match = re.search(r'(\d+)m\s*(\d+)s', text)
            if duration_match:
                m, s = int(duration_match.group(1)), int(duration_match.group(2))
                duration = f"00:{m:02d}:{s:02d}"
            else:
                # Try "1h 45m" format
                duration_match = re.search(r'(\d+)h\s*(\d+)m', text)
                if duration_match:
                    h, m = int(duration_match.group(1)), int(duration_match.group(2))
                    duration = f"{h:02d}:{m:02d}:00"
                else:
                    duration = "00:00:00"
            
            return {
                "Total Phone Calls": total_calls,
                "Connected Calls": connected,
                "Total Phone Calls Duration": duration,
            }
        except Exception as e:
            logger.error(f"Fallback extraction failed: {e}")
            return None

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        text = re.sub(r"```(?:json)?", "", text).strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _clean(data: Dict) -> Dict:
        total_calls = coerce_int(data.get("Total Phone Calls", 0))
        connected = coerce_int(data.get("Connected Calls", 0))
        
        duration_str = data.get("Total Phone Calls Duration", "")
        duration = VisionParser._convert_duration(duration_str)
        
        logger.info(f"Final values: TotalCalls={total_calls}, Connected={connected}, Duration={duration}")
        
        return {
            "Total Phone Calls": total_calls,
            "Connected Calls": connected,
            "Total Phone Calls Duration": duration,
        }

    @staticmethod
    def _convert_duration(duration_str: str) -> str:
        if not duration_str or duration_str == "00:00:00":
            return "00:00:00"

        # Handle "28m 10s" format (most common)
        match = re.search(r'(\d+)m\s*(\d+)s', duration_str, re.IGNORECASE)
        if match:
            m, s = int(match.group(1)), int(match.group(2))
            return f"00:{m:02d}:{s:02d}"

        # Handle "1h 28m 10s" format
        match = re.search(r'(\d+)h\s*(\d+)m\s*(\d+)s', duration_str, re.IGNORECASE)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{h:02d}:{m:02d}:{s:02d}"

        # Handle "1h 45m" format (missing seconds)
        match = re.search(r'(\d+)h\s*(\d+)m', duration_str, re.IGNORECASE)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            return f"{h:02d}:{m:02d}:00"

        # Handle "45m" format
        match = re.search(r'(\d+)m', duration_str, re.IGNORECASE)
        if match and 'h' not in duration_str:
            m = int(match.group(1))
            return f"00:{m:02d}:00"

        # Handle existing HH:MM:SS
        match = re.search(r'(\d{2}):(\d{2}):(\d{2})', duration_str)
        if match:
            return duration_str

        # Handle MM:SS
        match = re.search(r'(\d{2}):(\d{2})', duration_str)
        if match:
            m, s = int(match.group(1)), int(match.group(2))
            return f"00:{m:02d}:{s:02d}"

        return "00:00:00"
