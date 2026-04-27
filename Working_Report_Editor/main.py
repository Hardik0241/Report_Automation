# File: Working_Report_Editor/main.py
"""
main.py — Production pipeline orchestrator.

Key changes:
  - Buffer sheet writes in self._write_buffer and flush as batched writes at end of run.
  - This reduces Sheets API calls and allows updating all employees quickly.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config import (
    HR_EMAIL_MAP, HR_EMPLOYEES,
    SALES_CUTOFF_HOUR, SALES_CUTOFF_MINUTE,
    SALES_EMAIL_MAP, SALES_EMPLOYEES,
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
    received_timestamp_to_datetime,
)
from validator import DataValidator
from vision_parser import VisionParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ReportProcessor:

    def __init__(self):
        logger.info("Initialising ReportProcessor …")
        self.gmail     = GmailReader()
        self.parser    = GeminiParser()
        self.vision    = VisionParser()
        self.sheets    = SheetsService()
        self.tracker   = Tracker()
        self.validator = DataValidator()
        # Buffer: {(dept, date_str): [(row_num, data_dict), ...]}
        self._write_buffer: Dict[Tuple[str, str], List[Tuple[int, Dict]]] = {}

    # ─────────────────────────────────────────
    # Per-email pipeline
    # ─────────────────────────────────────────

    def process_email(self, email: Dict) -> Dict:
        t0          = time.time()
        email_id    = email.get("id", "")
        subject     = email.get("subject", "")
        body        = email.get("body", "")
        attachments = email.get("attachments", [])
        email_hash  = email.get("hash", "")
        from_header = email.get("from", "")
        received_at: datetime = email.get("received_at", datetime.now())
        received_ms: int      = email.get("received_ms", 0)
        preview     = (subject or body)[:120]

        # Parse sender header into email + name
        sender_email = extract_email_address(from_header)
        # Try to extract display name (part before angle brackets) otherwise use sender_email
        sender_name = ""
        if "<" in from_header and ">" in from_header:
            try:
                sender_name = from_header.split("<")[0].strip().strip('"').strip()
            except Exception:
                sender_name = sender_email
        else:
            possible_name = from_header.split("<")[0].strip().strip('"').strip()
            sender_name = possible_name if possible_name and "@" not in possible_name else sender_email

        def _fail(reason: str, dept="", emp="", date="") -> Dict:
            self.tracker.log_status(
                preview,
                status="FAILED",
                email_id=email_id,
                department=dept,
                employee_name=emp,
                date=date,
                reason=reason,
                processing_time=time.time() - t0,
                sender_email=sender_email,
                sender_name=sender_name,
                received_time=received_at,
            )
            logger.warning(f"FAILED [{email_id}]: {reason}")
            return {"status": "FAILED", "reason": reason}

        # ── 1. Duplicate check ────────────────
        if self.tracker.is_duplicate(email_hash):
            self.tracker.log_status(
                preview,
                status="DUPLICATE",
                email_id=email_id,
                reason="Already processed within window",
                processing_time=time.time() - t0,
                sender_email=sender_email,
                sender_name=sender_name,
                received_time=received_at,
            )
            logger.info(f"DUPLICATE skipped: {subject!r}")
            return {"status": "DUPLICATE"}

        try:
            # ── 2. Parse email body ───────────
            email_data = self.parser.parse_email(body)
            if not email_data:
                return _fail("Email body parsing failed completely")

            dept = email_data.get("department", "Unknown")

            # ── 3. Resolve department from sender if still Unknown ───────
            if dept == "Unknown":
                if sender_email in SALES_EMAIL_MAP:
                    dept = "Sales"
                elif sender_email in HR_EMAIL_MAP:
                    dept = "HR"

            if dept not in ("Sales", "HR"):
                return _fail(
                    f"Could not determine department — not in Sales/HR email maps "
                    f"and body detection failed. Sender: {sender_email}"
                )

            email_data["department"] = dept
            employees = SALES_EMPLOYEES if dept == "Sales" else HR_EMPLOYEES

            # ── 4. Resolve employee name ──────────────────────────────────
            body_name = email_data.get("employee_name", "").strip()

            if body_name:
                ok, canonical_name, name_reason = self.validator.validate_employee_name(
                    body_name, dept
                )
                if not ok:
                    email_map = SALES_EMAIL_MAP if dept == "Sales" else HR_EMAIL_MAP
                    canonical_name = email_map.get(sender_email, "")
                    if not canonical_name:
                        return _fail(
                            f"Name '{body_name}' not matched & sender not in email map",
                            dept=dept,
                        )
                    logger.info(f"Name from body failed; used email map: {canonical_name}")
            else:
                email_map = SALES_EMAIL_MAP if dept == "Sales" else HR_EMAIL_MAP
                canonical_name = email_map.get(sender_email, "")
                if not canonical_name:
                    return _fail(
                        f"No name in email body and sender '{sender_email}' "
                        f"not found in email map",
                        dept=dept,
                    )
                logger.info(f"No name in body; resolved from email map: {canonical_name}")

            email_data["employee_name"] = canonical_name

            # ── 5. Determine date ─────────────────────────────────────────
            if dept == "Sales":
                date_str = received_timestamp_to_date(received_ms) if received_ms \
                           else received_at.strftime("%d-%m-%Y")
                logger.info(f"Sales email — using received date: {date_str}")
            else:  # HR
                date_str = extract_date_from_subject(subject)
                if not date_str:
                    date_str = received_at.strftime("%d-%m-%Y")
                    logger.info(f"HR: no date in subject, using received date: {date_str}")

            email_data["date"] = date_str

            # ── 6. Sales midnight cutoff ──────────────────────────────────
            if dept == "Sales":
                if received_at.hour == SALES_CUTOFF_HOUR and received_at.minute >= SALES_CUTOFF_MINUTE:
                    return _fail(
                        f"Sales report received after midnight cutoff ({received_at.strftime('%H:%M')}). Deadline is 11:59 PM.",
                        dept=dept, emp=canonical_name, date=date_str,
                    )

            # ── 7. Required fields ────────────
            ok, field_err = self.validator.validate_required_fields(email_data, dept)
            if not ok:
                return _fail(field_err, dept=dept, emp=canonical_name, date=date_str)

            # ── 8. Screenshot parsing ─────────
            screenshot_data = None
            image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
            logger.info(f"Found {len(attachments)} attachment(s): {attachments}")

            for att in attachments:
                if any(att.lower().endswith(ext) for ext in image_exts):
                    screenshot_data = self.vision.parse_screenshot(att)
                    if screenshot_data:
                        logger.info(f"Screenshot parsed: {screenshot_data}")
                        break
                    else:
                        logger.warning(f"Failed to parse screenshot: {att}")

            if not screenshot_data:
                logger.warning("No screenshot data parsed from any attachment")

            # ── 9. Data match validation ──────
            ok, match_reason = self.validator.validate_data_match(
                email_data, screenshot_data, dept
            )
            if not ok:
                return _fail(match_reason, dept=dept, emp=canonical_name, date=date_str)

            # ── 10. Ensure sheet rows exist ──────────────
            # call ensure_date_for_all_employees once per dept/date (it is idempotent)
            self.sheets.ensure_date_for_all_employees(dept, date_str)

            # Find the employee row (cached by SheetsService where possible)
            row_num = self.sheets.find_employee_row(dept, date_str, canonical_name)
            if not row_num:
                return _fail(
                    f"Row not found for {canonical_name} on {date_str}",
                    dept=dept, emp=canonical_name, date=date_str,
                )

            # ── Buffer the write (do not perform single-row update now)
            key = (dept, date_str)
            self._write_buffer.setdefault(key, []).append((row_num, email_data))

            # ── 11. Mark processed + log ─────
            self.tracker.mark_processed(email_hash)
            elapsed = time.time() - t0
            self.tracker.log_status(
                preview,
                status="SUCCESS",
                email_id=email_id,
                department=dept,
                employee_name=canonical_name,
                date=date_str,
                processing_time=elapsed,
                sender_email=sender_email,
                sender_name=sender_name,
                received_time=received_at,
            )
            logger.info(
                f"SUCCESS — {dept} / {canonical_name} / {date_str} (row {row_num}) [{elapsed:.1f}s]"
            )
            return {
                "status":     "SUCCESS",
                "department": dept,
                "employee":   canonical_name,
                "date":       date_str,
                "row":        row_num,
            }

        except BaseProcessingError as exc:
            log_error(exc, {"email_id": email_id, "subject": subject})
            return _fail(str(exc))

        except Exception as exc:
            log_error(exc, {"email_id": email_id, "subject": subject})
            return _fail(f"Unexpected error: {exc}")

    # ─────────────────────────────────────────
    # Batch runner
    # ─────────────────────────────────────────
    def _flush_writes(self) -> None:
        """Flush buffered writes to Google Sheets using batch_update per (dept,date)."""
        if not self._write_buffer:
            logger.info("No buffered writes to flush.")
            return

        for (dept, date_str), entries in self._write_buffer.items():
            try:
                logger.info(f"Flushing {len(entries)} write(s) for {dept} / {date_str}")
                # entries is list of (row_num, data_dict)
                self.sheets.write_batch(dept, date_str, entries)
            except Exception as exc:
                logger.error(f"Failed to flush writes for {dept}/{date_str}: {exc}")
                # If flush fails, log individual failures in processing log for traceability
                for row_num, data in entries:
                    preview = (data.get("Email_Subject") or "")[:120]
                    self.tracker.log_status(
                        preview,
                        status="FAILED",
                        email_id="",
                        department=dept,
                        employee_name=data.get("employee_name", ""),
                        date=date_str,
                        reason=f"Batch write failed: {exc}",
                        processing_time=0.0,
                    )

        # Clear buffer after attempt
        self._write_buffer.clear()

    def run(self) -> List[Dict]:
        logger.info("═" * 60)
        logger.info("Report Processor started")

        emails = self.gmail.fetch_emails()
        logger.info(f"Fetched {len(emails)} email(s) to process.")

        results: List[Dict] = []
        processed_dates: set = set()

        for idx, email in enumerate(emails, start=1):
            logger.info(
                f"Processing email {idx}/{len(emails)}: {email.get('subject', '')!r}"
            )
            result = self.process_email(email)
            results.append(result)

            if result.get("status") == "SUCCESS":
                dept = result.get("department")
                date = result.get("date")
                if dept and date:
                    processed_dates.add((dept, date))

        # Flush buffered writes (batch to Sheets)
        try:
            self._flush_writes()
        except Exception as exc:
            logger.error(f"Error while flushing writes: {exc}")

        # Mark "Not Sent" only for Sales, only after processing all emails
        for dept, date_str in processed_dates:
            if dept == "Sales":
                logger.info(f"Marking unsubmitted Sales employees as 'Not Sent' for {date_str}")
                self.sheets.mark_not_sent(dept, date_str)
            # HR: no "Not Sent" marking

        success   = sum(1 for r in results if r["status"] == "SUCCESS")
        failed    = sum(1 for r in results if r["status"] == "FAILED")
        duplicate = sum(1 for r in results if r["status"] == "DUPLICATE")
        logger.info(
            f"Run complete → SUCCESS={success}  FAILED={failed}  DUPLICATE={duplicate}"
        )
        logger.info("═" * 60)
        return results


if __name__ == "__main__":
    processor = ReportProcessor()
    processor.run()
