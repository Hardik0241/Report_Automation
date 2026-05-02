"""
vision_parser.py — Parse Callyzer report screenshot correctly
Extracts: Total Phone Calls, Connected Calls, Duration (next to Total Calls)
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

# IMPROVED PROMPT - Duration is next to Total Phone Calls with stopwatch icon
_VISION_PROMPT = """
You are analyzing a Callyzer report screenshot. Look VERY carefully at the layout.

The screenshot shows a summary with this exact structure:

For "Total Phone Calls":
- The number (like 100) is the TOTAL CALLS
- RIGHT NEXT TO IT or BELOW IT is a stopwatch icon 🕐 and a duration (like "28m 10s" or "1h 10m 7s")
- This duration belongs to the Total Phone Calls

For "Connected Calls":
- Look for "Connected Calls" text
- The number next to it (like 27) is CONNECTED CALLS

Extract ONLY these 3 values:

1. "Total Phone Calls": The number next to "Total Phone Calls" text
2. "Total Phone Calls Duration": The time (with 🕐 icon) that appears RIGHT NEXT TO or BELOW Total Phone Calls
3. "Connected Calls": The number next to "Connected Calls" text

IMPORTANT RULES:
- The duration is ALWAYS associated with Total Phone Calls (not with Connected Calls)
- Look for a stopwatch icon 🕐 or text like "28m 10s", "57m 43s", "1h 10m 7s"
- Convert "28m 10s" to "00:28:10"
- Convert "1h 10m 7s" to "01:10:07"

For the example in the screenshot:
- Total Phone Calls should be 100
- Total Phone Calls Duration should be from the stopwatch icon (like "28m 10s" -> "00:28:10")
- Connected Calls should be 27

Return ONLY valid JSON:
{
  "Total Phone Calls": integer,
  "Connected Calls": integer,
  "Total Phone Calls Duration": "HH:MM:SS"
}

Use 0 for numbers you cannot see clearly.
Use "00:00:00" for duration you cannot see.
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
            
            # Crop to top 40% where the summary section is
            crop_height = int(h * 0.4)
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
                logger.warning("Could not parse JSON, returning None")
                return None

            return self._clean(data)

        except Exception as exc:
            logger.error(f"Image processing failed: {exc}")
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
        
        logger.info(f"Cleaned values: TotalCalls={total_calls}, Connected={connected}, Duration={duration}")
        
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

        # Handle "1h 28m" format
        match = re.search(r'(\d+)h\s*(\d+)m', duration_str, re.IGNORECASE)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            return f"{h:02d}:{m:02d}:00"

        # Handle HH:MM:SS format
        match = re.search(r'(\d{2}):(\d{2}):(\d{2})', duration_str)
        if match:
            return duration_str

        # Handle MM:SS format
        match = re.search(r'(\d{2}):(\d{2})', duration_str)
        if match:
            m, s = int(match.group(1)), int(match.group(2))
            return f"00:{m:02d}:{s:02d}"

        return "00:00:00"
