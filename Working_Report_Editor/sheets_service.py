"""
sheets_service.py — Google Sheets operations with Calibri font, size 13, center alignment
Handles: Not Sent, Invalid Report, Quota Error, actual data
Formatting: Dark black text (#000000), All borders on data cells
UPDATED: Added mark_all_as_not_sent() for start-of-day marking
UPDATED: Added caching to reduce API calls and prevent rate limiting
"""

import logging
import json
import os
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

    def _apply_formatting(self, ws: gspread.Worksheet, range_str: str = None) -> None:
        try:
            if range_str is None:
                range_str = "A1:Z1000"
            
            sheet_id = ws.id
            
            if ":" in range_str:
                start_cell, end_cell = range_str.split(":")
                start_row = int(''.join(filter(str.isdigit, start_cell))) if any(c.isdigit() for c in start_cell) else 1
                start_col = ''.join(filter(str.isalpha, start_cell)) or "A"
                end_row = int(''.join(filter(str.isdigit, end_cell))) if any(c.isdigit() for c in end_cell) else 1000
                end_col = ''.join(filter(str.isalpha, end_cell)) or "Z"
            else:
                start_row = 1
                start_col = "A"
                end_row = 1000
                end_col = "Z"
            
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
                        "startRowIndex": start_row - 1,
                        "endRowIndex": end_row,
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
                    },
                    "fields": "userEnteredFormat.textFormat,userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment,userEnteredFormat.borders"
                }
            }]
            
            ws.spreadsheet.batch_update({"requests": requests})
            logger.info(f"Applied formatting (Calibri 13, black text, borders) to {ws.title}")
            
        except Exception as e:
            logger.warning(f"Formatting failed: {e}")

    def ensure_status_column(self, department: str, date_str: str) -> None:
        if department != "Sales":
            return
        
        ws = self._get_worksheet(department, date_str)
        try:
            headers = ws.row_values(1)
            if "Report Status" not in headers:
                last_col = len(headers) + 1
                ws.update_cell(1, last_col, "Report Status")
                self._apply_formatting(ws, f"{gspread.utils.rowcol_to_a1(1, last_col)}:{gspread.utils.rowcol_to_a1(1, last_col)}")
                logger.info(f"Added 'Report Status' column to {ws.title}")
        except Exception as e:
            logger.warning(f"Could not ensure status column: {e}")

    def _get_worksheet(self, department: str, date_str: str) -> gspread.Worksheet:
        key = (department, date_str)
        if key in self._ws_cache:
            return self._ws_cache[key]

        ss = self._spreadsheet(department)
        name = self.sheet_name(date_str)
        try:
            ws = ss.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self._create_worksheet(ss, name, department)

        self._ws_cache[key] = ws
        return ws

    def _create_worksheet(self, ss: gspread.Spreadsheet, name: str, department: str) -> gspread.Worksheet:
        employees = SALES_EMPLOYEES if department == "Sales" else HR_EMPLOYEES
        headers = SALES_HEADERS if department == "Sales" else HR_HEADERS
        ws = ss.add_worksheet(title=name, rows=str(len(employees) * 35 + 10), cols="20")
        ws.update("A1", [headers])
        ws.update(f"B2:B{len(employees) + 1}", [[emp] for emp in employees])
        self._apply_formatting(ws)
        logger.info(f"Created sheet '{name}' for {department}")
        return ws

    def mark_all_as_not_sent(self, department: str, date_str: str) -> None:
        """Mark ALL employees as 'Not Sent' in the Report Status column at start of day"""
        if department != "Sales":
            return
        
        date_key = f"{department}_{date_str}"
        if date_key in self._date_marked_not_sent:
            return
        
        ws = self._get_worksheet(department, date_str)
        employees = SALES_EMPLOYEES
        
        self.ensure_status_column(department, date_str)
        
        headers = ws.row_values(1)
        status_col = None
        for i, header in enumerate(headers, start=1):
            if header == "Report Status":
                status_col = i
                break
        
        if status_col is None:
            status_col = len(headers) + 1
            ws.update_cell(1, status_col, "Report Status")
        
        all_values = self._get_cached_worksheet_data(department, date_str)
        
        updates = []
        for i, row in enumerate(all_values[1:], start=2):
            row_date = row[0].strip() if len(row) > 0 else ""
            if row_date == date_str:
                col_letter = gspread.utils.rowcol_to_a1(i, status_col).rstrip("0123456789")
                range_str = f"{col_letter}{i}"
                updates.append({"range": range_str, "values": [["Not Sent"]]})
        
        if updates:
            for update in updates:
                ws.update(update["range"], update["values"], value_input_option="USER_ENTERED")
                self._apply_formatting(ws, update["range"])
            self._date_marked_not_sent.add(date_key)
            logger.info(f"Marked {len(updates)} employees as 'Not Sent' for {date_str}")

    @with_retry()
    def ensure_date_for_all_employees(self, department: str, date_str: str) -> None:
        employees = SALES_EMPLOYEES if department == "Sales" else HR_EMPLOYEES
        ws = self._get_worksheet(department, date_str)
        
        all_values = self._get_cached_worksheet_data(department, date_str)
        
        has_date = set()
        for row in all_values[1:]:
            if row and row[0].strip() == date_str:
                name = row[1].strip() if len(row) > 1 else ""
                if name:
                    has_date.add(name)
        updates = []
        for emp in employees:
            if emp not in has_date:
                updates.append({"range": f"A{len(all_values) + 1 + len(updates)}:B{len(all_values) + 1 + len(updates)}",
                                "values": [[date_str, emp]]})
        if updates:
            ws.batch_update(updates, value_input_option="USER_ENTERED")
            for update in updates:
                self._apply_formatting(ws, update["range"])
            key = (department, date_str)
            if key in self._worksheet_data_cache:
                del self._worksheet_data_cache[key]
            logger.info(f"Added date for {len(updates)} employees in {department}")

    @with_retry()
    def find_employee_row(self, department: str, date_str: str, employee_name: str) -> Optional[int]:
        ws = self._get_worksheet(department, date_str)
        all_values = self._get_cached_worksheet_data(department, date_str)
        for i, row in enumerate(all_values[1:], start=2):
            if row and row[0].strip() == date_str and row[1].strip().lower() == employee_name.lower():
                return i
        return None

    @with_retry()
    def write_batch(self, department: str, date_str: str, updates: List[Tuple[int, Dict]]) -> None:
        if not updates:
            return
        ws = self._get_worksheet(department, date_str)
        mapping = SALES_COLUMN_MAPPING if department == "Sales" else HR_COLUMN_MAPPING
        
        # Find status column index
        headers = ws.row_values(1)
        status_col = None
        for i, header in enumerate(headers, start=1):
            if header == "Report Status":
                status_col = i
                break
        
        batch_requests = []
        ranges_to_format = []
        
        for row_number, data in updates:
            cell_updates = {}
            for field, col in mapping.items():
                if field in ("Date", "Employee Name"):
                    continue
                if field == "Report Status":
                    continue
                val = data.get(field, 0 if field != "Duration" else "00:00:00")
                cell_updates[col] = val
            
            # Also update status column if we have a status
            if status_col and data.get("report_status"):
                cell_updates[status_col] = data.get("report_status")
            elif status_col:
                # Clear "Not Sent" when data is written
                cell_updates[status_col] = ""
            
            if not cell_updates:
                continue
            
            cols = sorted(cell_updates)
            min_col, max_col = cols[0], cols[-1]
            row_values = [cell_updates.get(c, "") for c in range(min_col, max_col + 1)]
            col_start = gspread.utils.rowcol_to_a1(row_number, min_col).rstrip("0123456789")
            col_end = gspread.utils.rowcol_to_a1(row_number, max_col).rstrip("0123456789")
            range_str = f"{col_start}{row_number}:{col_end}{row_number}"
            batch_requests.append({"range": range_str, "values": [row_values]})
            ranges_to_format.append(range_str)
        
        if batch_requests:
            ws.batch_update(batch_requests, value_input_option="USER_ENTERED")
            for range_str in ranges_to_format:
                self._apply_formatting(ws, range_str)
            key = (department, date_str)
            if key in self._worksheet_data_cache:
                del self._worksheet_data_cache[key]
            logger.info(f"Batch wrote {len(batch_requests)} rows to {ws.title}")

    @with_retry()
    def mark_not_sent(self, department: str, date_str: str) -> None:
        """Legacy method - kept for compatibility. Use mark_all_as_not_sent instead."""
        if department != "Sales":
            return
        self.mark_all_as_not_sent(department, date_str)

    @with_retry()
    def mark_invalid_report(self, department: str, date_str: str, employee_name: str) -> None:
        if department != "Sales":
            return

        ws = self._get_worksheet(department, date_str)
        
        headers = ws.row_values(1)
        status_col = None
        for i, header in enumerate(headers, start=1):
            if header == "Report Status":
                status_col = i
                break
        
        if status_col is None:
            status_col = len(headers) + 1
            ws.update_cell(1, status_col, "Report Status")
            self._apply_formatting(ws, f"{gspread.utils.rowcol_to_a1(1, status_col)}:{gspread.utils.rowcol_to_a1(1, status_col)}")
        
        all_values = self._get_cached_worksheet_data(department, date_str)
        row_num = None

        for i, row in enumerate(all_values[1:], start=2):
            row_date = row[0].strip() if len(row) > 0 else ""
            row_name = row[1].strip() if len(row) > 1 else ""
            if row_date == date_str and row_name.lower() == employee_name.lower():
                row_num = i
                break

        if not row_num:
            logger.warning(f"Row not found for {employee_name} on {date_str}")
            return

        col_letter = gspread.utils.rowcol_to_a1(row_num, status_col).rstrip("0123456789")
        range_str = f"{col_letter}{row_num}"
        ws.update(range_str, [["Invalid"]], value_input_option="USER_ENTERED")
        self._apply_formatting(ws, range_str)
        key = (department, date_str)
        if key in self._worksheet_data_cache:
            del self._worksheet_data_cache[key]
        logger.info(f"Marked {employee_name} as 'Invalid' for {date_str}")

    @with_retry()
    def mark_quota_error(self, department: str, date_str: str, employee_name: str) -> None:
        if department != "Sales":
            return

        ws = self._get_worksheet(department, date_str)
        
        headers = ws.row_values(1)
        status_col = None
        for i, header in enumerate(headers, start=1):
            if header == "Report Status":
                status_col = i
                break
        
        if status_col is None:
            status_col = len(headers) + 1
            ws.update_cell(1, status_col, "Report Status")
            self._apply_formatting(ws, f"{gspread.utils.rowcol_to_a1(1, status_col)}:{gspread.utils.rowcol_to_a1(1, status_col)}")
        
        all_values = self._get_cached_worksheet_data(department, date_str)
        row_num = None

        for i, row in enumerate(all_values[1:], start=2):
            row_date = row[0].strip() if len(row) > 0 else ""
            row_name = row[1].strip() if len(row) > 1 else ""
            if row_date == date_str and row_name.lower() == employee_name.lower():
                row_num = i
                break

        if not row_num:
            logger.warning(f"Row not found for {employee_name} on {date_str}")
            return

        col_letter = gspread.utils.rowcol_to_a1(row_num, status_col).rstrip("0123456789")
        range_str = f"{col_letter}{row_num}"
        ws.update(range_str, [["Quota Error"]], value_input_option="USER_ENTERED")
        self._apply_formatting(ws, range_str)
        key = (department, date_str)
        if key in self._worksheet_data_cache:
            del self._worksheet_data_cache[key]
        logger.info(f"Marked {employee_name} as 'Quota Error' for {date_str}")

    def list_sheets(self, department: str) -> List[str]:
        return [ws.title for ws in self._spreadsheet(department).worksheets()]

    def get_employees_for_date(self, department: str, date_str: str) -> Dict[str, int]:
        ws = self._get_worksheet(department, date_str)
        all_values = self._get_cached_worksheet_data(department, date_str)
        emp_rows = {}
        for i, row in enumerate(all_values[1:], start=2):
            row_date = row[0].strip() if len(row) > 0 else ""
            row_name = row[1].strip() if len(row) > 1 else ""
            if row_date == date_str and row_name:
                emp_rows[row_name] = i
        return emp_rows
