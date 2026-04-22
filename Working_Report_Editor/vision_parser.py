"""
vision_parser.py — Parse Callyzer screenshot using Gemini Vision.
Includes image pre-processing (contrast enhancement) and JSON fallback.
"""

import json
import logging
import os
import re
from typing import Dict, Optional

import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageFilter

from config import GEMINI_API_KEY, GEMINI_MODEL
from error_handler import ParsingError, with_retry
from utils import coerce_int, parse_duration

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

_VISION_PROMPT = """
Analyse this Callyzer report screenshot carefully.

Return ONLY a JSON object with these exact keys - no markdown, no explanation:

{
  "Total Phone Calls": integer,
  "Connected Calls": integer,
  "Total Phone Calls Duration": "HH:MM:SS",
  "Connected Calls Duration": "HH:MM:SS"
}

Rules:
- Extract "Total Phone Calls" value from the Total Phone Calls section
- Extract "Connected Calls" value from the Connected Calls section  
- Extract duration for Total Phone Calls section (format like "1h 45m 34s")
- Extract duration for Connected Calls section if available
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
        Returns a cleaned dict, or None if parsing fails completely.
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
            logger.warning(f"Raw response was: {raw_text}")
            return None

        logger.info(f"Successfully parsed screenshot data: {data}")
        return self._clean(data)

    # ─────────────────────────────────────────
    # Image pre-processing
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
        text  = re.sub(r"```(?:json)?", "", text).strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _clean(data: Dict) -> Dict:
        int_fields = [
            "Total Phone Calls", "Connected Calls"
        ]
        for field in int_fields:
            data[field] = coerce_int(data.get(field, 0))

        # Handle duration format conversion from "1h 45m 34s" to "HH:MM:SS"
        def convert_duration(duration_str: str) -> str:
            if not duration_str or duration_str == "00:00:00":
                return "00:00:00"
            
            # Handle format like "1h 45m 34s"
            import re
            match = re.search(r'((\d+)h)?\s*((\d+)m)?\s*((\d+)s)?', duration_str)
            if match:
                hours = int(match.group(1) or 0)
                minutes = int(match.group(2) or 0)
                seconds = int(match.group(3) or 0)
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            # Handle existing HH:MM:SS format
            match = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', duration_str)
            if match:
                return duration_str
            
            return "00:00:00"

        data["Total Phone Calls Duration"] = convert_duration(data.get("Total Phone Calls Duration", ""))
        data["Connected Calls Duration"] = convert_duration(data.get("Connected Calls Duration", ""))
        
        return data
