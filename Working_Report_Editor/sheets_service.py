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
    """Get credentials from either file or environment variable or Streamlit secrets."""
    
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

    def _spreadsheet(self, department: str):
        return self._sales_ss if department == "Sales" else self._hr_ss

    @staticmethod
    def sheet_name(date_str: str) -> str:
        dt = datetime.strptime(date_str, DATE_IN_SUBJECT_FORMAT)
        return dt.strftime(SHEET_NAME_FORMAT)

    def _apply_formatting(self, ws: gspread.Worksheet) -> None:
        """Apply Calibri font size 13 with center alignment to entire sheet."""
        try:
            spreadsheet_id = ws.spreadsheet.id
            sheet_id = ws.id
            
            requests = [{
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1000,
                        "startColumnIndex": 0,
                        "endColumnIndex": 26
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "fontFamily": "Calibri",
                                "fontSize": 13
                            },
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat.textFormat,userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment"
                }
            }]
            
            ws.spreadsheet.batch_update({"requests": requests})
            logger.info(f"Applied Calibri 13 center alignment to {ws.title}")
            
        except Exception as exc:
            logger.warning(f"Could not apply formatting: {exc}")

    def _get_worksheet(self, department: str, date_str: str) -> gspread.Worksheet:
        ss = self._spreadsheet(department)
        name = self.sheet_name(date_str)
        try:
            ws = ss.worksheet(name)
            logger.debug(f"Using existing sheet '{name}' ({department})")
            return ws
        except gspread.WorksheetNotFound:
            return self._create_worksheet(ss, name, department)

    def _create_worksheet(
        self,
        ss: gspread.Spreadsheet,
        name: str,
        department: str,
    ) -> gspread.Worksheet:
        logger.info(f"Creating new sheet '{name}' for {department}")
        employees = SALES_EMPLOYEES if department == "Sales" else HR_EMPLOYEES
        headers = SALES_HEADERS if department == "Sales" else HR_HEADERS

        ws = ss.add_worksheet(
            title=name,
            rows=str(len(employees) * 35 + 10),
            cols="20",
        )

        # Write header row
        ws.update("A1", [headers])
        
        # Pre-populate employee names in column B (rows 2…N)
        name_cells = [[emp] for emp in employees]
        ws.update(f"B2:B{len(employees) + 1}", name_cells)
        
        # Apply formatting to the entire sheet
        self._apply_formatting(ws)
        
        logger.info(f"Sheet '{name}' created with {len(employees)} employee rows.")
        return ws

    @with_retry()
    def ensure_date_for_all_employees(
        self, department: str, date_str: str
    ) -> None:
        """
        Ensure every employee has a row for `date_str`.
        Adds new rows at the end for employees that don't have this date yet.
        """
        employees = SALES_EMPLOYEES if department == "Sales" else HR_EMPLOYEES
        ws = self._get_worksheet(department, date_str)
        all_values = ws.get_all_values()

        # Find which employees already have this date
        has_date: set = set()
        for row in all_values[1:]:  # skip header
            if row and row[0].strip() == date_str:
                name = row[1].strip() if len(row) > 1 else ""
                if name:
                    has_date.add(name)

        # Add rows for employees missing this date
        updates: List[Dict] = []
        for emp in employees:
            if emp not in has_date:
                next_row = len(all_values) + 1 + len(updates)
                updates.append({
                    "range": f"A{next_row}:B{next_row}",
                    "values": [[date_str, emp]],
                })

        if updates:
            ws.batch_update(updates, value_input_option="USER_ENTERED")
            self._apply_formatting(ws)
            logger.info(f"Added date '{date_str}' for {len(updates)} employee(s) in {ws.title}")

    @with_retry()
    def find_employee_row(
        self, department: str, date_str: str, employee_name: str
    ) -> Optional[int]:
        """
        Find the 1-indexed row number where date==date_str AND name==employee_name.
        Returns None if not found.
        """
        ws = self._get_worksheet(department, date_str)
        all_values = ws.get_all_values()

        for i, row in enumerate(all_values[1:], start=2):
            row_date = row[0].strip() if len(row) > 0 else ""
            row_name = row[1].strip() if len(row) > 1 else ""
            if row_date == date_str and row_name.lower() == employee_name.lower():
                return i

        logger.warning(f"Row not found: {employee_name} / {date_str}")
        return None

    @with_retry()
    def write_data(
        self,
        department: str,
        date_str: str,
        row_number: int,
        data: Dict,
    ) -> None:
        """
        Write all data fields for a single employee row in one batched update.
        Auto-fills missing columns with sensible defaults.
        """
        ws = self._get_worksheet(department, date_str)
        mapping = SALES_COLUMN_MAPPING if department == "Sales" else HR_COLUMN_MAPPING

        cell_updates: Dict[int, object] = {}
        for field, col in mapping.items():
            if field in ("Date", "Employee Name"):
                continue  # already populated

            if field in data:
                val = data[field]
            else:
                # Default values for missing fields
                if field == "Duration":
                    val = "00:00:00"
                elif field in (
                    "Ref Added", "status Viewed", "Document Collected",
                    "Total Calls", "Connected Calls",
                    "Total Dialed", "Total Connected",
                    "Interview Held", "Tomorrow Interview Lineups", "Prospect",
                ):
                    val = 0
                else:
                    val = ""

            cell_updates[col] = val

        if not cell_updates:
            logger.warning("write_data: no fields to update.")
            return

        cols_sorted = sorted(cell_updates)
        min_col = cols_sorted[0]
        max_col = cols_sorted[-1]

        row_values = [""] * (max_col - min_col + 1)
        for col, val in cell_updates.items():
            row_values[col - min_col] = val

        col_start = gspread.utils.rowcol_to_a1(row_number, min_col).rstrip("0123456789")
        col_end = gspread.utils.rowcol_to_a1(row_number, max_col).rstrip("0123456789")
        range_str = f"{col_start}{row_number}:{col_end}{row_number}"

        ws.update(range_str, [row_values], value_input_option="USER_ENTERED")
        self._apply_formatting(ws)

        logger.info(f"Written {department} data for {data.get('employee_name')} on {date_str} → row {row_number} ({ws.title})")

    @with_retry()
    def mark_not_sent(self, department: str, date_str: str) -> None:
        """
        Mark all employees who haven't submitted data for date_str as 'Not Sent'.
        Only called for Sales department.
        """
        if department != "Sales":
            logger.info("Not Sent marking only applies to Sales department")
            return

        ws = self._get_worksheet(department, date_str)
        employees = SALES_EMPLOYEES
        mapping = SALES_COLUMN_MAPPING

        first_data_col = min(
            col for field, col in mapping.items()
            if field not in ("Date", "Employee Name")
        )

        all_values = ws.get_all_values()
        updates: List[Dict] = []

        for emp in employees:
            row_num = None
            for i, row in enumerate(all_values[1:], start=2):
                row_date = row[0].strip() if len(row) > 0 else ""
                row_name = row[1].strip() if len(row) > 1 else ""
                if row_date == date_str and row_name.lower() == emp.lower():
                    row_num = i
                    break

            if not row_num:
                continue

            # Check if row already has data
            has_data = False
            for field, col in mapping.items():
                if field not in ("Date", "Employee Name"):
                    cell_val = (
                        all_values[row_num - 1][col - 1].strip()
                        if col - 1 < len(all_values[row_num - 1])
                        else ""
                    )
                    if cell_val:
                        has_data = True
                        break

            if not has_data:
                col_letter = gspread.utils.rowcol_to_a1(
                    row_num, first_data_col
                ).rstrip("0123456789")
                updates.append({
                    "range": f"{col_letter}{row_num}",
                    "values": [["Not Sent"]],
                })

        if updates:
            ws.batch_update(updates, value_input_option="USER_ENTERED")
            self._apply_formatting(ws)
            logger.info(f"Marked {len(updates)} employee(s) as 'Not Sent' for {date_str} in {department}")

    def list_sheets(self, department: str) -> List[str]:
        """Return list of all sheet names in the spreadsheet."""
        return [ws.title for ws in self._spreadsheet(department).worksheets()]

    def get_employees_for_date(
        self, department: str, date_str: str
    ) -> Dict[str, int]:
        """Returns {employee_name: row_number} for a given date."""
        ws = self._get_worksheet(department, date_str)
        all_values = ws.get_all_values()
        emp_rows = {}
        for i, row in enumerate(all_values[1:], start=2):
            row_date = row[0].strip() if len(row) > 0 else ""
            row_name = row[1].strip() if len(row) > 1 else ""
            if row_date == date_str and row_name:
                emp_rows[row_name] = i
        return emp_rows
