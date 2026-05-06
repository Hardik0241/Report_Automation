"""
utils.py — Shared utility functions: date extraction, duration parsing, etc.
"""

import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from config import DATE_IN_SUBJECT_FORMAT, DATE_PATTERNS, SHEET_NAME_FORMAT

# IST timezone (UTC + 5:30)
IST = timezone(timedelta(hours=5, minutes=30))


# ─────────────────────────────────────────────
# Date Helpers
# ─────────────────────────────────────────────

def utc_to_ist(utc_dt: datetime) -> datetime:
    """Convert UTC datetime to IST (UTC + 5:30)"""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(IST)


def format_ist_time(dt: datetime) -> str:
    """Format datetime to IST string"""
    ist_dt = utc_to_ist(dt)
    return ist_dt.strftime("%d-%m-%Y %I:%M:%S %p")


def received_timestamp_to_date(timestamp_ms: int) -> str:
    """
    Convert Gmail internalDate (milliseconds since epoch) to DD-MM-YYYY string in IST.
    Used for Sales emails — we use the received date, not the subject date.
    """
    utc_dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    ist_dt = utc_to_ist(utc_dt)
    return ist_dt.strftime("%d-%m-%Y")


def received_timestamp_to_datetime(timestamp_ms: int) -> datetime:
    """Convert Gmail internalDate (ms) to a datetime object in IST."""
    utc_dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    return utc_to_ist(utc_dt)


def received_timestamp_to_ist_string(timestamp_ms: int) -> str:
    """Convert Gmail timestamp to IST readable string."""
    utc_dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    ist_dt = utc_to_ist(utc_dt)
    return ist_dt.strftime("%d-%m-%Y %I:%M:%S %p")


def extract_date_from_subject(subject: str) -> Optional[str]:
    """
    Try each DATE_PATTERNS regex against the subject line.
    Returns the first match in DD-MM-YYYY canonical form, or None.
    """
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


def _normalize_date(raw: str) -> Optional[str]:
    """Try to parse a raw date string and return it as DD-MM-YYYY."""
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
    """'25-03-2026' → 'Mar-2026'"""
    dt = datetime.strptime(date_str, DATE_IN_SUBJECT_FORMAT)
    return dt.strftime(SHEET_NAME_FORMAT)


def validate_date_string(date_str: str) -> Tuple[bool, Optional[str], str]:
    """Returns (is_valid, normalized_date_or_None, error_message)."""
    if not date_str:
        return False, None, "Date string is empty"
    normalized = _normalize_date(date_str)
    if normalized:
        return True, normalized, ""
    return False, None, f"Unrecognised date format: {date_str!r}"


# ─────────────────────────────────────────────
# Duration Helpers (IMPROVED)
# ─────────────────────────────────────────────

def parse_duration(raw: str) -> str:
    """
    Coerce ANY time-like string to HH:MM:SS.

    Handles all these formats (and combinations):
      "1h 20m 45s"   "1hr 20min"   "1h20m"   "20m 45sec"
      "1h"           "30m"         "45s"
      "1h 45m"       "1h 45m"      "45m"     (missing seconds)
      "02:30:45"     "30:45"       "00:36:35"
      bare integer   "90"          (treated as seconds)
    Falls back to "00:00:00" on failure.
    """
    if not raw:
        return "00:00:00"

    raw = str(raw).strip().lower()
    total_seconds = 0
    found = False

    # ── Verbose format: Xh Ym Zs (with or without spaces, various spellings) ──
    h_match = re.search(r'(\d+)\s*h(?:r|rs|our|ours)?(?:\s|$|\d)', raw)
    m_match = re.search(r'(\d+)\s*m(?:in|ins|inute|inutes)?(?:\s|$|\d)', raw)
    s_match = re.search(r'(\d+)\s*s(?:ec|ecs|econd|econds)?(?:\s|$|$)', raw)

    if h_match or m_match or s_match:
        total_seconds += int(h_match.group(1)) * 3600 if h_match else 0
        total_seconds += int(m_match.group(1)) * 60   if m_match else 0
        total_seconds += int(s_match.group(1))        if s_match else 0
        found = True

    if not found:
        # ── HH:MM:SS ──
        m = re.fullmatch(r'(\d{1,3}):(\d{2}):(\d{2})', raw)
        if m:
            total_seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            found = True

    if not found:
        # ── MM:SS ──
        m = re.fullmatch(r'(\d{1,3}):(\d{2})', raw)
        if m:
            total_seconds = int(m.group(1)) * 60 + int(m.group(2))
            found = True

    if not found:
        # ── Bare integer (seconds) ──
        if re.fullmatch(r'\d+', raw):
            total_seconds = int(raw)
            found = True

    if not found:
        return "00:00:00"

    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def duration_to_seconds(raw: str) -> int:
    """Convert any duration string to total seconds."""
    hms = parse_duration(raw)
    parts = hms.split(":")
    try:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except Exception:
        return 0


def seconds_to_hms(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ─────────────────────────────────────────────
# Numeric Helpers
# ─────────────────────────────────────────────

def coerce_int(value) -> int:
    """Extract the first integer from value; return 0 on failure."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    nums = re.findall(r"\d+", str(value))
    return int(nums[0]) if nums else 0


def safe_title(name: str) -> str:
    """Strip and title-case a name; return empty string on falsy input."""
    if not name:
        return ""
    return " ".join(name.strip().split()).title()


def normalize_employee_name(name: str) -> str:
    """
    Normalize employee name by removing single-letter initials.
    e.g. 'Sachin G.' → 'Sachin',  'Rahul K Singh' → 'Rahul Singh'
    """
    if not name:
        return ""
    words = name.strip().split()
    filtered = []
    for word in words:
        clean = word.rstrip(".")
        if len(clean) == 1 and clean.isalpha():
            continue   # skip initials
        filtered.append(word)
    return safe_title(" ".join(filtered))


def extract_email_address(from_header: str) -> str:
    """
    Extract bare email address from a 'From' header.
    'John Doe <john@example.com>' → 'john@example.com'
    'john@example.com'            → 'john@example.com'
    """
    match = re.search(r'<([^>]+)>', from_header)
    if match:
        return match.group(1).strip().lower()
    # No angle brackets — try to find a bare email
    match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', from_header)
    if match:
        return match.group(0).strip().lower()
    return from_header.strip().lower()
