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
    "Sayli", "Dhanshree", "Muskan", "Kalpita", "Komal", "Siddhesh",
]
HR_EMPLOYEES = [
    "Ruwaida", "Amanpreet", "Mehvish",
]
# ─────────────────────────────────────────────
# SALES EMAIL → NAME MAP
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
    "kalpita.edujam@gmail.com":    "Kalpita",
    "komals.edujam@gmail.com":     "Komal",
    "siddhesh.edujam@gmail.com":   "Siddhesh",
}
HR_EMAIL_MAP = {
    "ruwaida.hredujam@gmail.com":    "Ruwaida",
    "amanpreet.hredujam@gmail.com":  "Amanpreet",
    "mehvish.hredujam@gmail.com":    "Mehvish",
}
# ─────────────────────────────────────────────
# SALES DEADLINE RULE
# ─────────────────────────────────────────────
SALES_CUTOFF_HOUR = 0
SALES_CUTOFF_MINUTE = 0
# ─────────────────────────────────────────────
# SCHEDULER ACTIVE WINDOW
# ─────────────────────────────────────────────
ACTIVE_START_HOUR   = 14
ACTIVE_START_MINUTE = 30
ACTIVE_END_HOUR     = 23
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
DATE_IN_SUBJECT_FORMAT = "%d-%m-%Y"
SHEET_NAME_FORMAT      = "%b-%Y"
# Column mapping: field → column number (1-indexed)
SALES_COLUMN_MAPPING = {
    "Date":               1,
    "Employee Name":      2,
    "Total Dialed":       3,
    "Total Connected":    4,
    "Duration":           5,
    "Prospect":           6,
    "Ref Added":          7,
    "status Viewed":      8,
    "Document Collected": 9,
}
HR_COLUMN_MAPPING = {
    "Date":                       1,
    "Employee Name":              2,
    "Total Calls":                3,
    "Connected Calls":            4,
    "Duration":                   5,
    "Tomorrow Interview Lineups": 6,
    "Interview Held":             7,
}
SALES_HEADERS = list(SALES_COLUMN_MAPPING.keys())
HR_HEADERS    = list(HR_COLUMN_MAPPING.keys())
# ─────────────────────────────────────────────
# GMAIL CONFIGURATION - FIXED: Added modify scope
# ─────────────────────────────────────────────
GMAIL_QUERY        = "is:unread"
MAX_EMAILS_PER_RUN = 50
GMAIL_SCOPES       = [
    "https://www.googleapis.com/auth/gmail.modify",  # Allows marking as read
    "https://www.googleapis.com/auth/gmail.readonly"
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
DEPARTMENT_KEYWORDS = {
    "Sales": ["sales", "callyzer", "dialer", "prospect", "dialed", "dial"],
    "HR":    ["hr", "recruitment", "interview", "hiring", "lineup"],
}
DATE_PATTERNS = [
    r"(\d{2}-\d{2}-\d{4})",
    r"(\d{2}/\d{2}/\d{4})",
    r"(\d{4}-\d{2}-\d{2})",
]
MAX_RETRIES        = 3
RETRY_MIN_WAIT_SEC = 2
RETRY_MAX_WAIT_SEC = 10
LOG_DIR                = "logs"
PROCESSING_LOG_PATH    = f"{LOG_DIR}/processing_logs.csv"
ERROR_LOG_PATH         = f"{LOG_DIR}/error_logs.jsonl"
DUPLICATE_CACHE_PATH   = f"{LOG_DIR}/duplicate_cache.json"
DUPLICATE_WINDOW_HOURS = 24
