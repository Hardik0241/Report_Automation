"""
main.py — Production pipeline orchestrator with debug prints
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
    extract_date_from_subject,
    extract_email_address,
    received_timestamp_to_date,
)
from validator import DataValidator
from vision_parser import VisionParser

# === DEBUG PRINT AT THE VERY TOP ===
print("DEBUG: main.py started", flush=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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

    def process_email(self, email: Dict) -> Dict:
        t0 = time.time()
        email_id = email.get("id", "")
        subject = email.get("subject", "")
        body = email.get("body", "")
        attachments = email.get("attachments", [])
        email_hash = email.get("hash", "")
        from_header = email.get("from", "")
        sender_email = email.get("sender_email", "")
        received_at = email.get("received_at", datetime.now())
        preview = (subject or body)[:120]

        def _fail(reason: str, dept="", emp="", date="") -> Dict:
            self.tracker.log_status(
                preview, "FAILED", email_id, dept, emp, date,
                reason=reason, processing_time=time.time() - t0,
                sender_email=sender_email, sender_name=emp,
                received_time=received_at,
            )
            logger.warning(f"FAILED: {reason}")
            return {"status": "FAILED", "reason": reason}

        if self.tracker.is_duplicate(email_hash):
            self.tracker.log_status(preview, "DUPLICATE", email_id, processing_time=time.time() - t0)
            logger.info(f"DUPLICATE: {subject}")
            return {"status": "DUPLICATE"}

        try:
            email_data = self.parser.parse_email(body)
            if not email_data:
                return _fail("Email body parsing failed")

            print(f"DEBUG: parsed email_data = {email_data}", flush=True)

            dept = email_data.get("department", "Unknown")
            if dept == "Unknown":
                if sender_email in SALES_EMAIL_MAP:
                    dept = "Sales"
                elif sender_email in HR_EMAIL_MAP:
                    dept = "HR"

            if dept not in ("Sales", "HR"):
                return _fail(f"Cannot determine department. Sender: {sender_email}")

            email_data["department"] = dept
            employees = SALES_EMPLOYEES if dept == "Sales" else HR_EMPLOYEES

            body_name = email_data.get("employee_name", "").strip()
            email_map = SALES_EMAIL_MAP if dept == "Sales" else HR_EMAIL_MAP
            canonical_name = email_map.get(sender_email, "")

            if body_name:
                ok, name, _ = self.validator.validate_employee_name(body_name, dept)
                if ok:
                    canonical_name = name
                elif not canonical_name:
                    return _fail(f"Name '{body_name}' not valid and sender not in map", dept=dept)

            if not canonical_name:
                return _fail(f"No valid name for sender: {sender_email}", dept=dept)

            email_data["employee_name"] = canonical_name

            if dept == "Sales":
                date_str = received_at.strftime("%d-%m-%Y")
            else:
                date_str = extract_date_from_subject(subject)
                if not date_str:
                    date_str = received_at.strftime("%d-%m-%Y")

            email_data["date"] = date_str

            ok, field_err = self.validator.validate_required_fields(email_data, dept)
            if not ok:
                return _fail(field_err, dept=dept, emp=canonical_name, date=date_str)

            if dept == "Sales":
                screenshot_data = None
                for att in attachments:
                    if any(att.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg']):
                        screenshot_data = self.vision.parse_screenshot(att)
                        if screenshot_data:
                            break
                if not screenshot_data:
                    return _fail("Sales report requires screenshot", dept=dept, emp=canonical_name, date=date_str)

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
                    return _fail(f"Screenshot mismatch: {' | '.join(mismatches)}", dept=dept, emp=canonical_name, date=date_str)

                logger.info("Sales report validated successfully")

            self.sheets.ensure_date_for_all_employees(dept, date_str)
            row_num = self.sheets.find_employee_row(dept, date_str, canonical_name)
            if not row_num:
                return _fail(f"Row not found for {canonical_name}", dept=dept, emp=canonical_name, date=date_str)

            key = (dept, date_str)
            self._write_buffer.setdefault(key, []).append((row_num, email_data))

            self.tracker.mark_processed(email_hash)
            elapsed = time.time() - t0
            self.tracker.log_status(
                preview, "SUCCESS", email_id, dept, canonical_name, date_str,
                processing_time=elapsed, sender_email=sender_email,
                sender_name=canonical_name, received_time=received_at,
            )
            logger.info(f"SUCCESS — {dept} / {canonical_name} / {date_str} [{elapsed:.1f}s]")
            return {"status": "SUCCESS", "department": dept, "employee": canonical_name, "date": date_str}

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
        logger.info("=" * 60)
        logger.info("Report Processor started")
        print("DEBUG: run() method entered", flush=True)

        emails = self.gmail.fetch_emails()
        logger.info(f"Fetched {len(emails)} email(s) to process")
        print(f"DEBUG: fetched {len(emails)} emails", flush=True)

        results = []
        for idx, email in enumerate(emails, 1):
            logger.info(f"Processing {idx}/{len(emails)}: {email.get('subject', '')}")
            results.append(self.process_email(email))

        self._flush_writes()

        success = sum(1 for r in results if r["status"] == "SUCCESS")
        failed = sum(1 for r in results if r["status"] == "FAILED")
        duplicate = sum(1 for r in results if r["status"] == "DUPLICATE")

        logger.info(f"Run complete → SUCCESS={success}  FAILED={failed}  DUPLICATE={duplicate}")
        logger.info("=" * 60)
        return results


if __name__ == "__main__":
    print("DEBUG: Starting processor via if __name__ block", flush=True)
    processor = ReportProcessor()
    processor.run()
