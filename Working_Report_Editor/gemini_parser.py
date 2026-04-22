"""
gemini_parser.py — Parse email body into structured data using Gemini.

Key changes vs previous version:
  • Flexible keyword matching for field names (dial, conn, pros, dur, etc.)
  • Handles missing ':' separator between field name and value
  • Flexible duration parsing (1hr, 1h 20m, 20m 45sec, etc.)
  • Name/department are OPTIONAL — pipeline falls back to sender email map
  • Regex fallback covers all messy real-world formats
"""

import json
import logging
import re
from typing import Dict, Optional

import google.generativeai as genai

from config import DEPARTMENT_KEYWORDS, GEMINI_API_KEY, GEMINI_MODEL
from error_handler import with_retry
from utils import coerce_int, normalize_employee_name, parse_duration, safe_title

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

_BASE_PROMPT = """
You are a data extraction assistant. Extract information from this daily work-report email.

Return ONLY a JSON object — no markdown, no explanation.

IMPORTANT: The sender may use informal/short names for fields. Map them as follows:
- "total dials", "total dial", "dials", "total calls", "calls made" → "Total Dialed" (Sales) or "Total Calls" (HR)
- "connected", "conn", "cnct", "total connected", "connected calls" → "Total Connected" (Sales) or "Connected Calls" (HR)
- "duration", "dur", "time", "talk time", "call time", "total time" → "Duration"
- "prospect", "prospects", "pros", "prspct" → "Prospect"
- "interview lineups", "lineups", "tomorrow lineups" → "Tomorrow Interview Lineups"
- "interview held", "interviews held", "held" → "Interview Held"

Duration may be written as: "1hr", "1h 20m", "20m 45sec", "1:20:45", "00:36:35", "36:35", etc.
Always convert duration to HH:MM:SS format.

The field name and value may be separated by ":", "=", "-", " " or nothing at all.
Example: "Total Dials 42" or "Dials:42" or "Dials = 42" — all are valid.

For a SALES report:
{
  "employee_name": "string or empty string if not found",
  "department": "Sales",
  "Total Dialed": integer,
  "Total Connected": integer,
  "Duration": "HH:MM:SS",
  "Prospect": integer
}

For an HR report:
{
  "employee_name": "string or empty string if not found",
  "department": "HR",
  "Total Calls": integer,
  "Connected Calls": integer,
  "Duration": "HH:MM:SS",
  "Tomorrow Interview Lineups": integer,
  "Interview Held": integer
}

Rules:
- Use 0 for any missing integer field.
- Use "00:00:00" for missing duration.
- If you cannot determine the department, use "Unknown".
- If you cannot find the employee name, use an empty string "".

Email content:
"""


