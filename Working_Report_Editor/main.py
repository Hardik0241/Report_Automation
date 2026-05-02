"""
main.py — Production pipeline orchestrator
Always writes email body values, adds Report Status column
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

# Track processed email IDs to avoid re-processing within same run
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
        """Match sender email to department and return (department, employee_name)."""
        sender_lower = sender_email.lower()
        
        for email, name in SALES_EMAIL_MAP.items():
            if email.lower() == sender_lower:
                logger.info(f"✅ Matched Sales employee: {name} via email: {email}")
                return ("Sales", name)
        
        for email, name in HR_EMAIL_MAP.items():
            if email.lower() == sender_lower:
                logger.info(f"✅ Matched HR employee: {name} via email: {email}")
                return ("HR", name)
        
        logger.warning(f"❌ No department match for sender email: {sender_email}")
        return (None, None)

    def process_email(self, email: Dict) -> Dict:
        t0 = time.time()
        email_id = email.get("id", "")
        
        if email_id in PROCESSED_EMAILS:
            logger.info(f"Skipping already processed email: {email_id}")
            return {"status": "SKIPPED", "reason": "Already processed"}
        
        subject = email.get("subject", "")
        body = email.get("body", "")
        attachments = email.get("attachments", [])
        email_hash = email.get("hash", "")
        from_header = email.get("from", "")
        sender_email = email.get("sender_email", "")
        received_at = email.get("received_at", datetime.now())
        received_ms = email.get("received_ms", 0)
        preview = (subject or body)[:120]

        logger.info(f"📧 Processing email from sender: '{sender_email}'")

        def _fail(reason: str, dept="", emp="", date="") -> Dict:
            self.tracker.log_status(
                preview, "FAILED", email_id, dept, emp, date,
                reason=reason, processing_time=time.time() - t0,
                sender_email=sender_email, sender_name=emp,
                received_time=received_at,
            )
            logger.warning(f"FAILED [{email_id}]: {reason}")
            return {"status": "FAILED", "reason": reason}

        def _success(dept: str, emp: str, date_str: str) -> Dict:
            PROCESSED_EMAILS.add(email_id)
            self.tracker.mark_processed(email_hash)
            elapsed = time.time() - t0
            self.tracker.log_status(
                preview, "SUCCESS", email_id, dept, emp, date_str,
                processing_time=elapsed, sender_email=sender_email,
                sender_name=emp, received_time=received_at,
            )
            logger.info(f"SUCCESS — {dept} / {emp} / {date_str} [{elapsed:.1f}s]")
            return {"status": "SUCCESS", "department": dept, "employee": emp, "date": date_str}

        if self.tracker.is_duplicate(email_hash):
            self.tracker.log_status(preview, "DUPLICATE", email_id, processing_time=time.time() - t0)
            logger.info(f"DUPLICATE skipped: {subject}")
            return {"status": "DUPLICATE"}

        try:
            email_data = self.parser.parse_email(body)
            if not email_data:
                return _fail("Email body parsing failed")

            print(f"DEBUG: parsed email_data = {email_data}", flush=True)

            dept, canonical_name = self._match_sender_to_department(sender_email)
            
            if dept is None:
                dept = email_data.get("department", "Unknown")
                if dept == "Unknown":
                    return _fail(f"Sender '{sender_email}' not found in Sales or HR email maps")
                
                canonical_name = ""
                body_name = email_data.get("employee_name", "").strip()
                if body_name:
                    ok, name, _ = self.validator.validate_employee_name(body_name, dept)
                    if ok:
                        canonical_name = name
                
                if not canonical_name:
                    return _fail(f"Cannot determine name for sender: {sender_email}", dept=dept)

            email_data["department"] = dept
            email_data["employee_name"] = canonical_name

            date_str = received_timestamp_to_date(received_ms) if received_ms else received_at.strftime("%d-%m-%Y")
            logger.info(f"📅 Using received date: {date_str} for {dept} employee: {canonical_name}")

            email_data["date"] = date_str

            ok, field_err = self.validator.validate_required_fields(email_data, dept)
            if not ok:
                return _fail(field_err, dept=dept, emp=canonical_name, date=date_str)

            # Initialize report status as "Valid" (will change if mismatch)
            report_status = "Valid"
            
            # Screenshot validation ONLY for Sales department - determines status only, doesn't block writing
            if dept == "Sales":
                logger.info(f"📸 Processing screenshot for Sales employee: {canonical_name}")
                if attachments:
                    screenshot_data = None
                    for att in attachments:
                        if any(att.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg']):
                            screenshot_data = self.vision.parse_screenshot(att)
                            if screenshot_data:
                                logger.info(f"Screenshot parsed for {canonical_name}: {screenshot_data}")
                                break
                    
                    if screenshot_data:
                        email_calls = email_data.get("Total Dialed", 0)
                        email_connected = email_data.get("Total Connected", 0)
                        email_duration = email_data.get("Duration", "00:00:00")
                        
                        screen_calls = screenshot_data.get("Total Phone Calls", 0)
                        screen_connected = screenshot_data.get("Connected Calls", 0)
                        screen_duration = screenshot_data.get("Total Phone Calls Duration", "00:00:00")
                        
                        mismatches = []
                        if email_calls != screen_calls:
                            mismatches.append(f"Calls: email={email_calls}, screenshot={screen_calls}")
                        if email_connected != screen_connected:
                            mismatches.append(f"Connected: email={email_connected}, screenshot={screen_connected}")
                        if email_duration != screen_duration:
                            mismatches.append(f"Duration: email={email_duration}, screenshot={screen_duration}")
                        
                        if mismatches:
                            report_status = "Invalid"
                            logger.warning(f"⚠️ Screenshot mismatch for {canonical_name}: {' | '.join(mismatches)}")
                            # Mark as invalid report but DON'T fail - still write data
                            self.sheets.mark_invalid_report(dept, date_str, canonical_name)
                        else:
                            logger.info(f"✅ Screenshot validation PASSED for {canonical_name}")
                    else:
                        logger.warning(f"⚠️ No screenshot parsed for {canonical_name}")
                else:
                    logger.warning(f"⚠️ No attachments found for {canonical_name}")

            # Add report status to email_data for writing to sheet
            email_data["report_status"] = report_status

            if dept == "HR":
                logger.info(f"👥 HR report for {canonical_name} - no screenshot validation required")

            # Ensure sheet rows exist and write data (ALWAYS write email body values)
            self.sheets.ensure_date_for_all_employees(dept, date_str)
            self.sheets.ensure_status_column(dept)  # Ensure Status column exists
            row_num = self.sheets.find_employee_row(dept, date_str, canonical_name)

            if not row_num:
                return _fail(f"Row not found for {canonical_name}", dept=dept, emp=canonical_name, date=date_str)

            key = (dept, date_str)
            self._write_buffer.setdefault(key, []).append((row_num, email_data))

            return _success(dept, canonical_name, date_str)

        except BaseProcessingError as exc:
            log_error(exc, {"email_id": email_id})
            return _fail(str(exc))
        except Exception as exc:
            log_error(exc, {"email_id": email_id})
            return _fail(f"Unexpected error: {exc}")

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
        print("DEBUG: run() method entered", flush=True)

        emails = self.gmail.fetch_emails()
        logger.info(f"📬 Fetched {len(emails)} email(s) to process")
        print(f"DEBUG: fetched {len(emails)} emails", flush=True)

        unique_senders = set()
        for email in emails:
            sender = email.get("sender_email", "")
            if sender:
                unique_senders.add(sender)
        logger.info(f"📧 Unique senders found: {unique_senders}")

        results = []
        for idx, email in enumerate(emails, 1):
            logger.info(f"Processing {idx}/{len(emails)}: {email.get('subject', '')}")
            results.append(self.process_email(email))

        self._flush_writes()

        success = sum(1 for r in results if r.get("status") == "SUCCESS")
        failed = sum(1 for r in results if r.get("status") == "FAILED")
        duplicate = sum(1 for r in results if r.get("status") == "DUPLICATE")

        logger.info(f"Run complete → SUCCESS={success}  FAILED={failed}  DUPLICATE={duplicate}")
        logger.info("=" * 60)
        return results


if __name__ == "__main__":
    print("DEBUG: Starting processor via if __name__ block", flush=True)
    processor = ReportProcessor()
    processor.run()
