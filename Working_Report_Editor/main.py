"""
main.py — Production pipeline orchestrator
Always writes email body values. Marks "Quota Error" when API fails.
Duplicate check is FIRST to prevent re-processing same email.
NOW WITH: Sheet check before processing to prevent duplicate writes
UPDATED: Screenshot validation is optional, email is source of truth
UPDATED: NO "Quota Error" status saved to sheet - it's a system issue
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config import (
    HR_EMAIL_MAP, HR_EMPLOYEES, SALES_EMAIL_MAP, SALES_EMPLOYEES,
)
from error_handler import BaseProcessingError, log_error
from gmail_reader import GmailReader
from gemini_parser import GeminiParser
from sheets_service import SheetsService
from tracker import Tracker
from utils import (
    extract_email_address,
    received_timestamp_to_date,
)
from validator import DataValidator
from vision_parser import VisionParser

print("DEBUG: main.py started", flush=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Used for tracking duplicates within the same run (temporary)
PROCESSED_EMAILS = set()


class ReportProcessor:
    def __init__(self):
        print("DEBUG: Initialising ReportProcessor", flush=True)
        logger.info("Initialising ReportProcessor...")
        self.gmail = GmailReader()
        self.parser = GeminiParser()
        self.vision = VisionParser()
        self.sheets = SheetsService()
        self.tracker = Tracker()
        self.validator = DataValidator()
        self._write_buffer: Dict[Tuple[str, str], List[Tuple[int, Dict]]] = {}

    def _match_sender_to_department(self, sender_email: str) -> Tuple[Optional[str], Optional[str]]:
        sender_lower = sender_email.lower()
        
        for email, name in SALES_EMAIL_MAP.items():
            if email.lower() == sender_lower:
                return ("Sales", name)
        
        for email, name in HR_EMAIL_MAP.items():
            if email.lower() == sender_lower:
                return ("HR", name)
        
        return (None, None)

    def _check_already_in_sheet(self, department: str, employee_name: str, date_str: str) -> bool:
        """Check if employee already has data in sheet for this date"""
        try:
            row_num = self.sheets.find_employee_row(department, date_str, employee_name)
            if not row_num:
                return False
            
            # Get the row data to check if any data exists
            ws = self.sheets._get_worksheet(department, date_str)
            row_data = ws.row_values(row_num)
            
            # Check if any numeric column (beyond Date and Employee Name) has data
            mapping = self.sheets.get_column_mapping(department)
            for field, col in mapping.items():
                if field not in ("Date", "Employee Name", "Report Status"):
                    if col - 1 < len(row_data) and row_data[col - 1].strip():
                        val = row_data[col - 1].strip()
                        if val not in ["", "0", "00:00:00", "Not Sent", "Invalid", "Quota Error"]:
                            logger.info(f"Employee {employee_name} already has data in sheet for {date_str}: {field}={val}")
                            return True
            
            # Also check Report Status column
            headers = ws.row_values(1)
            for i, header in enumerate(headers, start=1):
                if header == "Report Status":
                    if i - 1 < len(row_data) and row_data[i - 1].strip() in ["Valid", "Invalid", "Quota Error"]:
                        logger.info(f"Employee {employee_name} already has status {row_data[i - 1]} for {date_str}")
                        return True
            
            return False
        except Exception as e:
            logger.warning(f"Error checking sheet for {employee_name}: {e}")
            return False

    def process_email(self, email: Dict) -> Dict:
        t0 = time.time()
        email_id = email.get("id", "")
        subject = email.get("subject", "")
        body = email.get("body", "")
        attachments = email.get("attachments", [])
        email_hash = email.get("hash", "")
        sender_email = email.get("sender_email", "")
        received_at = email.get("received_at", datetime.now())
        received_ms = email.get("received_ms", 0)
        preview = (subject or body)[:120]

        # ─────────────────────────────────────────────
        # 1. DUPLICATE CHECK - FIRST AND FOREMOST!
        # ─────────────────────────────────────────────
        if self.tracker.is_duplicate(email_hash):
            self.tracker.log_status(
                preview, "DUPLICATE", email_id,
                processing_time=time.time() - t0,
                sender_email=sender_email,
                received_time=received_at,
            )
            logger.info(f"🚫 DUPLICATE skipped: {subject}")
            return {"status": "DUPLICATE"}

        # Also check within same run (temporary cache)
        if email_id in PROCESSED_EMAILS:
            logger.info(f"⏭️ Already processed in this run: {email_id}")
            return {"status": "SKIPPED"}

        logger.info(f"📧 Processing: {sender_email}")

        def _fail(reason: str, dept="", emp="", date="") -> Dict:
            self.tracker.log_status(
                preview, "FAILED", email_id, dept, emp, date, reason,
                processing_time=time.time() - t0, sender_email=sender_email,
                sender_name=emp, received_time=received_at,
            )
            return {"status": "FAILED", "reason": reason}

        def _success(dept: str, emp: str, date_str: str) -> Dict:
            PROCESSED_EMAILS.add(email_id)
            # Mark as processed in persistent cache
            self.tracker.mark_processed(email_hash)
            self.tracker.log_status(
                preview, "SUCCESS", email_id, dept, emp, date_str,
                processing_time=time.time() - t0, sender_email=sender_email,
                sender_name=emp, received_time=received_at,
            )
            return {"status": "SUCCESS", "department": dept, "employee": emp, "date": date_str}

        try:
            # Determine department and employee from sender email
            dept, canonical_name = self._match_sender_to_department(sender_email)
            
            if dept is None:
                return _fail(f"Sender '{sender_email}' not in department maps")

            # Get date from email received time
            date_str = received_timestamp_to_date(received_ms) if received_ms else received_at.strftime("%d-%m-%Y")
            
            # ─────────────────────────────────────────────
            # 2. CHECK SHEET BEFORE PROCESSING - PREVENT DUPLICATE WRITES!
            # ─────────────────────────────────────────────
            if self._check_already_in_sheet(dept, canonical_name, date_str):
                logger.info(f"✅ Employee {canonical_name} already has data in sheet for {date_str} - marking as DUPLICATE without reprocessing")
                self.tracker.mark_processed(email_hash)
                self.tracker.log_status(
                    preview, "DUPLICATE", email_id, dept, canonical_name, date_str,
                    "Already in sheet", processing_time=time.time() - t0,
                    sender_email=sender_email, sender_name=canonical_name, received_time=received_at,
                )
                return {"status": "DUPLICATE", "reason": "Already in sheet"}

            # Parse email body (pass sender_email for better department detection)
            email_data = self.parser.parse_email(body, sender_email)
            if not email_data:
                return _fail("Email body parsing failed", dept=dept, emp=canonical_name, date=date_str)

            email_data["department"] = dept
            email_data["employee_name"] = canonical_name
            email_data["date"] = date_str

            # Validate required fields
            ok, field_err = self.validator.validate_required_fields(email_data, dept)
            if not ok:
                return _fail(field_err, dept=dept, emp=canonical_name, date=date_str)

            # Initialize status - will be overwritten if screenshot validation happens
            report_status = None
            screenshot_mismatch = False

            # Screenshot validation for Sales only - OPTIONAL, NOT MANDATORY
            if dept == "Sales" and attachments:
                screenshot_data = None
                try:
                    for att in attachments:
                        if any(att.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg']):
                            screenshot_data = self.vision.parse_screenshot(att)
                            if screenshot_data:
                                logger.info(f"📸 Screenshot parsed for {canonical_name}: {screenshot_data}")
                                break
                except Exception as e:
                    # Handle quota error silently - don't mark as Quota Error in sheet
                    if "429" in str(e) or "quota" in str(e).lower():
                        logger.warning(f"⚠️ Quota error during screenshot parsing for {canonical_name} - continuing with email values only")
                        # DO NOT set report_status - just continue
                    else:
                        logger.warning(f"⚠️ Error parsing screenshot: {e}")
                
                # ONLY validate if screenshot was successfully parsed
                if screenshot_data:
                    email_calls = email_data.get("Total Dialed", 0)
                    email_connected = email_data.get("Total Connected", 0)
                    email_duration = email_data.get("Duration", "00:00:00")
                    
                    screen_calls = screenshot_data.get("Total Phone Calls", 0)
                    screen_connected = screenshot_data.get("Connected Calls", 0)
                    screen_duration = screenshot_data.get("Total Phone Calls Duration", "00:00:00")
                    
                    logger.info(f"📧 Email values for {canonical_name}: Calls={email_calls}, Connected={email_connected}, Duration={email_duration}")
                    logger.info(f"📸 Screenshot values for {canonical_name}: Calls={screen_calls}, Connected={screen_connected}, Duration={screen_duration}")
                    
                    # Compare only if email values are not zero (email is the source of truth)
                    if email_calls > 0 or email_connected > 0 or email_duration != "00:00:00":
                        if (email_calls != screen_calls or 
                            email_connected != screen_connected or 
                            email_duration != screen_duration):
                            screenshot_mismatch = True
                            logger.warning(f"⚠️ Screenshot mismatch for {canonical_name} - but email values will still be written")
                        else:
                            report_status = "Valid"
                            logger.info(f"✅ Screenshot verified for {canonical_name}")
                    else:
                        # If email values are zero but screenshot has values, use screenshot values
                        logger.info(f"📸 Email values were zero, using screenshot values for {canonical_name}")
                        email_data["Total Dialed"] = screen_calls
                        email_data["Total Connected"] = screen_connected
                        email_data["Duration"] = screen_duration
                        report_status = "Valid (from screenshot)"
                elif not screenshot_data:
                    logger.info(f"📸 No screenshot found for {canonical_name} - skipping validation")
            
            # Add status to email_data - NEVER set Quota Error in sheet
            if report_status:
                email_data["report_status"] = report_status
            elif screenshot_mismatch:
                # Log mismatch but don't mark as Invalid - email is source of truth
                email_data["report_status"] = "Email (screenshot mismatch)"
                logger.info(f"📊 {canonical_name}: Email values written despite screenshot mismatch")
            else:
                email_data["report_status"] = ""

            # Ensure sheet rows exist
            self.sheets.ensure_date_for_all_employees(dept, date_str)
            self.sheets.ensure_status_column(dept, date_str)
            row_num = self.sheets.find_employee_row(dept, date_str, canonical_name)

            if not row_num:
                return _fail(f"Row not found for {canonical_name}", dept=dept, emp=canonical_name, date=date_str)

            # Add to write buffer
            key = (dept, date_str)
            self._write_buffer.setdefault(key, []).append((row_num, email_data))

            # NO status column updates for system issues (Quota Error) - employee did nothing wrong
            # Only update status if there's a meaningful validation result
            if dept == "Sales" and report_status == "Valid":
                # Optional: You can add a method to mark as Valid if needed
                pass

            return _success(dept, canonical_name, date_str)

        except Exception as exc:
            log_error(exc, {"email_id": email_id})
            return _fail(f"Error: {exc}")

    def _flush_writes(self) -> None:
        if not self._write_buffer:
            return
        for (dept, date_str), entries in self._write_buffer.items():
            try:
                self.sheets.write_batch(dept, date_str, entries)
                logger.info(f"Flushed {len(entries)} writes for {dept}/{date_str}")
            except Exception as exc:
                logger.error(f"Failed to flush writes: {exc}")
        self._write_buffer.clear()

    def run(self) -> List[Dict]:
        global PROCESSED_EMAILS
        PROCESSED_EMAILS = set()
        
        logger.info("=" * 60)
        logger.info("Report Processor started")

        emails = self.gmail.fetch_emails()
        logger.info(f"📬 Fetched {len(emails)} email(s) to process")

        results = []
        for idx, email in enumerate(emails, 1):
            logger.info(f"Processing {idx}/{len(emails)}")
            results.append(self.process_email(email))

        self._flush_writes()

        success = sum(1 for r in results if r.get("status") == "SUCCESS")
        failed = sum(1 for r in results if r.get("status") == "FAILED")
        duplicate = sum(1 for r in results if r.get("status") == "DUPLICATE")

        logger.info(f"Run complete → SUCCESS={success}  FAILED={failed}  DUPLICATE={duplicate}")
        logger.info("=" * 60)
        return results


if __name__ == "__main__":
    processor = ReportProcessor()
    processor.run()
