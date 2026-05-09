"""
utils.py — Shared utility functions: date extraction, duration parsing, math handling
UPDATED: Enhanced duration parsing for ALL formats (Sales + HR)
"""

import re
from datetime import datetime
from typing import Optional, Tuple

from config import DATE_IN_SUBJECT_FORMAT, DATE_PATTERNS, SHEET_NAME_FORMAT


# ─────────────────────────────────────────────
# Date Helpers
# ─────────────────────────────────────────────

def extract_date_from_subject(subject: str) -> Optional[str]:
    if not subject:
        return None
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, subject)
        if match:
            raw = match.group(1)
            normalized = _normalize_date(raw)
            if normalized:
                return normalized
    return None


def received_timestamp_to_date(timestamp_ms: int) -> str:
    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt.strftime("%d-%m-%Y")


def received_timestamp_to_datetime(timestamp_ms: int) -> datetime:
    return datetime.fromtimestamp(timestamp_ms / 1000)


def _normalize_date(raw: str) -> Optional[str]:
    candidate_formats = [
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
    ]
    for fmt in candidate_formats:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%d-%m-%Y")
        except ValueError:
            continue
    return None


def date_to_sheet_name(date_str: str) -> str:
    dt = datetime.strptime(date_str, DATE_IN_SUBJECT_FORMAT)
    return dt.strftime(SHEET_NAME_FORMAT)


def validate_date_string(date_str: str) -> Tuple[bool, Optional[str], str]:
    if not date_str:
        return False, None, "Date string is empty"
    normalized = _normalize_date(date_str)
    if normalized:
        return True, normalized, ""
    return False, None, f"Unrecognised date format: {date_str!r}"


# ─────────────────────────────────────────────
# Enhanced Duration Helpers (Handles ALL formats)
# ─────────────────────────────────────────────

def parse_duration(raw: str) -> str:
    """
    Parse duration string, handling:
    - "1h 0m 35s" → 01:00:35
    - "1H 15M + 14M ON WHATSAPP + 5M ON ANOTHER CALL" → 01:34:00
    - "1 H 31 M" → 01:31:00
    - "1hr 25m 21s" → 01:25:21
    - "1 hr 49 min" → 01:49:00
    - "1h 17m 45s" → 01:17:45
    - "53m 7s" → 00:53:07
    - "39m 47s" → 00:39:47
    """
    if not raw:
        return "00:00:00"
    
    raw = str(raw).strip()
    
    # Check if it says "Leave"
    if 'leave' in raw.lower():
        return "00:00:00"
    
    # Check if there are multiple durations with "+"
    if '+' in raw:
        # Split by + and sum all durations
        parts = raw.split('+')
        total_seconds = 0
        for part in parts:
            total_seconds += _duration_to_seconds(part.strip())
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    
    # Single duration
    return _duration_to_hms(raw)


