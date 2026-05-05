"""
gemini_parser.py — Parse email body into structured data using Gemini.
"""

import json
import logging
import re
from typing import Dict, Optional

import warnings
warnings.filterwarnings('ignore', category=FutureWarning)
import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL
from error_handler import with_retry
from utils import coerce_int, normalize_employee_name, parse_duration, safe_title

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

_BASE_PROMPT = """
You are a data extraction assistant. Extract information from this daily work-report email.

Return ONLY a JSON object — no markdown, no explanation.

IMPORTANT: First determine if this is a SALES or HR report based on content.

For a SALES report, look for:
- "total dialed", "total dial", "dials", "total calls", "calls made"
- "connected", "conn", "total connected", "connected calls"  
- "duration", "dur", "talk time"
- "prospect", "prospects"

For an HR report, look for:
- "interview", "recruitment", "candidate", "screening", "lineup"
- "interview held", "interviews held", "held"
- "tomorrow interview lineups", "lineups"

For SALES report:
{
  "employee_name": "string or empty",
  "department": "Sales",
  "Total Dialed": integer,
  "Total Connected": integer,
  "Duration": "HH:MM:SS",
  "Prospect": integer
}

For HR report:
{
  "employee_name": "string or empty",
  "department": "HR",
  "Total Calls": integer,
  "Connected Calls": integer,
  "Duration": "HH:MM:SS",
  "Tomorrow Interview Lineups": integer,
  "Interview Held": integer
}

Rules:
- Use 0 for missing integer fields.
- Use "00:00:00" for missing duration.
- If the email is about calls/dialer numbers → Sales
- If the email is about interviews/recruitment → HR

Email content:
"""


