"""
utils.py — Shared utility functions: date extraction, duration parsing, math handling
COMPLETELY REWRITTEN: Fixed duration parsing and number extraction
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
    - "1h 38m 40s" → 01:38:40
    - "1 H 45 M" → 01:45:00
    - "1h 51m" → 01:51:00
    - "1h" → 01:00:00
    - "43m 32s" → 00:43:32
    """
    if not raw:
        return "00:00:00"
    
    raw = str(raw).strip().lower()
    
    # Check for "Leave"
    if 'leave' in raw:
        return "00:00:00"
    
    # Handle multiple durations with "+"
    if '+' in raw:
        parts = raw.split('+')
        total_seconds = 0
        for part in parts:
            total_seconds += _parse_single_duration_to_seconds(part.strip())
        return _seconds_to_hms(total_seconds)
    
    # Single duration
    seconds = _parse_single_duration_to_seconds(raw)
    return _seconds_to_hms(seconds)


def _parse_single_duration_to_seconds(duration_str: str) -> int:
    """Parse a single duration string to total seconds."""
    duration_str = duration_str.strip().lower()
    
    # Remove noise after keywords
    duration_str = re.sub(r'\s+(?:on|from|another|whatsapp|other|phone).*$', '', duration_str)
    
    hours = 0
    minutes = 0
    seconds = 0
    
    # Pattern 1: "1h 38m 40s" or "1hr 54m 14s"
    match = re.search(r'(\d+)\s*h(?:r)?\s*(\d+)\s*m\s*(\d+)\s*s', duration_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        return hours * 3600 + minutes * 60 + seconds
    
    # Pattern 2: "1 H 45 M" (uppercase with spaces)
    match = re.search(r'(\d+)\s*[hH]\s*(\d+)\s*[mM]', duration_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        return hours * 3600 + minutes * 60
    
    # Pattern 3: "1h 51m" (hours and minutes)
    match = re.search(r'(\d+)\s*h(?:r)?\s*(\d+)\s*m', duration_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        return hours * 3600 + minutes * 60
    
    # Pattern 4: "43m 32s" (minutes and seconds)
    match = re.search(r'(\d+)\s*m\s*(\d+)\s*s', duration_str)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        return minutes * 60 + seconds
    
    # Pattern 5: "1h" (hours only)
    match = re.search(r'(\d+)\s*h(?:r)?', duration_str)
    if match:
        hours = int(match.group(1))
        return hours * 3600
    
    # Pattern 6: "43m" (minutes only)
    match = re.search(r'(\d+)\s*m', duration_str)
    if match:
        minutes = int(match.group(1))
        return minutes * 60
    
    # Pattern 7: "32s" (seconds only)
    match = re.search(r'(\d+)\s*s', duration_str)
    if match:
        seconds = int(match.group(1))
        return seconds
    
    # Pattern 8: HH:MM:SS format
    match = re.search(r'(\d{2}):(\d{2}):(\d{2})', duration_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        return hours * 3600 + minutes * 60 + seconds
    
    # Pattern 9: MM:SS format
    match = re.search(r'(\d{2}):(\d{2})', duration_str)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        return minutes * 60 + seconds
    
    return 0


def _seconds_to_hms(total_seconds: int) -> str:
    """Convert total seconds to HH:MM:SS format"""
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def duration_to_seconds(raw: str) -> int:
    """Convenience function to get duration in seconds"""
    return _parse_single_duration_to_seconds(raw)


def seconds_to_hms(seconds: int) -> str:
    """Convenience function to convert seconds to HH:MM:SS"""
    return _seconds_to_hms(seconds)


# ─────────────────────────────────────────────
# Numeric Helpers - FIXED for "Total dial:- 135" format
# ─────────────────────────────────────────────

def coerce_int(value) -> int:
    """
    Extract and sum numbers, handling patterns like:
    - "135" → 135
    - "126+10" → 136
    - "Total dial:- 135" → 135 (extracts the number)
    - "192" → 192
    - "0" → 0
    """
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    
    str_val = str(value).strip()
    
    # Check for "Leave"
    if str_val.lower() == 'leave':
        return 0
    
    # Handle addition like "126+10"
    if '+' in str_val:
        parts = re.split(r'\s*\+\s*', str_val)
        total = 0
        for part in parts:
            nums = re.findall(r'\d+', part)
            if nums:
                total += int(nums[0])
        return total
    
    # Extract first number found (handles "Total dial:- 135" → extracts 135)
    nums = re.findall(r'\d+', str_val)
    if nums:
        return int(nums[0])
    
    return 0


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
