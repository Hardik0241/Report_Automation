"""
utils.py — Shared utility functions: date extraction, duration parsing, math handling
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
# Enhanced Duration Helpers (Handles addition)
# ─────────────────────────────────────────────

def parse_duration(raw: str) -> str:
    """
    Parse duration string, handling multiple durations added together.
    Examples:
    - "1h 18m + 8m 47s + 13m33s + 2m31s + 4m" → sums all durations
    - "2h 29m 54s + 12m" → 2h 41m 54s
    - "56m 49s" → 00:56:49
    - "1h 20m 13sec" → 01:20:13
    """
    if not raw:
        return "00:00:00"
    
    raw = str(raw).strip().lower()
    
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
    """Convert a duration string to total seconds"""
    duration_str = duration_str.strip()
    total_seconds = 0
    
    # Pattern for "1h 18m 47s"
    match = re.search(r'(\d+)\s*h(?:r|our)?s?\s*(\d+)\s*m(?:in|inute)?s?\s*(\d+)\s*s(?:ec|econd)?s?', duration_str, re.IGNORECASE)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return h * 3600 + m * 60 + s
    
    # Pattern for "1h 18m"
    match = re.search(r'(\d+)\s*h(?:r|our)?s?\s*(\d+)\s*m(?:in|inute)?s?', duration_str, re.IGNORECASE)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        return h * 3600 + m * 60
    
    # Pattern for "1h"
    match = re.search(r'(\d+)\s*h(?:r|our)?s?', duration_str, re.IGNORECASE)
    if match:
        return int(match.group(1)) * 3600
    
    # Pattern for "56m 49s"
    match = re.search(r'(\d+)\s*m(?:in|inute)?s?\s*(\d+)\s*s(?:ec|econd)?s?', duration_str, re.IGNORECASE)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        return m * 60 + s
    
    # Pattern for "56m"
    match = re.search(r'(\d+)\s*m(?:in|inute)?s?', duration_str, re.IGNORECASE)
    if match:
        return int(match.group(1)) * 60
    
    # Pattern for "47s"
    match = re.search(r'(\d+)\s*s(?:ec|econd)?s?', duration_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
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
# Enhanced Numeric Helpers (Handles math like 121+19)
# ─────────────────────────────────────────────

def coerce_int(value) -> int:
    """Extract and sum numbers, handling patterns like '121+19'"""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    
    str_val = str(value)
    
    # Check if there's addition (e.g., "121+19" or "121 + 19")
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