class GeminiParser:
    def __init__(self):
        self.model = genai.GenerativeModel(GEMINI_MODEL)

    @with_retry()
    def parse_email(self, body: str) -> Optional[Dict]:
        if not body or not body.strip():
            logger.warning("Empty email body — skipping Gemini call.")
            return None

        prompt = _BASE_PROMPT + body[:5000]

        try:
            response = self.model.generate_content(prompt)
            raw_text = response.text.strip()
            data = self._extract_json(raw_text)
        except Exception as exc:
            logger.warning(f"Gemini call failed ({exc}); trying regex fallback.")
            data = None

        if data is None:
            logger.info("Using regex fallback parser.")
            data = self._fallback_parse(body)

        if data is None:
            return None

        return self._clean(data, body)

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

    def _clean(self, data: Dict, original_body: str) -> Dict:
        dept = data.get("department", "")
        if dept not in ("Sales", "HR"):
            dept = self._detect_department(original_body)
        data["department"] = dept

        raw_name = data.get("employee_name", "") or ""
        data["employee_name"] = normalize_employee_name(raw_name)

        if dept == "Sales":
            for field in ["Total Dialed", "Total Connected", "Prospect"]:
                data[field] = coerce_int(data.get(field, 0))
            data["Duration"] = parse_duration(data.get("Duration", ""))
            for k in ["Total Calls", "Connected Calls", "Tomorrow Interview Lineups", "Interview Held"]:
                data.pop(k, None)

        elif dept == "HR":
            for field in ["Total Calls", "Connected Calls", "Tomorrow Interview Lineups", "Interview Held"]:
                data[field] = coerce_int(data.get(field, 0))
            data["Duration"] = parse_duration(data.get("Duration", ""))
            for k in ["Total Dialed", "Total Connected", "Prospect"]:
                data.pop(k, None)

        return data

    @staticmethod
    def _detect_department(text: str) -> str:
        t = text.lower()
        
        # Check HR keywords FIRST (priority)
        hr_keywords = ["hr", "recruitment", "interview", "hiring", "lineup", "candidate", "screening", "interview held", "tomorrow interview"]
        for kw in hr_keywords:
            if kw in t:
                logger.info(f"Department detected: HR (keyword: '{kw}')")
                return "HR"
        
        # Then check Sales keywords
        sales_keywords = ["sales", "callyzer", "dialer", "prospect", "dialed", "dial", "outgoing", "total dialed", "total connected", "connected calls", "duration"]
        for kw in sales_keywords:
            if kw in t:
                logger.info(f"Department detected: Sales (keyword: '{kw}')")
                return "Sales"
        
        logger.info("Department detection: Unknown (no keywords found)")
        return "Unknown"

    def _fallback_parse(self, text: str) -> Optional[Dict]:
        dept = self._detect_department(text)
        dur = self._extract_duration_flexible(text)
        name = self._extract_name(text)

        def grab(keywords: list) -> int:
            for kw in keywords:
                kw_esc = re.escape(kw)
                pattern = rf"(?i){kw_esc}\s*[:\-=.]?\s*(\d+)"
                match = re.search(pattern, text)
                if match:
                    return int(match.group(1))
            return 0

        if dept == "Sales":
            return {
                "employee_name": name,
                "department": "Sales",
                "Total Dialed": grab(["total dial", "total dials", "total dialed", "total calls", "calls made", "dials"]),
                "Total Connected": grab(["total connected", "connected calls", "connected"]),
                "Duration": dur,
                "Prospect": grab(["prospect", "prospects"]),
            }

        elif dept == "HR":
            return {
                "employee_name": name,
                "department": "HR",
                # Fix: Look for "Total Dialed" AND "Total Calls" for HR
                "Total Calls": grab([
                    "total calls", "total dial", "total dials", "total dialed", 
                    "calls", "total connected", "connected calls"
                ]),
                "Connected Calls": grab([
                    "connected calls", "connected", "total connected", "conn"
                ]),
                "Duration": dur,
                # Fix: Look for various lineups formats
                "Tomorrow Interview Lineups": grab([
                    "tomorrow interview lineups", "interview lineups", 
                    "tomorrow lineups", "lineups", "total line ups for tomorrow",
                    "total line ups", "line ups for tomorrow", "lineups for tomorrow",
                    "total lineups for tomorrow", "tomorrow lineups count"
                ]),
                # Fix: Look for various interview held formats
                "Interview Held": grab([
                    "interview held", "interviews held", "held", "today held",
                    "today interview held", "interview done", "interviews done",
                    "today held interviews", "held interviews"
                ]),
            }

        return None

    @staticmethod
    def _extract_name(text: str) -> str:
        """
        Extract employee name from email body.
        Ignores common salutations like Dear, Hi, Hello, Kindly, etc.
        Also ignores email signatures and common phrases.
        """
        # List of words/phrases to ignore as name
        ignore_words = [
            'dear', 'hi', 'hello', 'kindly', 'please', 'thanks', 'thank', 
            'regards', 'sincerely', 'best', 'warm', 'good', 'morning',
            'afternoon', 'evening', 'hardik', 'sir', 'madam', 'team',
            'everyone', 'all', 'daily', 'report', 'calling', 'kra',
            'subject', 'forwarded', 'attachment', 'see', 'below',
            'attached', 'please find', 'here is', 'today\'s', 'sales',
            'hr', 'callyzer', 'dialer', 'total', 'connected', 'duration'
        ]
        
        for line in text.splitlines():
            line = line.strip()
            # Skip empty or very short lines
            if len(line) < 3:
                continue
            # Skip lines with numbers
            if re.search(r'\d', line):
                continue
            # Skip lines with colon, equals, dash (field:value patterns)
            if re.search(r'[:=\-]', line):
                continue
            # Skip lines that are too long (likely sentences)
            if len(line) > 50:
                continue
            # Skip lines that look like email addresses
            if '@' in line or '.' in line:
                continue
            # Check if line contains any ignore words
            line_lower = line.lower()
            if any(word in line_lower for word in ignore_words):
                continue
            # If we get here, this might be a name
            return line
        
        return ""

    @staticmethod
    def _extract_duration_flexible(text: str) -> str:
        m = re.search(r'\b(\d{1,3}:\d{2}:\d{2})\b', text)
        if m:
            return parse_duration(m.group(1))
        m = re.search(r'(\d+\s*h(?:r|rs)?\s*\d*\s*m(?:in|ins)?\s*\d*\s*s(?:ec|ecs)?)', text, re.IGNORECASE)
        if m:
            return parse_duration(m.group(1))
        m = re.search(r'\b(\d{1,3}:\d{2})\b', text)
        if m:
            return parse_duration(m.group(1))
        return "00:00:00"
