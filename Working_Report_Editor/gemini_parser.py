"""
gemini_parser.py — Parse email body into structured data using Gemini.
UPDATED: Fixed HR regex for "Total Line ups for tomorrow" (plural, dash, colon)
UPDATED: Fixed duration extraction for HH:MM:SS format with dash and dots
UPDATED: Added support for "sec" as seconds identifier (e.g., 8sec, 42m 8sec)
UPDATED: Added support for "total dialled" (double L) spelling variation
UPDATED: Improved call number extraction precision
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
- "total dialed", "total dial", "total dialled", "dials", "total calls", "calls made", "dial"
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
- Duration can be in formats: "1h 0m 35s", "1H 15M + 14M", "1 H 31 M", "1hr 25m 21s", "01:28:52", "02.07.36", "2.08.32", "1h 42m 8sec"

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

        data = None
        try:
            response = self.model.generate_content(prompt)
            raw_text = response.text.strip()
            data = self._extract_json(raw_text)
        except Exception as exc:
            if "429" in str(exc) or "quota" in str(exc).lower():
                logger.warning(f"⚠️ Gemini API quota exceeded - using regex fallback parser")
            else:
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
        
        if 'leave' in t:
            logger.info(f"Department: Sales (Leave detected)")
            return "Sales"
        
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
        
        sales_keywords = [
            "sales", "dialer", "prospect", "dialed", "dial", "dialled",
            "outgoing", "total dialed", "total connected", "connected calls", 
            "duration", "total dial", "total calls", "calls made",
            "bde", "bde name", "bde -", "prospects"
        ]
        for kw in sales_keywords:
            if kw in t:
                logger.info(f"Department detected: Sales (body keyword: '{kw}')")
                return "Sales"
        
        logger.info("Department detection: Unknown (no keywords found)")
        return "Unknown"

    def _fallback_parse(self, text: str) -> Optional[Dict]:
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

        def grab_number(keywords: list) -> int:
            for kw in keywords:
                kw_esc = re.escape(kw)
                patterns = [
                    rf"(?i){kw_esc}[\s]*[:=-][\s]*(\d+(?:\s*\+\s*\d+)*)",
                    rf"(?i){kw_esc}[\s]*:[\s]*(\d+(?:\s*\+\s*\d+)*)",
                    rf"(?i){kw_esc}[\s]*-[\s]*(\d+(?:\s*\+\s*\d+)*)",
                    rf"(?i){kw_esc}\s+(\d+(?:\s*\+\s*\d+)*)",
                    rf"(?i){kw_esc}:(\d+(?:\s*\+\s*\d+)*)",
                    rf"(?i){kw_esc}-(\d+(?:\s*\+\s*\d+)*)",
                    rf"(?i){kw_esc}:-(\d+(?:\s*\+\s*\d+)*)",
                ]
                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        value_str = match.group(1)
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

        def grab_duration(keywords: list) -> str:
            for kw in keywords:
                kw_esc = re.escape(kw)
                
                pattern_time = rf"(?i){kw_esc}[\s]*[:=-][\s]*(\d{{2}}:\d{{2}}:\d{{2}})"
                match = re.search(pattern_time, text)
                if match:
                    return match.group(1)
                
                pattern_dots_two = rf"(?i){kw_esc}[\s]*[:=-][\s]*(\d{{2}}\.\d{{2}}\.\d{{2}})"
                match = re.search(pattern_dots_two, text)
                if match:
                    return match.group(1).replace('.', ':')
                
                pattern_dots_one = rf"(?i){kw_esc}[\s]*[:=-][\s]*(\d{{1}}\.\d{{2}}\.\d{{2}})"
                match = re.search(pattern_dots_one, text)
                if match:
                    return match.group(1).replace('.', ':')
                
                pattern_time_colon = rf"(?i){kw_esc}[\s]*:[\s]*(\d{{2}}:\d{{2}}:\d{{2}})"
                match = re.search(pattern_time_colon, text)
                if match:
                    return match.group(1)
                
                # Handle text format with "sec" (e.g., 1h 42m 8sec)
                pattern_text_sec = rf"(?i){kw_esc}[\s]*[:=-][\s]*(\d+\s*h(?:r)?s?\s*\d+\s*m(?:in)?s?\s*\d+\s*sec)"
                match = re.search(pattern_text_sec, text)
                if match:
                    return match.group(1).strip()
                
                pattern_text = rf"(?i){kw_esc}[\s]*[:=-][\s]*([\d\s]+[hms]+[\d\s]+[hms]*[\d\s]*[hms]*)"
                match = re.search(pattern_text, text)
                if match:
                    return match.group(1).strip()
                
                pattern_text_space = rf"(?i){kw_esc}\s+([\d\s]+[hms]+[\d\s]+[hms]*[\d\s]*[hms]*)"
                match = re.search(pattern_text_space, text)
                if match:
                    return match.group(1).strip()
            
            return "00:00:00"

        if dept == "Sales":
            total_dialed = grab_number([
                "total dial", "total dials", "total dialed", "total dialled",
                "total calls", "calls made", "dials", "dial"
            ])
            total_connected = grab_number([
                "total connected", "connected calls", "connected", 
                "conn", "connect"
            ])
            prospect = grab_number([
                "prospect", "prospects", "pros"
            ])
            
            duration = grab_duration([
                "duration", "dur", "talk time", "time"
            ])
            if duration and duration != "00:00:00" and ':' not in duration and '.' not in duration:
                duration = parse_duration(duration)
            
            return {
                "employee_name": name,
                "department": "Sales",
                "Total Dialed": total_dialed,
                "Total Connected": total_connected,
                "Duration": duration,
                "Prospect": prospect,
            }

        elif dept == "HR":
            total_calls = grab_number([
                "total dialed", "total dial", "total calls", "dialed", "calls", "dial"
            ])
            connected_calls = grab_number([
                "connected", "connected calls", "total connected", "conn", "connect"
            ])
            
            duration = grab_duration([
                "duration", "dur", "talk time", "time"
            ])
            if duration and duration != "00:00:00" and ':' not in duration and '.' not in duration:
                duration = parse_duration(duration)
            
            lineups = 0
            lineup_patterns = [
                r"(?i)total[\s]+line[\s]+ups?[\s]+for[\s]+tomorrow[\s]*[-:][\s]*(\d+)",
                r"(?i)total[\s]+line[\s]+ups?[\s]+for[\s]+tomorrow[\s]*:[\s]*(\d+)",
                r"(?i)total[\s]+line[\s]+ups?[\s]+for[\s]+tomorrow[\s]+(\d+)",
                r"(?i)line[\s]+ups?[\s]+for[\s]+tomorrow[\s]*[-:][\s]*(\d+)",
                r"(?i)total[\s]+line[\s]+ups?[\s]+for[\s]+tomorrow-[\s]*(\d+)",
                r"(?i)total line ups? for tomorrow[\s]*[-:]?\s*(\d+)",
                r"(?i)lineups?[\s]*:[\s]*(\d+)",
            ]
            for pattern in lineup_patterns:
                match = re.search(pattern, text)
                if match:
                    lineups = int(match.group(1))
                    logger.info(f"HR Lineups extracted: {lineups} using pattern: {pattern}")
                    break
            
            held = 0
            held_patterns = [
                r"(?i)today[\s]+held[\s]*-[\s]*(\d+)",
                r"(?i)today[\s]+held[\s]*:[\s]*(\d+)",
                r"(?i)today[\s]+held[\s]+(\d+)",
                r"(?i)today[\s]+interview[\s]+held[\s]*-[\s]*(\d+)",
                r"(?i)interview[\s]+held[\s]*:[\s]*(\d+)",
                r"(?i)held[\s]*-[\s]*(\d+)",
                r"(?i)held[\s]*:[\s]*(\d+)",
                r"(?i)held-[\s]*(\d+)",
            ]
            for pattern in held_patterns:
                match = re.search(pattern, text)
                if match:
                    held = int(match.group(1))
                    logger.info(f"HR Held extracted: {held} using pattern: {pattern}")
                    break
            
            return {
                "employee_name": name,
                "department": "HR",
                "Total Calls": total_calls,
                "Connected Calls": connected_calls,
                "Duration": duration,
                "Tomorrow Interview Lineups": lineups,
                "Interview Held": held,
            }

        return None

    @staticmethod
    def _extract_name(text: str) -> str:
        bde_patterns = [
            r'BDE[:\s-]+\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)',
            r'BDE Name[:\s-]+\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)',
            r'BDE NAME[:\s-]+\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)',
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
            'hr', 'dialer', 'total', 'connected', 'duration',
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
        if 'leave' in text.lower():
            return "00:00:00"
        
        match = re.search(r'(\d{2}):(\d{2}):(\d{2})', text)
        if match:
            return match.group(0)
        
        # Handle HH.MM.SS with two-digit hour
        match = re.search(r'(\d{2})\.(\d{2})\.(\d{2})', text)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{h:02d}:{m:02d}:{s:02d}"
        
        # Handle H.MM.SS with single-digit hour (e.g., 2.08.32)
        match = re.search(r'(\d{1})\.(\d{2})\.(\d{2})', text)
        if match:
            h = int(match.group(1))
            m = int(match.group(2))
            s = int(match.group(3))
            return f"{h:02d}:{m:02d}:{s:02d}"
        
        # Handle "1h 42m 8sec" format
        match = re.search(r'(\d+)\s*h(?:r)?\s*(\d+)\s*m\s*(\d+)\s*sec', text, re.IGNORECASE)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{h:02d}:{m:02d}:{s:02d}"
        
        match = re.search(r'(\d+)\s*h(?:r)?\s*(\d+)\s*m\s*(\d+)\s*s', text, re.IGNORECASE)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{h:02d}:{m:02d}:{s:02d}"
        
        match = re.search(r'(\d+)\s*h(?:r)?\s*(\d+)\s*m', text, re.IGNORECASE)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            return f"{h:02d}:{m:02d}:00"
        
        match = re.search(r'(\d+)\s*m\s*(\d+)\s*s', text, re.IGNORECASE)
        if match:
            m, s = int(match.group(1)), int(match.group(2))
            return f"00:{m:02d}:{s:02d}"
        
        match = re.search(r'(\d+)\s*m', text, re.IGNORECASE)
        if match:
            m = int(match.group(1))
            return f"00:{m:02d}:00"
        
        return "00:00:00"
