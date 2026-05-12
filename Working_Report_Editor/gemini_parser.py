"""
gemini_parser.py — Parse email body into structured data using Gemini.
UPDATED: Enhanced fallback for Sales duration parsing and "Leave" detection
UPDATED: Fixed duration extraction for proper hour/minute/second capture
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
- "total dialed", "total dial", "dials", "total calls", "calls made", "dial"
- "connected", "conn", "total connected", "connected calls"  
- "duration", "dur", "talk time", "time"
- "prospect", "prospects", "pros"
- BDE name patterns: "BDE Name:", "BDE -", "BDE:"

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
- If the email contains "Leave" or "leave" anywhere, mark as "Leave" and skip.
- Duration can be in formats: "1h 0m 35s", "1H 15M + 14M", "1 H 31 M", "1hr 25m 21s"

Email content:
"""


class GeminiParser:
    def __init__(self):
        self.model = genai.GenerativeModel(GEMINI_MODEL)

    @with_retry()
    def parse_email(self, body: str, sender_email: str = "") -> Optional[Dict]:
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
        
        if sender_email:
            sender_lower = sender_email.lower()
            for email in SALES_EMAIL_MAP.keys():
                if email.lower() == sender_lower:
                    logger.info(f"Department: Sales (from sender email: {sender_email})")
                    return "Sales"
            for email in HR_EMAIL_MAP.keys():
                if email.lower() == sender_lower:
                    logger.info(f"Department: HR (from sender email: {sender_email})")
                    return "HR"
        
        # Check for "Leave" first
        if 'leave' in t:
            logger.info(f"Department: Sales (Leave detected)")
            return "Sales"
        
        # Sales keywords (more comprehensive)
        sales_keywords = [
            "sales", "callyzer", "dialer", "prospect", "dialed", "dial", 
            "outgoing", "total dialed", "total connected", "connected calls", 
            "duration", "total dial", "total calls", "calls made",
            "bde", "bde name", "bde -", "prospects"
        ]
        for kw in sales_keywords:
            if kw in t:
                logger.info(f"Department detected: Sales (body keyword: '{kw}')")
                return "Sales"
        
        # HR keywords
        hr_keywords = [
            "hr", "recruitment", "interview", "hiring", "lineup", 
            "candidate", "screening", "interview held", "tomorrow interview",
            "today held", "line ups for tomorrow", "total line ups", 
            "interview lineups", "held interviews", "held-",
            "today held", "today interview held"
        ]
        for kw in hr_keywords:
            if kw in t:
                logger.info(f"Department detected: HR (body keyword: '{kw}')")
                return "HR"
        
        logger.info("Department detection: Unknown (no keywords found)")
        return "Unknown"

    def _fallback_parse(self, text: str) -> Optional[Dict]:
        # Check for "Leave" first
        if 'leave' in text.lower():
            return {
                "employee_name": self._extract_name(text),
                "department": "Sales",
                "Total Dialed": 0,
                "Total Connected": 0,
                "Duration": "00:00:00",
                "Prospect": 0,
            }
        
        dept = self._detect_department(text)
        dur = self._extract_duration_flexible(text)
        name = self._extract_name(text)

        def grab(keywords: list) -> int:
            for kw in keywords:
                kw_esc = re.escape(kw)
                patterns = [
                    rf"(?i){kw_esc}\s*[:\-=]?\s*([\d\s\+]+)",
                    rf"(?i){kw_esc}[:\-=]?\s*([\d\s\+]+)",
                    rf"(?i){kw_esc}\s+([\d\s\+]+)",
                    rf"(?i){kw_esc}[\s]*[-:=][\s]*([\d\s\+]+)",
                    rf"(?i){kw_esc}\s*[:\-=]?\s*(\d+(?:\s*\+\s*\d+)*)",
                ]
                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        value_str = match.group(1)
                        # Handle addition like "126+10", "163 + 4"
                        if '+' in value_str:
                            parts = re.split(r'\s*\+\s*', value_str)
                            total = 0
                            for part in parts:
                                nums = re.findall(r'\d+', part)
                                if nums:
                                    total += int(nums[0])
                            return total
                        nums = re.findall(r'\d+', value_str)
                        if nums:
                            return int(nums[0])
            return 0

        if dept == "Sales":
            return {
                "employee_name": name,
                "department": "Sales",
                "Total Dialed": grab([
                    "total dial", "total dials", "total dialed", "total calls", 
                    "calls made", "dials", "dial", "total dial", "dial"
                ]),
                "Total Connected": grab([
                    "total connected", "connected calls", "connected", 
                    "conn", "connect", "total connected"
                ]),
                "Duration": dur,
                "Prospect": grab([
                    "prospect", "prospects", "pros", "prspct"
                ]),
            }

        elif dept == "HR":
            return {
                "employee_name": name,
                "department": "HR",
                "Total Calls": grab([
                    "total dialed", "total dial", "total calls", "dialed",
                    "calls", "dial", "total connected", "connected calls"
                ]),
                "Connected Calls": grab([
                    "connected calls", "connected", "total connected", "conn", "connect"
                ]),
                "Duration": dur,
                "Tomorrow Interview Lineups": grab([
                    "tomorrow interview lineups", "interview lineups", 
                    "tomorrow lineups", "lineups", "total line ups for tomorrow",
                    "total line ups", "line ups for tomorrow", "lineups for tomorrow",
                    "line ups", "lineups", "total lineups", "line up for tomorrow",
                    "total line up for tomorrow", "tomorrow line up"
                ]),
                "Interview Held": grab([
                    "interview held", "interviews held", "held", "today held",
                    "today interview held", "interview done", "interviews done",
                    "held interviews", "today held interviews", "held-",
                    "today held-", "today held interview"
                ]),
            }

        return None

    @staticmethod
    def _extract_name(text: str) -> str:
        # First try to find BDE Name pattern
        bde_patterns = [
            r'BDE[:\s-]+\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)',
            r'BDE Name[:\s-]+\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)',
            r'Name[:\s-]+\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)',
        ]
        for pattern in bde_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        ignore_words = [
            'dear', 'hi', 'hello', 'kindly', 'please', 'thanks', 'thank', 
            'regards', 'sincerely', 'best', 'warm', 'good', 'morning',
            'afternoon', 'evening', 'hardik', 'sir', 'madam', 'team',
            'everyone', 'all', 'daily', 'report', 'calling', 'kra',
            'subject', 'forwarded', 'attachment', 'see', 'below',
            'attached', 'please find', 'here is', 'today\'s', 'sales',
            'hr', 'callyzer', 'dialer', 'total', 'connected', 'duration',
            'kindly check', 'bde', 'prospect', 'kfb', 'dear sir', 'bde -',
            'calling', 'prospect', 'edujam', 'gmail', 'com'
        ]
        
        for line in text.splitlines():
            line = line.strip()
            if len(line) < 3:
                continue
            if re.search(r'\d', line):
                continue
            if re.search(r'[:=\-@.]', line):
                continue
            if len(line) > 50:
                continue
            line_lower = line.lower()
            if any(word in line_lower for word in ignore_words):
                continue
            line = re.sub(r'^(bde\s*-\s*)', '', line, flags=re.IGNORECASE)
            line = re.sub(r'^(dear\s+sir\s*-\s*)', '', line, flags=re.IGNORECASE)
            if line.strip():
                return line
        
        return ""

    @staticmethod
    def _extract_duration_flexible(text: str) -> str:
        """Extract duration from text - FIXED for proper hour/minute/second capture"""
        # First, check for "Leave"
        if 'leave' in text.lower():
            return "00:00:00"
        
        # Pattern for "1h 43m 32s" or "1hr 54m 14s"
        match = re.search(r'(\d+)\s*h(?:r)?\s*(\d+)\s*m\s*(\d+)\s*s', text, re.IGNORECASE)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{h:02d}:{m:02d}:{s:02d}"
        
        # Pattern for "1h 43m" (hours and minutes only)
        match = re.search(r'(\d+)\s*h(?:r)?\s*(\d+)\s*m', text, re.IGNORECASE)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            return f"{h:02d}:{m:02d}:00"
        
        # Pattern for "53m 7s" (minutes and seconds)
        match = re.search(r'(\d+)\s*m\s*(\d+)\s*s', text, re.IGNORECASE)
        if match:
            m, s = int(match.group(1)), int(match.group(2))
            return f"00:{m:02d}:{s:02d}"
        
        # Pattern for "56m" (just minutes)
        match = re.search(r'(\d+)\s*m', text, re.IGNORECASE)
        if match:
            m = int(match.group(1))
            return f"00:{m:02d}:00"
        
        # Pattern for "Duration: 1h 43m 32s"
        match = re.search(r'Duration[:\s-]+\s*(\d+)\s*h(?:r)?\s*(\d+)\s*m\s*(\d+)\s*s', text, re.IGNORECASE)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{h:02d}:{m:02d}:{s:02d}"
        
        return "00:00:00"
