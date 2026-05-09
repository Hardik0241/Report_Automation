"""
scheduler.py — Automatic scheduler for the Report Automation System.

Runs the email processor every 20 minutes between 2:30 PM and 11:59 PM.
At midnight (00:00), marks all Sales employees who haven't submitted as "Not Sent".

Deploy this file on GitHub Actions or any server — it runs forever.
On your local PC: python scheduler.py
On GitHub Actions: triggered by cron (see .github/workflows/scheduler.yml)

UPDATED: Enhanced Not Sent marking to check actual data presence
"""

import logging
import time
from datetime import datetime

from config import (
    ACTIVE_END_HOUR, ACTIVE_END_MINUTE,
    ACTIVE_START_HOUR, ACTIVE_START_MINUTE,
    SALES_EMPLOYEES,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Set of dates already marked "Not Sent" today — prevents double-marking
_marked_not_sent_dates: set = set()


def is_active_window() -> bool:
    """
    Returns True if current time is within the active window:
    7:00 PM (19:00) to 11:59 PM (23:59).
    """
    now = datetime.now()
    h, m = now.hour, now.minute

    after_start = (h > ACTIVE_START_HOUR) or \
                  (h == ACTIVE_START_HOUR and m >= ACTIVE_START_MINUTE)
    before_end  = (h < ACTIVE_END_HOUR) or \
                  (h == ACTIVE_END_HOUR and m <= ACTIVE_END_MINUTE)

    return after_start and before_end


def run_processor():
    """Run the main email processing pipeline."""
    logger.info("▶ Running email processor …")
    try:
        from main import ReportProcessor
        results = ReportProcessor().run()
        ok  = sum(1 for r in results if r.get("status") == "SUCCESS")
        bad = sum(1 for r in results if r.get("status") == "FAILED")
        dup = sum(1 for r in results if r.get("status") == "DUPLICATE")
        logger.info(f"✅ Done — {ok} success, {bad} failed, {dup} duplicate")
    except Exception as exc:
        logger.error(f"Processor error: {exc}", exc_info=True)


def mark_not_sent_deadline():
    """
    Called at midnight. Marks all Sales employees who haven't submitted
    today as 'Not Sent'. Only runs once per date.
    """
    today = datetime.now().strftime("%d-%m-%Y")
    if today in _marked_not_sent_dates:
        return   # Already done for today

    logger.info(f"🕛 Midnight — marking unsubmitted Sales employees as 'Not Sent' for {today}")
    try:
        from sheets_service import SheetsService
        sheets = SheetsService()
        
        # First ensure all employees have rows for today
        sheets.ensure_date_for_all_employees("Sales", today)
        sheets.ensure_status_column("Sales", today)
        
        # Then mark Not Sent
        sheets.mark_not_sent("Sales", today)
        _marked_not_sent_dates.add(today)
        logger.info("✅ 'Not Sent' marking complete")
    except Exception as exc:
        logger.error(f"Failed to mark Not Sent: {exc}", exc_info=True)


def main():
    logger.info("═" * 55)
    logger.info("Scheduler started — active window: "
                f"{ACTIVE_START_HOUR:02d}:{ACTIVE_START_MINUTE:02d} – "
                f"{ACTIVE_END_HOUR:02d}:{ACTIVE_END_MINUTE:02d}")
    logger.info("Checks every 20 minutes during active window")
    logger.info("═" * 55)

    CHECK_INTERVAL_SECONDS = 20 * 60   # 20 minutes

    while True:
        now = datetime.now()

        # Midnight handler: mark Not Sent for Sales
        if now.hour == 0 and now.minute == 0:
            mark_not_sent_deadline()

        # Active window: run the processor
        if is_active_window():
            run_processor()
        else:
            logger.info(
                f"Outside active window ({now.strftime('%H:%M')}) — sleeping …"
            )

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
