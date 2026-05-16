"""
sheets_service.py — Google Sheets operations with Calibri font, size 13, center alignment
Handles: Not Sent, Invalid Report, Quota Error, actual data
Formatting: Dark black text (#000000), All borders on data cells
UPDATED: Fixed write_batch() to properly clear "Not Sent" status when data is written
UPDATED: Ensures Calibri font, size 13, center alignment, and all borders for every write operation
UPDATED: Fixed row index validation to prevent 400 errors
"""

import logging
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import gspread
from google.oauth2 import service_account

from config import (
    DATE_IN_SUBJECT_FORMAT, HR_COLUMN_MAPPING, HR_EMPLOYEES,
    HR_HEADERS, HR_SPREADSHEET_ID, SALES_COLUMN_MAPPING,
    SALES_EMPLOYEES, SALES_HEADERS, SALES_SPREADSHEET_ID, SHEET_NAME_FORMAT,
)
from error_handler import with_retry

logger = logging.getLogger(__name__)
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]


def _get_credentials():
    try:
        import streamlit as st
        if "GOOGLE_CREDENTIALS" in st.secrets:
            logger.info("Loading from Streamlit secrets")
            return service_account.Credentials.from_service_account_info(
                dict(st.secrets["GOOGLE_CREDENTIALS"]), scopes=_SCOPES)
    except Exception:
        pass

    creds_json = os.environ.get("GOOGLE_CREDENTIALS", "")
    if creds_json:
        logger.info("Loading from GOOGLE_CREDENTIALS env var")
        return service_account.Credentials.from_service_account_info(json.loads(creds_json), scopes=_SCOPES)

    if os.path.exists("credentials.json"):
        logger.info("Loading from credentials.json file")
        return service_account.Credentials.from_service_account_file("credentials.json", scopes=_SCOPES)

    raise Exception("No valid credentials found")


def _get_gspread_client() -> gspread.Client:
    return gspread.authorize(_get_credentials())


class SheetsService:
    def __init__(self):
        client = _get_gspread_client()
        self._sales_ss = client.open_by_key(SALES_SPREADSHEET_ID)
        self._hr_ss = client.open_by_key(HR_SPREADSHEET_ID)
        logger.info("Connected to Sales and HR spreadsheets")
        self._emp_cache: Dict[Tuple[str, str], Dict[str, int]] = {}
        self._ws_cache: Dict[Tuple[str, str], gspread.Worksheet] = {}
        self._worksheet_data_cache: Dict[Tuple[str, str], List[List[str]]] = {}
        self._cache_timestamp: Dict[Tuple[str, str], datetime] = {}
        self._cache_ttl_seconds = 60
        self._date_marked_not_sent: set = set()

    def _spreadsheet(self, department: str):
        return self._sales_ss if department == "Sales" else self._hr_ss

    @staticmethod
    def sheet_name(date_str: str) -> str:
        return datetime.strptime(date_str, DATE_IN_SUBJECT_FORMAT).strftime(SHEET_NAME_FORMAT)
    
    def get_column_mapping(self, department: str) -> Dict:
        return SALES_COLUMN_MAPPING if department == "Sales" else HR_COLUMN_MAPPING

    def _get_cached_worksheet_data(self, department: str, date_str: str) -> List[List[str]]:
        key = (department, date_str)
        now = datetime.now()
        
        if key in self._worksheet_data_cache and key in self._cache_timestamp:
            if (now - self._cache_timestamp[key]).seconds < self._cache_ttl_seconds:
                return self._worksheet_data_cache[key]
        
        ws = self._get_worksheet(department, date_str)
        data = ws.get_all_values()
        self._worksheet_data_cache[key] = data
        self._cache_timestamp[key] = now
        return data
    
    def _invalidate_cache(self, department: str, date_str: str) -> None:
        key = (department, date_str)
        if key in self._worksheet_data_cache:
            del self._worksheet_data_cache[key]
        if key in self._cache_timestamp:
            del self._cache_timestamp[key]

    def _apply_formatting(self, ws: gspread.Worksheet, range_str: str = None) -> None:
        try:
            if range_str is None:
                all_values = ws.get_all_values()
                if not all_values:
                    return
                max_row = len(all_values)
                max_col = len(all_values[0]) if all_values else 10
                max_row = min(max_row, 500)
                max_col = min(max_col, 20)
                range_str = f"A1:{gspread.utils.rowcol_to_a1(max_row, max_col)}"
            
            sheet_id = ws.id
            
            start_row_num = 1
            end_row_num = 100
            start_col = "A"
            end_col = "Z"
            
            if ":" in range_str:
                start_cell, end_cell = range_str.split(":")
                
                start_row_match = re.search(r'(\d+)$', start_cell)
                end_row_match = re.search(r'(\d+)$', end_cell)
                
                if start_row_match:
                    start_row_num = int(start_row_match.group(1))
                if end_row_match:
                    end_row_num = int(end_row_match.group(1))
                
                if end_row_num < start_row_num:
                    logger.warning(f"Invalid range: endRow {end_row_num} < startRow {start_row_num}, swapping")
                    start_row_num, end_row_num = end_row_num, start_row_num
                
                if end_row_num - start_row_num > 500:
                    end_row_num = start_row_num + 500
                    logger.info(f"Limited formatting range to {end_row_num - start_row_num} rows")
                
                start_col = ''.join(filter(str.isalpha, start_cell)) or "A"
                end_col = ''.join(filter(str.isalpha, end_cell)) or "Z"
            else:
                row_match = re.search(r'(\d+)$', range_str)
                if row_match:
                    start_row_num = int(row_match.group(1))
                    end_row_num = start_row_num
                start_col = ''.join(filter(str.isalpha, range_str)) or "A"
                end_col = start_col
            
            def col_to_index(col_letter):
                index = 0
                for char in col_letter:
                    index = index * 26 + (ord(char.upper()) - ord('A') + 1)
                return index - 1
            
            start_col_idx = col_to_index(start_col)
            end_col_idx = col_to_index(end_col)
            
            requests = [{
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row_num - 1,
                        "endRowIndex": end_row_num,
                        "startColumnIndex": start_col_idx,
                        "endColumnIndex": end_col_idx + 1
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "fontFamily": "Calibri",
                                "fontSize": 13,
                                "foregroundColor": {
                                    "red": 0.0,
                                    "green": 0.0,
                                    "blue": 0.0
                                }
                            },
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE",
                            "borders": {
                                "top": {"style": "SOLID"},
                                "bottom": {"style": "SOLID"},
                                "left": {"style": "SOLID"},
                                "right": {"style": "SOLID"}
                            }
                        }
