"""
sheets_service.py — All Google Sheets operations with Calibri font, size 13, center alignment.
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import gspread
from google.oauth2 import service_account

from config import (
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
)
from error_handler import with_retry

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_credentials():
    """Get credentials from either file or environment variable."""
    
    # Try 1: Load from credentials.json file (for local testing)
    if os.path.exists("credentials.json"):
        logger.info("Loading credentials from credentials.json file")
        return service_account.Credentials.from_service_account_file(
            "credentials.json",
            scopes=_SCOPES,
        )
    
    # Try 2: Load from GOOGLE_CREDENTIALS environment variable (GitHub Actions)
    creds_json = os.environ.get("GOOGLE_CREDENTIALS", "")
    if creds_json:
        logger.info("Loading credentials from GOOGLE_CREDENTIALS env var")
        try:
            creds_dict = json.loads(creds_json)
            return service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=_SCOPES,
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GOOGLE_CREDENTIALS JSON: {e}")
            raise
    
    # Try 3: Load from Streamlit secrets (for Streamlit Cloud)
    try:
        import streamlit as st
        if "GOOGLE_CREDENTIALS" in st.secrets:
            logger.info("Loading credentials from Streamlit secrets")
            creds_dict = dict(st.secrets["GOOGLE_CREDENTIALS"])
            return service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=_SCOPES,
            )
    except Exception as e:
        logger.warning(f"Could not load from Streamlit secrets: {e}")
    
    raise Exception("No valid credentials found in credentials.json, GOOGLE_CREDENTIALS env var, or Streamlit secrets")


def _get_gspread_client() -> gspread.Client:
    creds = _get_credentials()
    return gspread.authorize(creds)


class SheetsService:
    def __init__(self):
        client = _get_gspread_client()
        self._sales_ss = client.open_by_key(SALES_SPREADSHEET_ID)
        self._hr_ss = client.open_by_key(HR_SPREADSHEET_ID)
        logger.info("SheetsService: connected to Sales and HR spreadsheets.")

    # ... rest of your SheetsService class (keep everything else the same)
