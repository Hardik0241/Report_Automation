"""
config.py — Central configuration for Report Automation System.
All secrets loaded from .env. Never hardcode credentials here.
"""

import streamlit as st

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# ─────────────────────────────────────────────
# EMPLOYEE LISTS — Fixed order, never auto-sorted
# ─────────────────────────────────────────────
SALES_EMPLOYEES = [
    "Apoorva", "Abhijit", "Sakib", "Jayesh",
    "Saif", "Rajesh", "Manasvi", "Praful", "Sachin", "Aishwary",
    "Sayli", "Dhanshree", "Muskan",
]

HR_EMPLOYEES = [
    "Ruwaida", "Amanpreet", "Mehvish", "Deep"
]

# ─────────────────────────────────────────────
# SALES EMAIL → NAME MAP
# Map each sales employee's email address to their canonical name.
# This is used when the email body has no name — we identify the sender
# from their Gmail "From" address instead.
# UPDATE these with your employees' real email addresses.
# ─────────────────────────────────────────────
SALES_EMAIL_MAP = {
    "apoorva.edujam@gmail.com":   "Apoorva",
    "abhijit.edujam@gmail.com":   "Abhijit",
    "sakibs.edujam@gmail.com":     "Sakib",
    "jayesha.edujam@gmail.com":    "Jayesh",
    "saifd.edujam@gmail.com":      "Saif",
    "rajeshp.edujam@gmail.com":    "Rajesh",
    "manasvi.edujam@gmail.com":   "Manasvi",
    "prafulp.edujam@gmail.com":    "Praful",
    "sachingodara.edujam@gmail.com":    "Sachin",
    "aishwary.edujam@gmail.com":  "Aishwary",
    "saylip.edujam@gmail.com":     "Sayli",
    "dhanshree.edujam@gmail.com": "Dhanshree",
    "muskan.edujam@gmail.com":    "Muskan",
}

HR_EMAIL_MAP = {
    "ruwaida.hredujam@gmail.com":    "Ruwaida",
    "amanpreet.hredujam@gmail.com":  "Amanpreet",
    "mehvish.hredujam@gmail.com":    "Mehvish",
    "deep.hredujam@gmail.com":       "Deep",
}

# ─────────────────────────────────────────────
# SALES DEADLINE RULE
# Emails received at or after SALES_CUTOFF_HOUR (midnight = 0) are rejected.
# Only applies to Sales department. HR has no deadline.
# ─────────────────────────────────────────────
SALES_CUTOFF_HOUR = 0       # 12:00 AM — emails received on/after this hour are rejected
SALES_CUTOFF_MINUTE = 0

# ─────────────────────────────────────────────
# SCHEDULER ACTIVE WINDOW (for scheduler.py)
# Script only runs between ACTIVE_START and ACTIVE_END each day.
# ─────────────────────────────────────────────
ACTIVE_START_HOUR   = 14   # 2:30 PM
ACTIVE_START_MINUTE = 30
ACTIVE_END_HOUR     = 23   # 11:59 PM
ACTIVE_END_MINUTE   = 59

# ─────────────────────────────────────────────
# GOOGLE SHEETS CONFIGURATION
# ─────────────────────────────────────────────
import streamlit as st
from google.oauth2 import service_account

creds_dict = st.secrets["GOOGLE_CREDENTIALS"]
creds = service_account.Credentials.from_service_account_info(creds_dict)

SALES_SPREADSHEET_ID = st.secrets["SALES_SPREADSHEET_ID"]
HR_SPREADSHEET_ID    = st.secrets["HR_SPREADSHEET_ID"]

# Sheet name format derived from date: "25-03-2026" → "Apr-2026"
DATE_IN_SUBJECT_FORMAT = "%d-%m-%Y"
SHEET_NAME_FORMAT      = "%b-%Y"

# Column mapping: field → column number (1-indexed)
SALES_COLUMN_MAPPING = {
    "Date":               1,   # A
    "Employee Name":      2,   # B
    "Total Dialed":       3,   # C
    "Total Connected":    4,   # D
    "Duration":           5,   # E
    "Prospect":           6,   # F
    "Ref Added":          7,   # G
    "status Viewed":      8,   # H
    "Document Collected": 9,   # I
}

HR_COLUMN_MAPPING = {
    "Date":                       1,   # A
    "Employee Name":              2,   # B
    "Total Calls":                3,   # C
    "Connected Calls":            4,   # D
    "Duration":                   5,   # E
    "Tomorrow Interview Lineups": 6,   # F
    "Interview Held":             7,   # G
}

SALES_HEADERS = list(SALES_COLUMN_MAPPING.keys())
HR_HEADERS    = list(HR_COLUMN_MAPPING.keys())

# ─────────────────────────────────────────────
# GMAIL CONFIGURATION
# ─────────────────────────────────────────────
GMAIL_QUERY        = "is:unread"      # Fetch ALL unread mail — we filter by sender
MAX_EMAILS_PER_RUN = 50
GMAIL_SCOPES       = [
    "https://www.googleapis.com/auth/gmail.modify",
]
GMAIL_USER_ID = "me"

# ─────────────────────────────────────────────
# GEMINI CONFIGURATION
# ─────────────────────────────────────────────
import streamlit as st

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GEMINI_MODEL   = "gemini-2.5-flash"

# ─────────────────────────────────────────────
# VALIDATION RULES
# ─────────────────────────────────────────────
VALIDATION_RULES = {
    "Sales": {
        "required_fields":      ["Total Dialed", "Total Connected", "Duration"],
        "numeric_fields":       ["Total Dialed", "Total Connected", "Prospect"],
        "tolerance_pct":        5,
        "name_fuzzy_threshold": 0.80,
    },
    "HR": {
        "required_fields":      ["Total Calls", "Connected Calls", "Duration"],
        "numeric_fields":       ["Total Calls", "Connected Calls",
                                 "Tomorrow Interview Lineups", "Interview Held"],
        "tolerance_pct":        5,
        "name_fuzzy_threshold": 0.80,
    },
}

# Keywords used to auto-detect department when not explicitly stated
DEPARTMENT_KEYWORDS = {
    "Sales": ["sales", "callyzer", "dialer", "prospect", "dialed", "dial"],
    "HR":    ["hr", "recruitment", "interview", "hiring", "lineup"],
}

# Date patterns tried in order during subject extraction
DATE_PATTERNS = [
    r"(\d{2}-\d{2}-\d{4})",   # DD-MM-YYYY
    r"(\d{2}/\d{2}/\d{4})",   # DD/MM/YYYY
    r"(\d{4}-\d{2}-\d{2})",   # YYYY-MM-DD
]

# ─────────────────────────────────────────────
# RETRY / RESILIENCE
# ─────────────────────────────────────────────
MAX_RETRIES        = 3
RETRY_MIN_WAIT_SEC = 2
RETRY_MAX_WAIT_SEC = 10

# ─────────────────────────────────────────────
# LOGGING / TRACKING
# ─────────────────────────────────────────────
LOG_DIR                = "logs"
PROCESSING_LOG_PATH    = f"{LOG_DIR}/processing_logs.csv"
ERROR_LOG_PATH         = f"{LOG_DIR}/error_logs.jsonl"
DUPLICATE_CACHE_PATH   = f"{LOG_DIR}/duplicate_cache.json"
DUPLICATE_WINDOW_HOURS = 24
