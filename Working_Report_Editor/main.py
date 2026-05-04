"""
main.py — Production pipeline orchestrator
ALWAYS writes email body values to sheets, adds Report Status column for Sales
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
                logger.info(f"✅ Matched Sales employee: {name}")
                return ("Sales", name)
        
        for email, name in HR_EMAIL_MAP.items():
            if email.lower() == sender_lower:
                logger.info(f"✅ Matched HR employee: {name}")
                return ("HR", name)
        
        logger.warning(f"❌ No department match for: {sender_email}")
        return (None, None)

    def process_email(self, email: Dict) -> Dict:
        t0 = time.time()
        email_id = email.get("id", "")
        
        if email_id in PROCESSED_EMAILS:
            return {"status": "SKIPPED"}

        subject = email.get("subject", "")
        body = email.get("body", "")
        attachments = email.get("attachments", [])
        email_hash = email.get("hash", "")
        sender_email = email.get("sender_email", "")
        received_at = email.get("received_at", datetime.now())
        received_ms = email.get("received_ms", 0)
        preview = (subject or body)[:120]

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
            self.tracker.mark_processed(email_hash)
            self.tracker.log_status(
                preview, "SUCCESS", email_id, dept, emp, date_str,
                processing_time=time.time() - t0, sender_email=sender_email,
                sender_name=emp, received_time=received_at,
            )
            return {"status": "SUCCESS", "department": dept, "employee": emp, "date": date_str}

        if self.tracker.is_duplicate(email_hash):
            self.tracker.log_status(preview, "DUPLICATE", email_id)
            return {"status": "DUPLICATE"}

        try:
            email_data = self.parser.parse_email(body)
            if not email_data:
                return _fail("Email body parsing failed")

            dept, canonical_name = self._match_sender_to_department(sender_email)
            
            if dept is None:
                return _fail(f"Sender '{sender_email}' not in department maps")

            email_data["department"] = dept
            email_data["employee_name"] = canonical_name

            date_str = received_timestamp_to_date(received_ms) if received_ms else received_at.strftime("%d-%m-%Y")
            email_data["date"] = date_str

            # Validate required fields
            ok, field_err = self.validator.validate_required_fields(email_data, dept)
            if not ok:
                return _fail(field_err, dept=dept, emp=canonical_name, date=date_str)

            # Initialize report status (for Sales only)
            report_status = "Valid"
            
            # Screenshot validation for Sales only (determines status, doesn't block writing)
            if dept == "Sales" and attachments:
                screenshot_data = None
                for att in attachments:
                    if any(att.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg']):
                        screenshot_data = self.vision.parse_screenshot(att)
                        if screenshot_data:
                            break
                
                if screenshot_data:
                    email_calls = email_data.get("Total Dialed", 0)
                    email_connected = email_data.get("Total Connected", 0)
                    email_duration = email_data.get("Duration", "00:00:00")
                    
                    screen_calls = screenshot_data.get("Total Phone Calls", 0)
                    screen_connected = screenshot_data.get("Connected Calls", 0)
                    screen_duration = screenshot_data.get("Total Phone Calls Duration", "00:00:00")
                    
                    if (email_calls != screen_calls or 
                        email_connected != screen_connected or 
                        email_duration != screen_duration):
                        report_status = "Invalid"
                        logger.warning(f"⚠️ Screenshot mismatch for {canonical_name}")
                else:
                    logger.warning(f"⚠️ No screenshot parsed for {canonical_name}")

            # Add status to email_data
            email_data["report_status"] = report_status

            # Ensure sheet rows exist and write data (ALWAYS write email values)
            self.sheets.ensure_date_for_all_employees(dept, date_str)
            self.sheets.ensure_status_column(dept, date_str)
            row_num = self.sheets.find_employee_row(dept, date_str, canonical_name)

            if not row_num:
                return _fail(f"Row not found for {canonical_name}", dept=dept, emp=canonical_name, date=date_str)

            key = (dept, date_str)
            self._write_buffer.setdefault(key, []).append((row_num, email_data))

            # Mark invalid in status column separately if needed
            if dept == "Sales" and report_status == "Invalid":
                self.sheets.mark_invalid_report(dept, date_str, canonical_name)

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
