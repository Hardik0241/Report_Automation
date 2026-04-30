"""
sheets_service.py — Google Sheets operations with Calibri font, size 13, center alignment
Handles: Not Sent (no email), Invalid Report (screenshot mismatch), and actual data
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

    def _spreadsheet(self, department: str):
        return self._sales_ss if department == "Sales" else self._hr_ss

    @staticmethod
    def sheet_name(date_str: str) -> str:
        return datetime.strptime(date_str, DATE_IN_SUBJECT_FORMAT).strftime(SHEET_NAME_FORMAT)

    def _apply_formatting(self, ws: gspread.Worksheet) -> None:
        try:
            ws.spreadsheet.batch_update({
                "requests": [{
                    "repeatCell": {
                        "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 1000,
                                  "startColumnIndex": 0, "endColumnIndex": 26},
                        "cell": {"userEnteredFormat": {"textFormat": {"fontFamily": "Calibri", "fontSize": 13},
                                                       "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"}},
                        "fields": "userEnteredFormat.textFormat,userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment"
                    }
                }]
            })
        except Exception as e:
            logger.warning(f"Formatting failed: {e}")

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
        logger.info(f"Created sheet '{name}'")
        return ws

    @with_retry()
    def ensure_date_for_all_employees(self, department: str, date_str: str) -> None:
        employees = SALES_EMPLOYEES if department == "Sales" else HR_EMPLOYEES
        ws = self._get_worksheet(department, date_str)
        all_values = ws.get_all_values()
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
            self._apply_formatting(ws)
            logger.info(f"Added date for {len(updates)} employees")

    @with_retry()
    def find_employee_row(self, department: str, date_str: str, employee_name: str) -> Optional[int]:
        ws = self._get_worksheet(department, date_str)
        all_values = ws.get_all_values()
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
        batch_requests = []
        for row_number, data in updates:
            cell_updates = {}
            for field, col in mapping.items():
                if field in ("Date", "Employee Name"):
                    continue
                val = data.get(field, 0 if field != "Duration" else "00:00:00")
                cell_updates[col] = val
            if not cell_updates:
                continue
            cols = sorted(cell_updates)
            min_col, max_col = cols[0], cols[-1]
            row_values = [cell_updates.get(c, "") for c in range(min_col, max_col + 1)]
            col_start = gspread.utils.rowcol_to_a1(row_number, min_col).rstrip("0123456789")
            col_end = gspread.utils.rowcol_to_a1(row_number, max_col).rstrip("0123456789")
            batch_requests.append({"range": f"{col_start}{row_number}:{col_end}{row_number}", "values": [row_values]})
        if batch_requests:
            ws.batch_update(batch_requests, value_input_option="USER_ENTERED")
            self._apply_formatting(ws)
            logger.info(f"Batch wrote {len(batch_requests)} rows to {ws.title}")

    @with_retry()
    def mark_not_sent(self, department: str, date_str: str) -> None:
        """Mark employees who didn't submit any report by deadline"""
        if department != "Sales":
            return

        ws = self._get_worksheet(department, date_str)
        employees = SALES_EMPLOYEES
        mapping = SALES_COLUMN_MAPPING

        first_data_col = min(col for field, col in mapping.items() if field not in ("Date", "Employee Name"))
        all_values = ws.get_all_values()
        updates = []

        for emp in employees:
            row_num = None
            for i, row in enumerate(all_values[1:], start=2):
                if row and row[0].strip() == date_str and row[1].strip().lower() == emp.lower():
                    row_num = i
                    break

            if not row_num:
                continue

            has_data = False
            for field, col in mapping.items():
                if field not in ("Date", "Employee Name"):
                    if col - 1 < len(all_values[row_num - 1]) and all_values[row_num - 1][col - 1].strip():
                        has_data = True
                        break

            if not has_data:
                col_letter = gspread.utils.rowcol_to_a1(row_num, first_data_col).rstrip("0123456789")
                updates.append({"range": f"{col_letter}{row_num}", "values": [["Not Sent"]]})

        if updates:
            ws.batch_update(updates, value_input_option="USER_ENTERED")
            self._apply_formatting(ws)
            logger.info(f"Marked {len(updates)} employee(s) as 'Not Sent' for {date_str}")

    @with_retry()
    def mark_invalid_report(self, department: str, date_str: str, employee_name: str) -> None:
        """Mark a specific employee's report as 'Invalid Report' when screenshot validation fails"""
        if department != "Sales":
            return

        ws = self._get_worksheet(department, date_str)
        mapping = SALES_COLUMN_MAPPING
        first_data_col = min(col for field, col in mapping.items() if field not in ("Date", "Employee Name"))

        all_values = ws.get_all_values()
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

        col_letter = gspread.utils.rowcol_to_a1(row_num, first_data_col).rstrip("0123456789")
        ws.update(f"{col_letter}{row_num}", [["Invalid Report"]], value_input_option="USER_ENTERED")
        self._apply_formatting(ws)
        logger.info(f"Marked {employee_name} as 'Invalid Report' for {date_str}")

    def list_sheets(self, department: str) -> List[str]:
        return [ws.title for ws in self._spreadsheet(department).worksheets()]

    def get_employees_for_date(self, department: str, date_str: str) -> Dict[str, int]:
        ws = self._get_worksheet(department, date_str)
        all_values = ws.get_all_values()
        emp_rows = {}
        for i, row in enumerate(all_values[1:], start=2):
            row_date = row[0].strip() if len(row) > 0 else ""
            row_name = row[1].strip() if len(row) > 1 else ""
            if row_date == date_str and row_name:
                emp_rows[row_name] = i
        return emp_rows
