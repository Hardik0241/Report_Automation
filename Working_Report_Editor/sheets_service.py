"""
sheets_service.py — All Google Sheets operations with Calibri font, size 13, center alignment.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import gspread
from google.oauth2 import service_account

from config_cloud import (  # ← Changed from config to config_cloud
    DATE_IN_SUBJECT_FORMAT,
    HR_COLUMN_MAPPING,
    HR_EMPLOYEES,
    HR_HEADERS,
    HR_SPREADSHEET_ID,
    SALES_COLUMN_MAPPING,
    SALES_EMPLOYEES,
    SALES_HEADERS,
    SALES_SPREADSHEET_ID,
    SHEET_NAME_FORMAT,
    GOOGLE_CREDENTIALS_DICT,  # ← Added this
)
from error_handler import with_retry

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_gspread_client() -> gspread.Client:
    # Use the credentials dict from config_cloud
    creds = service_account.Credentials.from_service_account_info(
        GOOGLE_CREDENTIALS_DICT,  # ← Changed from st.secrets
        scopes=_SCOPES,
    )
    return gspread.authorize(creds)


# ... rest of your sheets_service.py code remains the same ...
