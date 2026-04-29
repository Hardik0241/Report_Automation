"""
vision_parser.py — Parse Callyzer screenshot using Gemini Vision
Extracts: Total Phone Calls, Connected Calls, Total Phone Calls Duration
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

print("DEBUG: main.py is running", flush=True)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

_VISION_PROMPT = """
Analyse this Callyzer report screenshot carefully.

Return ONLY a JSON object with these exact keys - no markdown, no explanation:

{
  "Total Phone Calls": integer,
  "Connected Calls": integer,
  "Total Phone Calls Duration": "HH:MM:SS"
}

Look for:
- "Total Phone Calls" or "Outgoing Calls" or "Total Dialed" - this is the total number of calls made
- "Connected Calls" or "Premium Plus Connected Calls" - this is the number of successful connections
- Duration format like "1h 10m 7s" or "46m 55s" or "01:10:07"

Convert duration to HH:MM:SS format.
Use 0 for numbers you cannot clearly read.
Use "00:00:00" for duration you cannot read.
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
            if w < 800:
                scale = 800 / w
                new_size = (int(w * scale), int(h * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                img.save(tmp.name, 'JPEG', quality=95)
                temp_path = tmp.name

            try:
                response = self.model.generate_content([_VISION_PROMPT, temp_path])
                raw_text = response.text.strip()
                data = self._extract_json(raw_text)
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass

            if data is None:
                logger.warning(f"Could not parse JSON from vision response")
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
        # Convert integer fields
        data["Total Phone Calls"] = coerce_int(data.get("Total Phone Calls", 0))
        data["Connected Calls"] = coerce_int(data.get("Connected Calls", 0))

        # Convert duration
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

        # Handle Xh Ym Zs format
        match = re.search(r'(\d+)h\s*(\d+)m\s*(\d+)s', duration_str, re.IGNORECASE)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{h:02d}:{m:02d}:{s:02d}"

        # Handle Xh Ym format
        match = re.search(r'(\d+)h\s*(\d+)m', duration_str, re.IGNORECASE)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            return f"{h:02d}:{m:02d}:00"

        # Handle Ym Zs format
        match = re.search(r'(\d+)m\s*(\d+)s', duration_str, re.IGNORECASE)
        if match:
            m, s = int(match.group(1)), int(match.group(2))
            return f"00:{m:02d}:{s:02d}"

        # Handle HH:MM:SS format
        match = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', duration_str)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{h:02d}:{m:02d}:{s:02d}"

        # Handle MM:SS format
        match = re.search(r'(\d{1,2}):(\d{2})', duration_str)
        if match:
            m, s = int(match.group(1)), int(match.group(2))
            return f"00:{m:02d}:{s:02d}"

        return "00:00:00"