class GeminiParser:
    def __init__(self):
        self.model = genai.GenerativeModel(GEMINI_MODEL)

    # ──────────────────────────────────────
    # Public
    # ──────────────────────────────────────

    @with_retry()
    def parse_email(self, body: str) -> Optional[Dict]:
        """Parse email body. Returns cleaned dict or None on hard failure."""
        if not body or not body.strip():
            logger.warning("Empty email body — skipping Gemini call.")
            return None

        prompt = _BASE_PROMPT + body[:5000]

        try:
            response = self.model.generate_content(prompt)
            raw_text = response.text.strip()
            data     = self._extract_json(raw_text)
        except Exception as exc:
            logger.warning(f"Gemini call failed ({exc}); trying regex fallback.")
            data = None

        if data is None:
            logger.info("Using regex fallback parser.")
            data = self._fallback_parse(body)

        if data is None:
            return None

        return self._clean(data, body)

    # ──────────────────────────────────────
    # JSON extraction
    # ──────────────────────────────────────

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

    # ──────────────────────────────────────
    # Cleaning / normalisation
    # ──────────────────────────────────────

    def _clean(self, data: Dict, original_body: str) -> Dict:
        # Department: validate + fallback to keyword detection
        dept = data.get("department", "")
        if dept not in ("Sales", "HR"):
            dept = self._detect_department(original_body)
        data["department"] = dept

        # Employee name — optional, normalise if present
        raw_name = data.get("employee_name", "") or ""
        data["employee_name"] = normalize_employee_name(raw_name)

        if dept == "Sales":
            for field in ["Total Dialed", "Total Connected", "Prospect"]:
                data[field] = coerce_int(data.get(field, 0))
            data["Duration"] = parse_duration(data.get("Duration", ""))
            for k in ["Total Calls", "Connected Calls",
                      "Tomorrow Interview Lineups", "Interview Held"]:
                data.pop(k, None)

        elif dept == "HR":
            for field in ["Total Calls", "Connected Calls",
                          "Tomorrow Interview Lineups", "Interview Held"]:
                data[field] = coerce_int(data.get(field, 0))
            data["Duration"] = parse_duration(data.get("Duration", ""))
            for k in ["Total Dialed", "Total Connected", "Prospect"]:
                data.pop(k, None)

        return data

    @staticmethod
    def _detect_department(text: str) -> str:
        t = text.lower()
        for dept, keywords in DEPARTMENT_KEYWORDS.items():
            if any(kw in t for kw in keywords):
                return dept
        return "Unknown"

    # ──────────────────────────────────────
    # Flexible regex fallback
    # ──────────────────────────────────────

    def _fallback_parse(self, text: str) -> Optional[Dict]:
        """
        Flexible regex fallback that handles:
          - Missing ':' separator
          - Short keywords: dial, conn, pros, dur
          - Any order of fields
          - Various duration formats
        """
        dept = self._detect_department(text)
        dur  = self._extract_duration_flexible(text)
        name = self._extract_name(text)

        def grab(keywords: list) -> int:
            """
            Find first number that appears after any keyword.
            Separator between keyword and number can be: : = - . space (or missing).
            """
            for kw in keywords:
                # Escape the keyword for regex use
                kw_esc = re.escape(kw)
                # Allow optional separator chars and whitespace between keyword and number
                pattern = rf"(?i){kw_esc}\s*[:\-=.]?\s*(\d+)"
                match = re.search(pattern, text)
                if match:
                    return int(match.group(1))
            return 0

        if dept == "Sales":
            return {
                "employee_name":   name,
                "department":      "Sales",
                "Total Dialed":    grab([
                    "total dial", "total dials", "total dialed",
                    "total calls", "calls made", "dials", "dial",
                ]),
                "Total Connected": grab([
                    "total connected", "connected calls",
                    "connected", "conn", "cnct",
                ]),
                "Duration": dur,
                "Prospect": grab([
                    "prospect", "prospects", "pros", "prspct",
                ]),
            }

        elif dept == "HR":
            return {
                "employee_name":              name,
                "department":                 "HR",
                "Total Calls":                grab([
                    "total calls", "total dial", "dials", "calls",
                ]),
                "Connected Calls":            grab([
                    "connected calls", "connected", "conn", "cnct",
                ]),
                "Duration":                   dur,
                "Tomorrow Interview Lineups": grab([
                    "tomorrow interview lineups", "interview lineups",
                    "tomorrow lineups", "lineups",
                ]),
                "Interview Held":             grab([
                    "interview held", "interviews held", "held",
                ]),
            }

        return None

    @staticmethod
    def _extract_name(text: str) -> str:
        """Best-effort name extraction from first non-empty, non-numeric line."""
        for line in text.splitlines():
            line = line.strip()
            # Skip lines that look like field:value pairs or are just numbers
            if 2 < len(line) < 50 and not re.search(r'\d{2,}', line):
                if not re.search(r'[:=\-]', line):   # skip field:value lines
                    return line
        return ""

    @staticmethod
    def _extract_duration_flexible(text: str) -> str:
        """
        Extract duration from text using the flexible parse_duration function.
        Tries multiple patterns in priority order.
        """
        # Priority 1: HH:MM:SS
        m = re.search(r'\b(\d{1,3}:\d{2}:\d{2})\b', text)
        if m:
            return parse_duration(m.group(1))

        # Priority 2: Xh Ym Zs verbose format
        m = re.search(
            r'(\d+\s*h(?:r|rs|our|ours)?\s*\d*\s*m?(?:in|ins)?\s*\d*\s*s?(?:ec|ecs)?)',
            text, re.IGNORECASE
        )
        if m:
            return parse_duration(m.group(1))

        # Priority 3: MM:SS
        m = re.search(r'\b(\d{1,3}:\d{2})\b', text)
        if m:
            return parse_duration(m.group(1))

        return "00:00:00"
