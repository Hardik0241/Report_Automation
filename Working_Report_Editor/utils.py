"""
utils.py — Shared utility functions: date extraction, duration parsing, math handling
UPDATED: Fixed duration parsing - properly handles hours, minutes, seconds
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
# Enhanced Duration Helpers - FIXED VERSION
# ─────────────────────────────────────────────

def parse_duration(raw: str) -> str:
    """
    Parse duration string, handling:
    - "1h 2m 48s" → 01:02:48
    - "1h 2m" → 01:02:00
    - "1h" → 01:00:00
    - "56m 49s" → 00:56:49
    - "53m 7s" → 00:53:07
    - "1h 15m + 14m + 5m" → 01:34:00 (sums)
    """
    if not raw:
        return "00:00:00"
    
    raw = str(raw).strip()
    
    # Check if it says "Leave"
    if 'leave' in raw.lower():
        return "00:00:00"
    
    # Check if there are multiple durations with "+"
    if '+' in raw:
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
    """
    Convert a duration string to total seconds - FIXED to properly handle hours
    """
    duration_str = duration_str.strip().lower()
    total_seconds = 0
    
    # Remove any text in parentheses or after keywords
    duration_str = re.sub(r'\s+(?:on|from|another|whatsapp|other|phone).*$', '', duration_str, flags=re.IGNORECASE)
    
    # ========== PATTERNS IN ORDER OF PRIORITY ==========
    
    # Pattern 1: "1h 2m 48s" or "1h 2m 48s" - FULL HOURS, MINUTES, SECONDS
    match = re.search(r'(\d+)\s*h(?:r)?s?\s*(\d+)\s*m(?:in)?s?\s*(\d+)\s*s(?:ec)?s?', duration_str, re.IGNORECASE)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return h * 3600 + m * 60 + s
    
    # Pattern 2: "1h2m48s" - NO SPACES between
    match = re.search(r'(\d+)h\s*(\d+)m\s*(\d+)s', duration_str, re.IGNORECASE)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return h * 3600 + m * 60 + s
    
    # Pattern 3: "1h 2m" - HOURS AND MINUTES (no seconds)
    match = re.search(r'(\d+)\s*h(?:r)?s?\s*(\d+)\s*m(?:in)?s?', duration_str, re.IGNORECASE)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        return h * 3600 + m * 60
    
    # Pattern 4: "1h2m" - NO SPACES, hours and minutes
    match = re.search(r'(\d+)h\s*(\d+)m', duration_str, re.IGNORECASE)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        return h * 3600 + m * 60
    
    # Pattern 5: "1 H 2 M" - SPACES, UPPERCASE
    match = re.search(r'(\d+)\s*[hH]\s*(\d+)\s*[mM]', duration_str)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        return h * 3600 + m * 60
    
    # Pattern 6: "1hr 2m 48s" - WITH "hr"
    match = re.search(r'(\d+)\s*hr\s*(\d+)\s*m\s*(\d+)\s*s', duration_str, re.IGNORECASE)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return h * 3600 + m * 60 + s
    
    # Pattern 7: "1 hr 2 min 48 sec" - FULL WORDS
    match = re.search(r'(\d+)\s*hr\s*(\d+)\s*min\s*(\d+)\s*sec', duration_str, re.IGNORECASE)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return h * 3600 + m * 60 + s
    
    # Pattern 8: "1 hr 2 min" - HOURS AND MINUTES with full words
    match = re.search(r'(\d+)\s*hr\s*(\d+)\s*min', duration_str, re.IGNORECASE)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        return h * 3600 + m * 60
    
    # Pattern 9: "1h" - JUST HOURS
    match = re.search(r'(\d+)\s*h(?:r)?s?', duration_str, re.IGNORECASE)
    if match:
        return int(match.group(1)) * 3600
    
    # Pattern 10: "56m 49s" - MINUTES AND SECONDS (no hours)
    match = re.search(r'(\d+)\s*m(?:in)?s?\s*(\d+)\s*s(?:ec)?s?', duration_str, re.IGNORECASE)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        return m * 60 + s
    
    # Pattern 11: "53m 7s" - MINUTES AND SECONDS (simplified)
    match = re.search(r'(\d+)\s*m\s*(\d+)\s*s', duration_str, re.IGNORECASE)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        return m * 60 + s
    
    # Pattern 12: "56m" - JUST MINUTES
    match = re.search(r'(\d+)\s*m(?:in)?s?', duration_str, re.IGNORECASE)
    if match:
        return int(match.group(1)) * 60
    
    # Pattern 13: "47s" - JUST SECONDS
    match = re.search(r'(\d+)\s*s(?:ec)?s?', duration_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # Pattern 14: "02:48" - MM:SS format
    match = re.search(r'(\d{2}):(\d{2})', duration_str)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        # If minutes > 59, treat as hours:minutes
        if m > 59:
            h = m // 60
            m = m % 60
            return h * 3600 + m * 60 + s
        return m * 60 + s
    
    # Pattern 15: "01:02:48" - HH:MM:SS format
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
# Enhanced Numeric Helpers
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
    
    # Check if there's addition
    if '+' in str_val:
        parts = re.split(r'\s*\+\s*', str_val)
        total = 0
        for part in parts:
            nums = re.findall(r'\d+', part)
            if nums:
                total += int(nums[0])
        return total
    
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
