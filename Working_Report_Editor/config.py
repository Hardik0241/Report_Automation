"""
config.py — Complete configuration for Report Automation System
Works on Streamlit Cloud AND GitHub Actions
"""

import streamlit as st
import os
import json

# ============================================================
# LOAD SECRETS (Streamlit Cloud or Environment Variables)
# ============================================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SALES_SPREADSHEET_ID = st.secrets["SALES_SPREADSHEET_ID"]
    HR_SPREADSHEET_ID = st.secrets["HR_SPREADSHEET_ID"]
    GOOGLE_CREDENTIALS_DICT = dict(st.secrets["GOOGLE_CREDENTIALS"])
except Exception:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    SALES_SPREADSHEET_ID = os.environ.get("SALES_SPREADSHEET_ID", "")
    HR_SPREADSHEET_ID = os.environ.get("HR_SPREADSHEET_ID", "")
    creds_json = os.environ.get("GOOGLE_CREDENTIALS", "")
    if creds_json:
        GOOGLE_CREDENTIALS_DICT = json.loads(creds_json)
    else:
        GOOGLE_CREDENTIALS_DICT = {}

# ============================================================
# EMPLOYEE LISTS (Fixed order - DO NOT CHANGE)
# ============================================================
SALES_EMPLOYEES = [
    "Apoorva", "Abhijit", "Sakib", "Jayesh",
    "Saif", "Rajesh", "Manasvi", "Praful", "Sachin", "Aishwary",
    "Sayli", "Dhanshree", "Muskan", "Komal", "Siddhesh",
]

HR_EMPLOYEES = [
    "Ruwaida", "Amanpreet", "Mehvish", "Salomi",
]

# ============================================================
# EMAIL TO NAME MAPPING
# ============================================================
SALES_EMAIL_MAP = {
    "apoorva.edujam@gmail.com": "Apoorva",
    "abhijit.edujam@gmail.com": "Abhijit",
    "sakibs.edujam@gmail.com": "Sakib",
    "jayesha.edujam@gmail.com": "Jayesh",
    "saifd.edujam@gmail.com": "Saif",
    "rajeshp.edujam@gmail.com": "Rajesh",
    "manasvi.edujam@gmail.com": "Manasvi",
    "prafulp.edujam@gmail.com": "Praful",
    "sachingodara.edujam@gmail.com": "Sachin",
    "aishwary.edujam@gmail.com": "Aishwary",
    "saylip.edujam@gmail.com": "Sayli",
    "dhanshree.edujam@gmail.com": "Dhanshree",
    "muskan.edujam@gmail.com": "Muskan",
    "komals.edujam@gmail.com": "Komal",
    "siddhesh.edujam@gmail.com": "Siddhesh",
}

HR_EMAIL_MAP = {
    "ruwaida.hredujam@gmail.com": "Ruwaida",
    "amanpreet.hredujam@gmail.com": "Amanpreet",
    "mehvish.hredujam@gmail.com": "Mehvish",
    "salomi.hredujam@gmail.com": "Salomi",
}

# ============================================================
# Build Gmail Query with specific senders
# ============================================================
ALL_SALES_EMAILS = list(SALES_EMAIL_MAP.keys())
ALL_HR_EMAILS = list(HR_EMAIL_MAP.keys())
ALL_ALLOWED_EMAILS = ALL_SALES_EMAILS + ALL_HR_EMAILS

FROM_QUERY = " OR ".join([f"from:{email}" for email in ALL_ALLOWED_EMAILS])
GMAIL_QUERY = f"({FROM_QUERY}) is:unread"

# ============================================================
# MAX EMAILS PER RUN - Increased to process ALL emails (Sales + HR)
# ============================================================
MAX_EMAILS_PER_RUN = 20

# ============================================================
# SALES DEADLINE RULE
# ============================================================
SALES_CUTOFF_HOUR = 0
SALES_CUTOFF_MINUTE = 0

# ============================================================
# SCHEDULER ACTIVE WINDOW
# ============================================================
ACTIVE_START_HOUR = 19    # 7:00 PM
ACTIVE_START_MINUTE = 0
ACTIVE_END_HOUR = 23      # 11:59 PM
ACTIVE_END_MINUTE = 59

# ============================================================
# GOOGLE SHEETS CONFIGURATION
# ============================================================
DATE_IN_SUBJECT_FORMAT = "%d-%m-%Y"
SHEET_NAME_FORMAT = "%b-%Y"

# Sales column mapping - INCLUDES Status column
SALES_COLUMN_MAPPING = {
    "Date": 1,
    "Employee Name": 2,
    "Total Dialed": 3,
    "Total Connected": 4,
    "Duration": 5,
    "Prospect": 6,
    "Ref Added": 7,
    "status Viewed": 8,
    "Document Collected": 9,
    "Report Status": 10,
}

# HR column mapping - NO Status column
HR_COLUMN_MAPPING = {
    "Date": 1,
    "Employee Name": 2,
    "Total Calls": 3,
    "Connected Calls": 4,
    "Duration": 5,
    "Tomorrow Interview Lineups": 6,
    "Interview Held": 7,
}

SALES_HEADERS = list(SALES_COLUMN_MAPPING.keys())
HR_HEADERS = list(HR_COLUMN_MAPPING.keys())

# ============================================================
# GMAIL CONFIGURATION
# ============================================================
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
GMAIL_USER_ID = "me"

# ============================================================
# GEMINI CONFIGURATION
# ============================================================
GEMINI_MODEL = "gemini-2.5-flash"

# ============================================================
# VALIDATION RULES
# ============================================================
VALIDATION_RULES = {
    "Sales": {
        "required_fields": ["Total Dialed", "Total Connected", "Duration"],
        "tolerance_pct": 5,
        "name_fuzzy_threshold": 0.80,
    },
    "HR": {
        "required_fields": ["Total Calls", "Connected Calls", "Duration"],
        "tolerance_pct": 5,
        "name_fuzzy_threshold": 0.80,
    },
}

DEPARTMENT_KEYWORDS = {
    "Sales": ["sales", "callyzer", "dialer", "prospect", "dialed", "dial", "outgoing"],
    "HR": ["hr", "recruitment", "interview", "hiring", "lineup"],
}

DATE_PATTERNS = [
    r"(\d{2}-\d{2}-\d{4})",
    r"(\d{2}/\d{2}/\d{4})",
    r"(\d{4}-\d{2}-\d{2})",
]

# ============================================================
# RETRY / RESILIENCE
# ============================================================
MAX_RETRIES = 3
RETRY_MIN_WAIT_SEC = 2
RETRY_MAX_WAIT_SEC = 10

# ============================================================
# LOGGING / TRACKING
# ============================================================
LOG_DIR = "logs"
PROCESSING_LOG_PATH = f"{LOG_DIR}/processing_logs.csv"
ERROR_LOG_PATH = f"{LOG_DIR}/error_logs.jsonl"
DUPLICATE_CACHE_PATH = f"{LOG_DIR}/duplicate_cache.json"
DUPLICATE_WINDOW_HOURS = 24

# ============================================================
# SERVICE ACCOUNT FILE
# ============================================================
SERVICE_ACCOUNT_FILE = "credentials.json"
