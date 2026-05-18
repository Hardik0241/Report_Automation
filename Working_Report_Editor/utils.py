"""
utils.py — Shared utility functions: date extraction, duration parsing, math handling
UPDATED: Fixed duration parsing for addition patterns like "+7 minutes", "+10 min"
UPDATED: Added more robust duration extraction for HH:MM:SS format with dashes
Handles: "1h 15m + 10 min", "1h 49m 16s + 12m", "Total dial:- 168", "Duration- 01:28:52"
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
# DURATION PARSING - COMPLETELY REWRITTEN
# ─────────────────────────────────────────────

def parse_duration(raw: str) -> str:
    """
    Parse duration string to HH:MM:SS format.
    
    Handles:
    - "1h 5m 30s" → 01:05:30
    - "1h 15m + 10 min" → 01:25:00
    - "1h 49m 16s + 12m" → 02:01:16
    - "1h 15m + 10min" → 01:25:00
    - "1h 15m +10m" → 01:25:00
    - "Duration- 01:28:52" → 01:28:52
    - "01:28:52" → 01:28:52
    """
    if not raw:
        return "00:00:00"
    
    raw = str(raw).strip()
    
    if 'leave' in raw.lower():
        return "00:00:00"
    
    # Handle HH:MM:SS format directly (e.g., "01:28:52")
    match = re.search(r'(\d{2}):(\d{2}):(\d{2})', raw)
    if match:
        return match.group(0)
    
    # Handle MM:SS format
    match = re.search(r'(\d{2}):(\d{2})', raw)
    if match and ':' in raw and raw.count(':') == 1:
        m, s = int(match.group(1)), int(match.group(2))
        return f"00:{m:02d}:{s:02d}"
    
    # Handle multiple durations with "+"
    if '+' in raw:
        parts = raw.split('+')
        total_seconds = 0
        for part in parts:
            total_seconds += _duration_to_seconds(part.strip())
        return _seconds_to_hms(total_seconds)
    
    # Single duration
    seconds = _duration_to_seconds(raw)
    return _seconds_to_hms(seconds)


def _duration_to_seconds(duration_str: str) -> int:
    """
    Convert a duration string to total seconds - Handles ALL formats including additions
    """
    duration_str = duration_str.strip().lower()
    total_seconds = 0
    
    # Remove any text in parentheses or after keywords
    duration_str = re.sub(r'\s+(?:on|from|another|whatsapp|other|phone).*$', '', duration_str, flags=re.IGNORECASE)
    
    # ========== HANDLE ADDITION PATTERNS FIRST ==========
    
    # Pattern for "+ 10 min" or "+10min" or "+ 10 minutes"
    addition_match = re.search(r'\+\s*(\d+)\s*(?:min(?:ute)?s?)', duration_str, re.IGNORECASE)
    if addition_match:
        extra_minutes = int(addition_match.group(1))
        total_seconds += extra_minutes * 60
        duration_str = re.sub(r'\+\s*\d+\s*(?:min(?:ute)?s?)', '', duration_str, flags=re.IGNORECASE)
    
    # Pattern for "+12m" (minutes)
    addition_match = re.search(r'\+\s*(\d+)\s*m', duration_str, re.IGNORECASE)
    if addition_match:
        extra_minutes = int(addition_match.group(1))
        total_seconds += extra_minutes * 60
        duration_str = re.sub(r'\+\s*\d+\s*m', '', duration_str, flags=re.IGNORECASE)
    
    # Pattern for "+ 15s" (seconds)
    addition_match = re.search(r'\+\s*(\d+)\s*s', duration_str, re.IGNORECASE)
    if addition_match:
        extra_seconds = int(addition_match.group(1))
        total_seconds += extra_seconds
        duration_str = re.sub(r'\+\s*\d+\s*s', '', duration_str, flags=re.IGNORECASE)
    
    # ========== PARSE MAIN DURATION ==========
    
    # Pattern 1: "1h 5m 30s" - FULL HOURS, MINUTES, SECONDS
    match = re.search(r'(\d+)\s*h(?:r)?s?\s*(\d+)\s*m(?:in)?s?\s*(\d+)\s*s(?:ec)?s?', duration_str, re.IGNORECASE)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        total_seconds += h * 3600 + m * 60 + s
        return total_seconds
    
    # Pattern 2: "1h 15m" - HOURS AND MINUTES (no seconds)
    match = re.search(r'(\d+)\s*h(?:r)?s?\s*(\d+)\s*m(?:in)?s?', duration_str, re.IGNORECASE)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        total_seconds += h * 3600 + m * 60
        return total_seconds
    
    # Pattern 3: "1 H 45 M" - UPPERCASE with spaces
    match = re.search(r'(\d+)\s*[hH]\s*(\d+)\s*[mM]', duration_str)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        total_seconds += h * 3600 + m * 60
        return total_seconds
    
    # Pattern 4: "1h" - JUST HOURS
    match = re.search(r'(\d+)\s*h(?:r)?s?', duration_str, re.IGNORECASE)
    if match:
        total_seconds += int(match.group(1)) * 3600
        return total_seconds
    
    # Pattern 5: "49m 16s" - MINUTES AND SECONDS
    match = re.search(r'(\d+)\s*m(?:in)?s?\s*(\d+)\s*s(?:ec)?s?', duration_str, re.IGNORECASE)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        total_seconds += m * 60 + s
        return total_seconds
    
    # Pattern 6: "49m" - JUST MINUTES
    match = re.search(r'(\d+)\s*m(?:in)?s?', duration_str, re.IGNORECASE)
    if match:
        total_seconds += int(match.group(1)) * 60
        return total_seconds
    
    # Pattern 7: "30s" - JUST SECONDS
    match = re.search(r'(\d+)\s*s(?:ec)?s?', duration_str, re.IGNORECASE)
    if match:
        total_seconds += int(match.group(1))
        return total_seconds
    
    # Pattern 8: "01:28:52" - HH:MM:SS format
    match = re.search(r'(\d{2}):(\d{2}):(\d{2})', duration_str)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        total_seconds += h * 3600 + m * 60 + s
        return total_seconds
    
    # Pattern 9: "01:28" - MM:SS format
    match = re.search(r'(\d{2}):(\d{2})', duration_str)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        total_seconds += m * 60 + s
        return total_seconds
    
    return total_seconds


def _seconds_to_hms(total_seconds: int) -> str:
    """Convert total seconds to HH:MM:SS format"""
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def duration_to_seconds(raw: str) -> int:
    """Convenience function to get duration in seconds"""
    return _duration_to_seconds(raw)


def seconds_to_hms(seconds: int) -> str:
    """Convenience function to convert seconds to HH:MM:SS"""
    return _seconds_to_hms(seconds)


# ─────────────────────────────────────────────
# Numeric Helpers - Handles addition like "34+2", "95+6"
# ─────────────────────────────────────────────

def coerce_int(value) -> int:
    """
    Extract and sum numbers, handling patterns like:
    - "135" → 135
    - "126+10" → 136
    - "34+2" → 36
    - "95+6" → 101
    - "Total dial:- 135" → 135 (extracts the number)
    """
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    
    str_val = str(value).strip()
    
    if str_val.lower() == 'leave':
        return 0
    
    # Handle addition like "34+2", "95+6", "126+10"
    if '+' in str_val:
        parts = re.split(r'\s*\+\s*', str_val)
        total = 0
        for part in parts:
            nums = re.findall(r'\d+', part)
            if nums:
                total += int(nums[0])
        return total
    
    # Extract first number found
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
