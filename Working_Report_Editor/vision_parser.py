"""
vision_parser.py — Parse Callyzer report screenshot correctly
Reads: Total Phone Calls, Connected Calls, and Total Phone Calls Duration
UPDATED: Changed from "Outgoing Calls" to "Total Phone Calls" section
UPDATED: Added delay between API calls to respect quota
UPDATED: Improved OCR fallback to read Total Phone Calls section
"""

import json
import logging
import os
import re
import time
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

# UPDATED PROMPT - Read from "Total Phone Calls" section (matches employee's "Total Dialed")
_VISION_PROMPT = """
You are analyzing a Callyzer report screenshot. Extract data from the "Total Phone Calls" section.

IMPORTANT: Look for these EXACT sections:

1. "Total Phone Calls" - The number next to or below this is TOTAL DIALED
2. Next to the stopwatch icon 🕐 or below "Total Phone Calls", find the DURATION (e.g., "1h 33m 33s")
3. "Connected Calls" - The number next to or below this is CONNECTED CALLS

For the example screenshot:
- Total Phone Calls = 110
- Total Phone Calls Duration = "1h 33m 33s" → convert to "01:33:33"
- Connected Calls = 55

Return ONLY valid JSON:
{
  "Total Phone Calls": integer,
  "Connected Calls": integer,
  "Total Phone Calls Duration": "HH:MM:SS"
}

RULES:
- Duration format: "1h 33m 33s" → "01:33:33"
- Duration format: "28m 10s" → "00:28:10"
- Duration format: "1h 45m" → "01:45:00"
- Use 0 if you cannot find a number
- Use "00:00:00" if you cannot find duration

DO NOT read from "Outgoing Calls", "Incoming Calls", or "Missed Calls" sections.
"""


class VisionParser:
    def __init__(self):
        self.model = genai.GenerativeModel(GEMINI_MODEL)
        self._last_api_call_time = 0
        self._min_delay_seconds = 15  # Delay between Vision API calls to respect quota

    def _wait_for_quota(self):
        """Wait to avoid hitting rate limits"""
        now = time.time()
        elapsed = now - self._last_api_call_time
        if elapsed < self._min_delay_seconds:
            wait_time = self._min_delay_seconds - elapsed
            logger.info(f"Waiting {wait_time:.1f}s to respect Vision API quota...")
            time.sleep(wait_time)
        self._last_api_call_time = time.time()

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
            
            # Focus on the Total Phone Calls section (typically 0-50% of image)
            crop_bottom = int(h * 0.50)
            img = img.crop((0, 0, w, crop_bottom))
            logger.info(f"Cropped to Total Phone Calls section: {img.size}")

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
                # Wait for quota before API call
                self._wait_for_quota()
                
                logger.info("Calling Gemini Vision API (focused on Total Phone Calls)...")
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
                logger.warning("Could not parse JSON, using fallback OCR focused on Total Phone Calls")
                return self._fallback_extraction(img)

            cleaned_data = self._clean(data)
            return cleaned_data

        except Exception as exc:
            if "429" in str(exc):
                logger.warning(f"Quota exceeded, waiting longer before retry...")
                time.sleep(30)
            else:
                logger.error(f"Image processing failed: {exc}")
            return None

    def _fallback_extraction(self, img: Image.Image) -> Optional[Dict]:
        """Fallback using OCR - specifically looks for Total Phone Calls section"""
        try:
            import pytesseract
            text = pytesseract.image_to_string(img)
            logger.info(f"OCR extracted text: {text[:500]}")
            
            # Look for Total Phone Calls section
            # Pattern: "Total Phone Calls" followed by number and duration
            total_match = re.search(r'Total\s+Phone\s+Calls[^\d]*(\d+)[^\d]*([\d\s]+[hms]+[\d\s]+[hms]*)', text, re.IGNORECASE | re.DOTALL)
            
            total_calls = 0
            duration = "00:00:00"
            
            if total_match:
                total_calls = int(total_match.group(1))
                duration_text = total_match.group(2)
                
                # Parse duration from text
                # Pattern for "1h 33m 33s"
                duration_match = re.search(r'(\d+)\s*h\s*(\d+)\s*m\s*(\d+)\s*s', duration_text, re.IGNORECASE)
                if duration_match:
                    h, m, s = int(duration_match.group(1)), int(duration_match.group(2)), int(duration_match.group(3))
                    duration = f"{h:02d}:{m:02d}:{s:02d}"
                else:
                    # Pattern for "33m 33s"
                    duration_match = re.search(r'(\d+)\s*m\s*(\d+)\s*s', duration_text, re.IGNORECASE)
                    if duration_match:
                        m, s = int(duration_match.group(1)), int(duration_match.group(2))
                        duration = f"00:{m:02d}:{s:02d}"
                    else:
                        # Pattern for just minutes "33m"
                        duration_match = re.search(r'(\d+)\s*m', duration_text, re.IGNORECASE)
                        if duration_match:
                            m = int(duration_match.group(1))
                            duration = f"00:{m:02d}:00"
            
            # Extract Connected Calls
            connected_match = re.search(r'Connected\s+Calls[^\d]*(\d+)', text, re.IGNORECASE)
            connected = int(connected_match.group(1)) if connected_match else 0
            
            logger.info(f"OCR fallback: TotalCalls={total_calls}, Connected={connected}, Duration={duration}")
            
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

        # Handle "1h 33m 33s" format
        match = re.search(r'(\d+)h\s*(\d+)m\s*(\d+)s', duration_str, re.IGNORECASE)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{h:02d}:{m:02d}:{s:02d}"

        # Handle "33m 33s" format
        match = re.search(r'(\d+)m\s*(\d+)s', duration_str, re.IGNORECASE)
        if match:
            m, s = int(match.group(1)), int(match.group(2))
            return f"00:{m:02d}:{s:02d}"

        # Handle "1h 33m" format (no seconds)
        match = re.search(r'(\d+)h\s*(\d+)m', duration_str, re.IGNORECASE)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            return f"{h:02d}:{m:02d}:00"

        # Handle "33m" format
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
