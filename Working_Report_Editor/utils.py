"""
utils.py — Shared utility functions: date extraction, duration parsing, math handling
COMPLETELY REWRITTEN: Fixed duration parsing for addition patterns like "+7 minutes"
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
# DURATION PARSING - HANDLES ADDITION PATTERNS
# ─────────────────────────────────────────────

def parse_duration(raw: str) -> str:
    """
    Parse duration string to HH:MM:SS format.
    
    Handles:
    - "2h 23m 14s +7 minutes" → 02:30:14
    - "1h 9m 0s + (personal calls aprox 30mins)" → 01:39:00
    - "1h 34m" → 01:34:00
    - "1hr 48m 0s" → 01:48:00
    - "46m 48s" → 00:46:48
    """
    if not raw:
        return "00:00:00"
    
    raw = str(raw).strip().lower()
    
    if 'leave' in raw:
        return "00:00:00"
    
    # First, extract all additional time from patterns like "+7 minutes"
    total_seconds = 0
    remaining_text = raw
    
    # Pattern 1: "+7 minutes" or "+ 30mins" or "+ 15 min"
    match = re.search(r'\+\s*(\d+)\s*(?:min(?:ute)?s?)', remaining_text, re.IGNORECASE)
    if match:
        extra_minutes = int(match.group(1))
        total_seconds += extra_minutes * 60
        remaining_text = re.sub(r'\+\s*\d+\s*(?:min(?:ute)?s?)', '', remaining_text, flags=re.IGNORECASE)
    
    # Pattern 2: "+ (personal calls aprox 30mins)" - extract number before mins
    match = re.search(r'\+\s*\([^)]*(\d+)\s*(?:min(?:ute)?s?)[^)]*\)', remaining_text, re.IGNORECASE)
    if match:
        extra_minutes = int(match.group(1))
        total_seconds += extra_minutes * 60
        remaining_text = re.sub(r'\+\s*\([^)]*\)', '', remaining_text, flags=re.IGNORECASE)
    
    # Pattern 3: "+10m" or "+ 10m"
    match = re.search(r'\+\s*(\d+)\s*m', remaining_text, re.IGNORECASE)
    if match:
        extra_minutes = int(match.group(1))
        total_seconds += extra_minutes * 60
        remaining_text = re.sub(r'\+\s*\d+\s*m', '', remaining_text, flags=re.IGNORECASE)
    
    # Parse the main duration from remaining text
    main_seconds = _parse_single_duration_to_seconds(remaining_text)
    total_seconds += main_seconds
    
    return _seconds_to_hms(total_seconds)


def _parse_single_duration_to_seconds(duration_str: str) -> int:
    """Parse a single duration string to total seconds."""
    duration_str = duration_str.strip().lower()
    
    hours = 0
    minutes = 0
    seconds = 0
    
    # Pattern 1: "2h 23m 14s"
    match = re.search(r'(\d+)\s*h(?:r)?\s*(\d+)\s*m\s*(\d+)\s*s', duration_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        return hours * 3600 + minutes * 60 + seconds
    
    # Pattern 2: "1h 34m" (no seconds)
    match = re.search(r'(\d+)\s*h(?:r)?\s*(\d+)\s*m', duration_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        return hours * 3600 + minutes * 60
    
    # Pattern 3: "1 H 34 M" (uppercase with spaces)
    match = re.search(r'(\d+)\s*[hH]\s*(\d+)\s*[mM]', duration_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        return hours * 3600 + minutes * 60
    
    # Pattern 4: "1hr 48m 0s"
    match = re.search(r'(\d+)\s*hr\s*(\d+)\s*m\s*(\d+)\s*s', duration_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        return hours * 3600 + minutes * 60 + seconds
    
    # Pattern 5: "1h" (hours only)
    match = re.search(r'(\d+)\s*h(?:r)?', duration_str)
    if match:
        hours = int(match.group(1))
        return hours * 3600
    
    # Pattern 6: "46m 48s" (minutes and seconds)
    match = re.search(r'(\d+)\s*m\s*(\d+)\s*s', duration_str)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        return minutes * 60 + seconds
    
    # Pattern 7: "46m" (minutes only)
    match = re.search(r'(\d+)\s*m', duration_str)
    if match:
        minutes = int(match.group(1))
        return minutes * 60
    
    # Pattern 8: "48s" (seconds only)
    match = re.search(r'(\d+)\s*s', duration_str)
    if match:
        seconds = int(match.group(1))
        return seconds
    
    # Pattern 9: HH:MM:SS format
    match = re.search(r'(\d{2}):(\d{2}):(\d{2})', duration_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        return hours * 3600 + minutes * 60 + seconds
    
    # Pattern 10: MM:SS format
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
# Numeric Helpers
# ─────────────────────────────────────────────

def coerce_int(value) -> int:
    """Extract and sum numbers, handling patterns like '126+10', '63 + 10'"""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    
    str_val = str(value).strip()
    
    if str_val.lower() == 'leave':
        return 0
    
    # Handle addition like "63 + 10"
    if '+' in str_val:
        parts = re.split(r'\s*\+\s*', str_val)
        total = 0
        for part in parts:
            nums = re.findall(r'\d+', part)
            if nums:
                total += int(nums[0])
        return total
    
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
