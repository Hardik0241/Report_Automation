"""
sheets_service.py — All Google Sheets operations.

Handles:
 • Auto-detection of the correct monthly sheet ("Mar-2026", "Apr-2026", …)
 • Sheet creation with headers + employee rows if the sheet doesn't exist yet
 • Date-row creation for every employee when a new date appears
 • Exact row lookup for (employee, date) pairs
 • Batched cell updates (minimises API calls)
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import gspread
client = gspread.authorize(creds)

from google.oauth2.service_account import Credentials

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
from error_handler import SheetUpdateError, with_retry

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

from google.oauth2 import service_account
import streamlit as st

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = st.secrets["GOOGLE_CREDENTIALS"]

creds = service_account.Credentials.from_service_account_info(
    creds_dict,
    scopes=SCOPES
)
class SheetsService:
    

    def __init__(self):
        import streamlit as st
        from google.oauth2 import service_account
        creds_dict = st.secrets["GOOGLE_CREDENTIALS"]
        client = gspread.authorize(creds)
        self._sales_ss = client.open_by_key(SALES_SPREADSHEET_ID)
        self._hr_ss    = client.open_by_key(HR_SPREADSHEET_ID)
        logger.info("SheetsService: connected to Sales and HR spreadsheets.")

    # ─────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────

    def _spreadsheet(self, department: str):
        return self._sales_ss if department == "Sales" else self._hr_ss

    @staticmethod
    def sheet_name(date_str: str) -> str:
        """'25-03-2026' → 'Mar-2026'"""
        dt = datetime.strptime(date_str, DATE_IN_SUBJECT_FORMAT)
        return dt.strftime(SHEET_NAME_FORMAT)

    def _get_worksheet(self, department: str, date_str: str) -> gspread.Worksheet:
        """Return the worksheet for a given department + date, creating it if absent."""
        ss   = self._spreadsheet(department)
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
        """Create a new monthly worksheet with headers and employee name column."""
        logger.info(f"Creating new sheet '{name}' for {department}")
        employees = SALES_EMPLOYEES if department == "Sales" else HR_EMPLOYEES
        headers   = SALES_HEADERS    if department == "Sales" else HR_HEADERS

        ws = ss.add_worksheet(title=name, rows=str(len(employees) * 35 + 10), cols="20")

        # Write header row
        ws.update("A1", [headers])

        # Pre-populate employee names in column B (rows 2…N)
        name_cells = [[emp] for emp in employees]
        ws.update(f"B2:B{len(employees) + 1}", name_cells)

        logger.info(f"Sheet '{name}' created with {len(employees)} employee rows.")
        return ws

    # ─────────────────────────────────────────
    # Date-block management
    # ─────────────────────────────────────────

    @with_retry()
    def ensure_date_for_all_employees(
        self, department: str, date_str: str
    ) -> None:
        """
        Ensure every employee has a row for `date_str`.
        Adds new rows at the end for employees that don't have this date yet.
        This should be called ONCE before writing any individual row.
        """
        employees = SALES_EMPLOYEES if department == "Sales" else HR_EMPLOYEES
        ws        = self._get_worksheet(department, date_str)

        # Fetch all values
        all_values = ws.get_all_values()   # list of rows (each row = list of cells)

        # Find which employees already have this date
        has_date: set = set()
        for row in all_values[1:]:   # skip header
            if row and row[0].strip() == date_str:
                name = row[1].strip() if len(row) > 1 else ""
                if name:
                    has_date.add(name)

        # Add new rows for employees that don't have this date
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
            logger.info(f"Added date '{date_str}' for {len(updates)} employee row(s) in {ws.title}")

    # ─────────────────────────────────────────
    # Row lookup
    # ─────────────────────────────────────────

    @with_retry()
    def find_employee_row(
        self, department: str, date_str: str, employee_name: str
    ) -> Optional[int]:
        """
        Find the 1-indexed row number where date==date_str AND name==employee_name.
        Returns None if not found.
        """
        ws         = self._get_worksheet(department, date_str)
        all_values = ws.get_all_values()

        for i, row in enumerate(all_values[1:], start=2):
            row_date = row[0].strip() if len(row) > 0 else ""
            row_name = row[1].strip() if len(row) > 1 else ""
            if row_date == date_str and row_name.lower() == employee_name.lower():
                return i

        logger.warning(
            f"Row not found: {employee_name} / {date_str} in {department} sheet {self.sheet_name(date_str)}"
        )
        return None

    # ─────────────────────────────────────────
    # Data write
    # ─────────────────────────────────────────

    @with_retry()
    def write_data(
        self,
        department:    str,
        date_str:      str,
        row_number:    int,
        data:          Dict,
    ) -> None:
        """
        Write all data fields for a single employee row in one batched update.
        Only writes the department-relevant columns.
        Auto-fills missing columns with defaults (0 for numeric, empty for text).
        """
        ws      = self._get_worksheet(department, date_str)
        mapping = SALES_COLUMN_MAPPING if department == "Sales" else HR_COLUMN_MAPPING

        # Build a dict: col_index → value
        cell_updates: Dict[int, object] = {}
        for field, col in mapping.items():
            if field in ("Date", "Employee Name"):
                continue   # These are already populated
            
            # Get value from data, or use auto-fill default
            if field in data:
                val = data[field]
            else:
                # Auto-fill missing fields with defaults
                if field == "Duration":
                    val = "00:00:00"
                elif field in ("Ref Added", "status Viewed", "Document Collected", 
                              "Total Calls", "Connected Calls", "Total Dialed", "Total Connected", 
                              "Interview Held", "Tomorrow Interview Lineups", "Prospect"):
                    # All numeric/count fields default to 0
                    val = 0
                else:
                    val = ""
            
            cell_updates[col] = val

        if not cell_updates:
            logger.warning("write_data: no fields to update.")
            return

        # Sort by column and batch as a single row update
        cols_sorted = sorted(cell_updates)
        min_col = cols_sorted[0]
        max_col = cols_sorted[-1]

        row_values = [""] * (max_col - min_col + 1)
        for col, val in cell_updates.items():
            row_values[col - min_col] = val

        col_letter_start = gspread.utils.rowcol_to_a1(row_number, min_col).rstrip("0123456789")
        col_letter_end   = gspread.utils.rowcol_to_a1(row_number, max_col).rstrip("0123456789")
        range_str        = f"{col_letter_start}{row_number}:{col_letter_end}{row_number}"

        ws.update(range_str, [row_values], value_input_option="USER_ENTERED")
        logger.info(
            f"Written {department} data for {data.get('employee_name')} "
            f"on {date_str} → row {row_number} ({ws.title})"
        )
    
    @with_retry()
    def mark_not_sent(
        self,
        department: str,
        date_str:   str,
    ) -> None:
        """
        Mark all employees who haven't submitted data for a date as 'Not Sent'.
        Finds rows with the date that have no data, and fills the first data column with 'Not Sent'.
        """
        ws        = self._get_worksheet(department, date_str)
        employees = SALES_EMPLOYEES if department == "Sales" else HR_EMPLOYEES
        mapping   = SALES_COLUMN_MAPPING if department == "Sales" else HR_COLUMN_MAPPING
        
        # Get the first data column (skip Date and Employee Name)
        first_data_col = min([col for field, col in mapping.items() if field not in ("Date", "Employee Name")])
        
        all_values = ws.get_all_values()
        updates: List[Dict] = []
        
        for emp in employees:
            # Find the row for this employee with this date
            row_num = None
            for i, row in enumerate(all_values[1:], start=2):
                row_date = row[0].strip() if len(row) > 0 else ""
                row_name = row[1].strip() if len(row) > 1 else ""
                if row_date == date_str and row_name.lower() == emp.lower():
                    row_num = i
                    break
            
            if row_num:
                # Check if this row has any data in the data columns
                has_data = False
                for field, col in mapping.items():
                    if field not in ("Date", "Employee Name"):
                        if col <= len(all_values[row_num - 1]):
                            cell_val = all_values[row_num - 1][col - 1].strip() if col - 1 < len(all_values[row_num - 1]) else ""
                            if cell_val:
                                has_data = True
                                break
                
                # If no data, mark as "Not Sent"
                if not has_data:
                    col_letter = gspread.utils.rowcol_to_a1(row_num, first_data_col).rstrip("0123456789")
                    updates.append({
                        "range": f"{col_letter}{row_num}",
                        "values": [["Not Sent"]]
                    })
        
        if updates:
            ws.batch_update(updates, value_input_option="USER_ENTERED")
            logger.info(f"Marked {len(updates)} employee(s) as 'Not Sent' for {date_str} in {department}")

    # ─────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────

    def list_sheets(self, department: str) -> List[str]:
        return [ws.title for ws in self._spreadsheet(department).worksheets()]
    
    def get_employees_for_date(
        self,
        department: str,
        date_str:   str,
    ) -> Dict[str, int]:
        """
        Get all employees and their row numbers for a given date.
        Returns: {employee_name: row_number}
        """
        ws = self._get_worksheet(department, date_str)
        all_values = ws.get_all_values()
        
        emp_rows = {}
        for i, row in enumerate(all_values[1:], start=2):
            row_date = row[0].strip() if len(row) > 0 else ""
            row_name = row[1].strip() if len(row) > 1 else ""
            if row_date == date_str and row_name:
                emp_rows[row_name] = i
        
        return emp_rows