def _duration_to_seconds(duration_str: str) -> int:
    """Convert a duration string to total seconds - Handles ALL formats"""
    duration_str = duration_str.strip().lower()
    total_seconds = 0
    
    # Remove any text in parentheses or after keywords like "on", "from", "another"
    duration_str = re.sub(r'\s+(?:on|from|another|whatsapp|other|phone).*$', '', duration_str, flags=re.IGNORECASE)
    
    # Pattern for "1h 18m 47s" or "1h 0m 35s"
    match = re.search(r'(\d+)\s*h(?:r)?s?\s*(\d+)\s*m(?:in)?s?\s*(\d+)\s*s(?:ec)?s?', duration_str, re.IGNORECASE)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return h * 3600 + m * 60 + s
    
    # Pattern for "1h 18m" or "1h 0m"
    match = re.search(r'(\d+)\s*h(?:r)?s?\s*(\d+)\s*m(?:in)?s?', duration_str, re.IGNORECASE)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        return h * 3600 + m * 60
    
    # Pattern for "1 H 31 M" (space between number and unit, uppercase) - FIXED
    match = re.search(r'(\d+)\s*[hH](?:r)?\s*(\d+)\s*[mM]', duration_str)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        return h * 3600 + m * 60
    
    # Pattern for "1hr 25m 21s" - FIXED
    match = re.search(r'(\d+)\s*hr\s*(\d+)\s*m\s*(\d+)\s*s', duration_str, re.IGNORECASE)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return h * 3600 + m * 60 + s
    
    # Pattern for "1 hr 49 min" (no seconds) - FIXED
    match = re.search(r'(\d+)\s*hr\s*(\d+)\s*min', duration_str, re.IGNORECASE)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        return h * 3600 + m * 60
    
    # Pattern for "1h" (just hours)
    match = re.search(r'(\d+)\s*h(?:r)?s?', duration_str, re.IGNORECASE)
    if match:
        return int(match.group(1)) * 3600
    
    # Pattern for "56m 49s" (minutes and seconds)
    match = re.search(r'(\d+)\s*m(?:in)?s?\s*(\d+)\s*s(?:ec)?s?', duration_str, re.IGNORECASE)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        return m * 60 + s
    
    # Pattern for "53m 7s" (minutes and seconds with single digit seconds)
    match = re.search(r'(\d+)\s*m\s*(\d+)\s*s', duration_str, re.IGNORECASE)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        return m * 60 + s
    
    # Pattern for "56m" (just minutes)
    match = re.search(r'(\d+)\s*m(?:in)?s?', duration_str, re.IGNORECASE)
    if match:
        return int(match.group(1)) * 60
    
    # Pattern for "47s" (just seconds)
    match = re.search(r'(\d+)\s*s(?:ec)?s?', duration_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # Pattern for MM:SS format
    match = re.search(r'(\d{2}):(\d{2})', duration_str)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        return m * 60 + s
    
    # Pattern for HH:MM:SS format
    match = re.search(r'(\d{2}):(\d{2}):(\d{2})', duration_str)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return h * 3600 + m * 60 + s
    
    return 0


def _duration_to_hms(duration_str: str) -> str:
    """Convert a single duration string to HH:MM:SS format"""
    seconds = _duration_to_seconds(duration_str)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def duration_to_seconds(raw: str) -> int:
    return _duration_to_seconds(raw)


def seconds_to_hms(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ─────────────────────────────────────────────
# Enhanced Numeric Helpers (Handles math like 121+19, 126+10, 163 + 4)
# ─────────────────────────────────────────────

def coerce_int(value) -> int:
    """Extract and sum numbers, handling patterns like '126+10', '163 + 4', '143 + 3'"""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    
    str_val = str(value).strip()
    
    # Check if it's "Leave"
    if str_val.lower() == 'leave':
        return 0
    
    # Check if there's addition (e.g., "126+10", "163 + 4", "56+6")
    if '+' in str_val:
        parts = re.split(r'\s*\+\s*', str_val)
        total = 0
        for part in parts:
            # Extract only digits from each part
            nums = re.findall(r'\d+', part)
            if nums:
                total += int(nums[0])
        return total
    
    # Check if there's a range or dash (e.g., "121-19" - treat as single number)
    if '-' in str_val:
        nums = re.findall(r'\d+', str_val)
        if nums:
            return int(nums[0])
    
    # Normal number extraction
    nums = re.findall(r"\d+", str_val)
    return int(nums[0]) if nums else 0


def safe_title(name: str) -> str:
    if not name:
        return ""
    return " ".join(name.strip().split()).title()


def normalize_employee_name(name: str) -> str:
    if not name:
        return ""
    words = name.strip().split()
    filtered = []
    for word in words:
        clean = word.rstrip(".")
        if len(clean) == 1 and clean.isalpha():
            continue
        filtered.append(word)
    return safe_title(" ".join(filtered))


def extract_email_address(from_header: str) -> str:
    match = re.search(r'<([^>]+)>', from_header)
    if match:
        return match.group(1).strip().lower()
    match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', from_header)
    if match:
        return match.group(0).strip().lower()
    return from_header.strip().lower()
