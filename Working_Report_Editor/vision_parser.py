"""
vision_parser.py — Parse Callyzer report screenshot correctly
Reads: Total Phone Calls (Outgoing Calls), Connected Calls, Duration
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

# Updated VISION PROMPT - More specific instructions
_VISION_PROMPT = """
You are analyzing a Callyzer call report screenshot. Extract ONLY these 3 values:

1. Total Phone Calls / Outgoing Calls - Look for "Outgoing Calls" or "Total Phone Calls" section. The number is usually large (80-100).
2. Connected Calls - Look for "Connected Calls" section. This is usually 40-60.
3. Duration - Look for the time next to "Total Phone Calls" or "Outgoing Calls". Format like "57m 43s" or "1h 10m 7s".

Do NOT read from "Unique Call", "Never Attended Calls", "Missed Calls", or any other sections.

Return ONLY valid JSON:
{
  "Total Phone Calls": integer,
  "Connected Calls": integer,
  "Total Phone Calls Duration": "HH:MM:SS"
}

If you cannot clearly see a value, use 0 for numbers and "00:00:00" for duration.
Do NOT guess. Only report what you see in the correct sections.
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

            # Upscale for better readability
            w, h = img.size
            if w < 1000:
                scale = 1000 / w
                new_size = (int(w * scale), int(h * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"Image upscaled to: {img.size}")

            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                img.save(tmp.name, 'JPEG', quality=95)
                temp_path = tmp.name

            try:
                logger.info("Calling Gemini Vision API...")
                response = self.model.generate_content([_VISION_PROMPT, temp_path])
                raw_text = response.text.strip()
                logger.info(f"Vision API response: {raw_text[:200]}")
                data = self._extract_json(raw_text)
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass

            if data is None:
                logger.warning("Could not parse JSON from vision response")
                return self._fallback_parse(image_path)

            return self._clean(data)

        except Exception as exc:
            logger.error(f"Image processing failed: {exc}")
            return None

    def _fallback_parse(self, image_path: str) -> Optional[Dict]:
        """Fallback parser using regex on image text"""
        logger.info("Using fallback parser")
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            logger.info(f"OCR extracted text: {text[:500]}")
            
            # Extract numbers using regex
            # Look for "Outgoing Calls" or pattern
            total_calls = 0
            connected_calls = 0
            duration_str = "00:00:00"
            
            # Find total calls (usually 2-3 digit number after "Outgoing Calls" or after "Total Phone Calls")
            match = re.search(r'Outgoing Calls[:\s]*(\d+)', text, re.IGNORECASE)
            if match:
                total_calls = int(match.group(1))
            
            # Find connected calls
            match = re.search(r'Connected Calls[:\s]*(\d+)', text, re.IGNORECASE)
            if match:
                connected_calls = int(match.group(1))
            
            # Find duration
            match = re.search(r'(\d+)h\s*(\d+)m\s*(\d+)s', text, re.IGNORECASE)
            if match:
                h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
                duration_str = f"{h:02d}:{m:02d}:{s:02d}"
            else:
                match = re.search(r'(\d+)m\s*(\d+)s', text, re.IGNORECASE)
                if match:
                    m, s = int(match.group(1)), int(match.group(2))
                    duration_str = f"00:{m:02d}:{s:02d}"
            
            return {
                "Total Phone Calls": total_calls,
                "Connected Calls": connected_calls,
                "Total Phone Calls Duration": duration_str
            }
        except Exception as e:
            logger.error(f"Fallback parse failed: {e}")
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
        data["Total Phone Calls"] = coerce_int(data.get("Total Phone Calls", 0))
        data["Connected Calls"] = coerce_int(data.get("Connected Calls", 0))
        
        duration_str = data.get("Total Phone Calls Duration", "")
        data["Total Phone Calls Duration"] = VisionParser._convert_duration(duration_str)
        
        return {
            "Total Phone Calls": data["Total Phone Calls"],
            "Connected Calls": data["Connected Calls"],
            "Total Phone Calls Duration": data["Total Phone Calls Duration"],
        }

    @staticmethod
    def _convert_duration(duration_str: str) -> str:
        if not duration_str or duration_str == "00:00:00":
            return "00:00:00"

        # Handle "57m 43s" format
        match = re.search(r'(\d+)m\s*(\d+)s', duration_str, re.IGNORECASE)
        if match:
            m, s = int(match.group(1)), int(match.group(2))
            return f"00:{m:02d}:{s:02d}"

        # Handle "1h 57m 43s" format
        match = re.search(r'(\d+)h\s*(\d+)m\s*(\d+)s', duration_str, re.IGNORECASE)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{h:02d}:{m:02d}:{s:02d}"

        # Handle existing HH:MM:SS
        match = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', duration_str)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{h:02d}:{m:02d}:{s:02d}"

        return "00:00:00"
