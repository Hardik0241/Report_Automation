"""
vision_parser.py — Parse Callyzer screenshot using Gemini Vision.
Includes image pre-processing (contrast enhancement) and JSON fallback.
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
from PIL import Image, ImageEnhance, ImageFilter

from config import GEMINI_API_KEY, GEMINI_MODEL
from error_handler import ParsingError, with_retry
from utils import coerce_int, parse_duration

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

# Updated VISION PROMPT - Only 3 fields needed for Sales validation
_VISION_PROMPT = """
Analyse this Callyzer report screenshot carefully.

Return ONLY a JSON object with these exact keys - no markdown, no explanation:

{
  "Total Phone Calls": integer,
  "Connected Calls": integer,
  "Total Phone Calls Duration": "HH:MM:SS"
}

Rules:
- Extract "Total Phone Calls" value from the screenshot (look for "Total Phone Calls" or "Outgoing Calls" or "Total Dialed")
- Extract "Connected Calls" value from the screenshot (look for "Connected Calls" or "Premium Plus Connected Calls")
- Extract duration for Total Phone Calls section (format like "1h 10m 7s" or "46m 55s")
- Convert duration from "Xh Ym Zs" format to "HH:MM:SS" format
- Use 0 for any number you cannot clearly read.
- Use "00:00:00" for duration you cannot read.
- Do NOT guess - only report what you can clearly see.
"""


class VisionParser:
    def __init__(self):
        self.model = genai.GenerativeModel(GEMINI_MODEL)

    # ─────────────────────────────────────────
    # Public
    # ─────────────────────────────────────────

    @with_retry()
    def parse_screenshot(self, image_path: str) -> Optional[Dict]:
        """
        Parse a Callyzer screenshot.
        Returns a cleaned dict with Total Phone Calls, Connected Calls, and Duration.
        """
        logger.info(f"Starting screenshot parsing for: {image_path}")
        
        if not image_path or not os.path.exists(image_path):
            logger.warning(f"Screenshot not found: {image_path}")
            return None

        logger.info(f"Image file exists, size: {os.path.getsize(image_path)} bytes")
        
        # Try to load and process image
        try:
            # Load image with PIL
            img = Image.open(image_path)
            logger.info(f"Image loaded successfully: {img.size}, mode: {img.mode}")
            
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
                logger.info(f"Converted to RGB: {img.size}")

            # Simple upscale if too small
            w, h = img.size
            if w < 800:
                scale = 800 / w
                new_size = (int(w * scale), int(h * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"Image upscaled to: {img.size}")

            # Save to a temporary file to avoid PIL compatibility issues
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                img.save(tmp_file.name, 'JPEG', quality=95)
                temp_path = tmp_file.name
            
            logger.info(f"Image saved to temporary file: {temp_path}")
            
            # Now load from the temporary file for Gemini
            try:
                logger.info("Calling Gemini Vision API...")
                response = self.model.generate_content([_VISION_PROMPT, temp_path])
                raw_text = response.text.strip()
                logger.info(f"Vision API response received: {raw_text[:200]}...")
                data = self._extract_json(raw_text)
            except Exception as exc:
                logger.warning(f"Vision API call failed ({exc}); returning None.")
                return None
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                    logger.info("Temporary file cleaned up")
                except:
                    pass

        except Exception as exc:
            logger.error(f"Image processing failed: {exc}")
            return None

        if data is None:
            logger.warning(f"Could not parse JSON from vision response for {image_path}")
            return None

        logger.info(f"Successfully parsed screenshot data: {data}")
        return self._clean(data)

    # ─────────────────────────────────────────
    # Image pre-processing (kept for compatibility)
    # ─────────────────────────────────────────

    def _load_and_preprocess(self, path: str) -> Optional[Image.Image]:
        """
        Load image with minimal processing to avoid PIL compatibility issues.
        """
        try:
            img = Image.open(path)
            logger.info(f"Image loaded successfully: {img.size}, mode: {img.mode}")
            
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
                logger.info(f"Converted to RGB: {img.size}")

            # Simple upscale if too small
            w, h = img.size
            if w < 800:
                scale = 800 / w
                new_size = (int(w * scale), int(h * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"Image upscaled to: {img.size}")

            return img

        except Exception as exc:
            logger.error(f"Failed to load image: {exc}")
            return None

    # ─────────────────────────────────────────
    # JSON extraction + cleaning
    # ─────────────────────────────────────────

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
        """Clean and standardize extracted data for the 3 required fields"""
        
        # Convert integer fields
        int_fields = ["Total Phone Calls", "Connected Calls"]
        for field in int_fields:
            data[field] = coerce_int(data.get(field, 0))

        # Convert duration from various formats to HH:MM:SS
        def convert_duration(duration_str: str) -> str:
            if not duration_str or duration_str == "00:00:00":
                return "00:00:00"
            
            # Handle format like "1h 10m 7s" or "1h 10m" or "46m 55s"
            import re
            match = re.search(r'((\d+)h)?\s*((\d+)m)?\s*((\d+)s)?', duration_str)
            if match:
                hours = int(match.group(2) or 0)
                minutes = int(match.group(4) or 0)
                seconds = int(match.group(6) or 0)
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            # Handle existing HH:MM:SS format
            match = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', duration_str)
            if match:
                return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}:{int(match.group(3)):02d}"
            
            # Handle MM:SS format
            match = re.search(r'(\d{1,2}):(\d{2})', duration_str)
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                return f"00:{minutes:02d}:{seconds:02d}"
            
            return "00:00:00"

        # Process duration field
        data["Total Phone Calls Duration"] = convert_duration(data.get("Total Phone Calls Duration", ""))
        
        # Remove any extra fields that might have been added (like Connected Calls Duration)
        # Keep only the 3 fields we need
        result = {
            "Total Phone Calls": data.get("Total Phone Calls", 0),
            "Connected Calls": data.get("Connected Calls", 0),
            "Total Phone Calls Duration": data.get("Total Phone Calls Duration", "00:00:00")
        }
        
        return result
