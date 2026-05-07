"""
gemini_parser.py — Parse email body into structured data using Gemini.
Handles extra text after values, flexible formats.
Sender email map takes priority over body keywords for department detection.
"""

import json
import logging
import re
from typing import Dict, Optional

import warnings
warnings.filterwarnings('ignore', category=FutureWarning)
import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL, SALES_EMAIL_MAP, HR_EMAIL_MAP
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
- "today held", "line ups for tomorrow"

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
- If the email contains HR keywords (interview, held, lineup) → HR
- If the email only contains call/dialer numbers → Sales

Email content:
"""


class GeminiParser:
    def __init__(self):
        self.model = genai.GenerativeModel(GEMINI_MODEL)

    @with_retry()
    def parse_email(self, body: str, sender_email: str = "") -> Optional[Dict]:
        """Parse email body with optional sender_email for department detection"""
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

        return self._clean(data, body, sender_email)

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

    def _clean(self, data: Dict, original_body: str, sender_email: str = "") -> Dict:
        dept = data.get("department", "")
        if dept not in ("Sales", "HR"):
            dept = self._detect_department(original_body, sender_email)
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
    def _detect_department(text: str, sender_email: str = "") -> str:
        t = text.lower()
        
        # PRIORITY 1: Check sender email map (MOST RELIABLE)
        if sender_email:
            sender_lower = sender_email.lower()
            # Check Sales email map
            for email in SALES_EMAIL_MAP.keys():
                if email.lower() == sender_lower:
                    logger.info(f"Department: Sales (from sender email: {sender_email})")
                    return "Sales"
            # Check HR email map
            for email in HR_EMAIL_MAP.keys():
                if email.lower() == sender_lower:
                    logger.info(f"Department: HR (from sender email: {sender_email})")
                    return "HR"
        
        # PRIORITY 2: Check HR keywords in email body
        hr_keywords = [
            "hr", "recruitment", "interview", "hiring", "lineup", 
            "candidate", "screening", "interview held", "tomorrow interview",
            "today held", "line ups for tomorrow", "total line ups", 
            "interview lineups", "held interviews", "held-"
        ]
        for kw in hr_keywords:
            if kw in t:
                logger.info(f"Department detected: HR (body keyword: '{kw}')")
                return "HR"
        
        # PRIORITY 3: Check Sales keywords in email body
        sales_keywords = [
            "sales", "callyzer", "dialer", "prospect", "dialed", "dial", 
            "outgoing", "total dialed", "total connected", "connected calls", 
            "duration", "total dial", "total calls", "calls made"
        ]
        for kw in sales_keywords:
            if kw in t:
                logger.info(f"Department detected: Sales (body keyword: '{kw}')")
                return "Sales"
        
        logger.info("Department detection: Unknown (no keywords found)")
        return "Unknown"

    def _fallback_parse(self, text: str) -> Optional[Dict]:
        dept = self._detect_department(text)
        dur = self._extract_duration_flexible(text)
        name = self._extract_name(text)

        def grab(keywords: list) -> int:
            """Extract first number after any keyword, ignoring extra text after the number"""
            for kw in keywords:
                kw_esc = re.escape(kw)
                # Multiple patterns to handle various formats
                patterns = [
                    rf"(?i){kw_esc}\s*[:\-=]?\s*(\d+)",           # Total Dialed: 134
                    rf"(?i){kw_esc}[:\-=]?\s*(\d+)",              # Total dial-134
                    rf"(?i){kw_esc}\s+(\d+)",                     # Total Dialed 134
                    rf"(?i){kw_esc}[\s]*[-:=][\s]*(\d+)",         # Total Dialed - 134
                    rf"(?i){kw_esc}\s*[:\-=]?\s*(\d+)\s*[^\d]",   # 134 followed by non-number
                ]
                for pattern in patterns:
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
                # Map "Total Dialed" to "Total Calls" for HR emails
                "Total Calls": grab([
                    "total calls", "total dial", "total dials", "total dialed", 
                    "calls", "total connected", "connected calls"
                ]),
                "Connected Calls": grab([
                    "connected calls", "connected", "total connected", "conn"
                ]),
                "Duration": dur,
                "Tomorrow Interview Lineups": grab([
                    "tomorrow interview lineups", "interview lineups", 
                    "tomorrow lineups", "lineups", "total line ups for tomorrow",
                    "total line ups", "line ups for tomorrow", "lineups for tomorrow",
                    "line ups", "lineups", "total lineups"
                ]),
                "Interview Held": grab([
                    "interview held", "interviews held", "held", "today held",
                    "today interview held", "interview done", "interviews done",
                    "held interviews", "today held interviews", "held-"
                ]),
            }

        return None

    @staticmethod
    def _extract_name(text: str) -> str:
        """Extract employee name from email body."""
        ignore_words = [
            'dear', 'hi', 'hello', 'kindly', 'please', 'thanks', 'thank', 
            'regards', 'sincerely', 'best', 'warm', 'good', 'morning',
            'afternoon', 'evening', 'hardik', 'sir', 'madam', 'team',
            'everyone', 'all', 'daily', 'report', 'calling', 'kra',
            'subject', 'forwarded', 'attachment', 'see', 'below',
            'attached', 'please find', 'here is', 'today\'s', 'sales',
            'hr', 'callyzer', 'dialer', 'total', 'connected', 'duration',
            'kindly check', 'bde', 'prospect', 'kfb', 'dear sir'
        ]
        
        for line in text.splitlines():
            line = line.strip()
            if len(line) < 3:
                continue
            if re.search(r'\d', line):
                continue
            if re.search(r'[:=\-]', line):
                continue
            if len(line) > 50:
                continue
            if '@' in line or '.' in line:
                continue
            line_lower = line.lower()
            if any(word in line_lower for word in ignore_words):
                continue
            # Clean up common prefixes
            line = re.sub(r'^(bde\s*-\s*)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'^(dear\s+sir\s*-\s*)', '', line, flags=re.IGNORECASE)
            return line
        
        return ""

    @staticmethod
    def _extract_duration_flexible(text: str) -> str:
        """Extract duration, ignoring extra text after it (like 'on hardik phone')"""
        # First, try to find duration pattern and capture only up to the time
        patterns = [
            r'(\d+\s*h(?:r|rs)?\s*\d*\s*m(?:in|ins)?\s*\d*\s*s(?:ec|ecs)?)',  # 1hr 53min
            r'(\d+\s*h(?:r|rs)?\s*\d*\s*m(?:in|ins)?)',                      # 1hr 53min (no seconds)
            r'(\d{1,3}:\d{2}:\d{2})',                                         # HH:MM:SS
            r'(\d{1,3}:\d{2})',                                               # MM:SS
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                duration_str = match.group(1)
                # Clean up the duration string
                duration_str = re.sub(r'\s+', ' ', duration_str.strip())
                return parse_duration(duration_str)
        
        return "00:00:00"
