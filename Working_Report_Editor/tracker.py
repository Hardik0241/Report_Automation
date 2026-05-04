"""
tracker.py — Email processing tracker with proper logging
"""

import csv
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config import (
    DUPLICATE_CACHE_PATH,
    DUPLICATE_WINDOW_HOURS,
    LOG_DIR,
    PROCESSING_LOG_PATH,
)

logger = logging.getLogger(__name__)

_CSV_COLUMNS = [
    "Timestamp", "Email_ID", "Email_Subject", "Sender_Email",
    "Sender_Name", "Received_Time", "Status", "Department",
    "Employee_Name", "Date", "Reason", "Processing_Time_Sec",
]


class Tracker:
    def __init__(self):
        # Create logs directory in multiple possible locations
        for path in [LOG_DIR, "logs", "Working_Report_Editor/logs"]:
            try:
                os.makedirs(path, exist_ok=True)
                logger.info(f"Created/verified logs directory: {path}")
            except Exception as e:
                logger.warning(f"Could not create {path}: {e}")
        
        # Set the actual path to use
        self.log_path = PROCESSING_LOG_PATH
        if not os.path.exists(LOG_DIR):
            self.log_path = "logs/processing_logs.csv"
        
        self._init_csv()
        self._init_cache()

    def _init_csv(self):
        """Initialize CSV with headers if it doesn't exist"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            
            if not os.path.exists(self.log_path):
                with open(self.log_path, "w", newline="", encoding="utf-8") as fh:
                    csv.writer(fh).writerow(_CSV_COLUMNS)
                logger.info(f"Created new log file at: {self.log_path}")
        except Exception as exc:
            logger.error(f"Failed to init CSV: {exc}")

    def log_status(self, email_preview: str, status: str, email_id: str = "",
                   department: str = "", employee_name: str = "", date: str = "",
                   reason: str = "", processing_time: float = 0.0,
                   sender_email: str = "", sender_name: str = "",
                   received_time: Optional[datetime] = None) -> None:
        received_iso = received_time.isoformat() if received_time else ""
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            email_id,
            (email_preview or "")[:200],
            sender_email, sender_name, received_iso,
            status, department, employee_name, date,
            (reason or "")[:300], f"{processing_time:.2f}",
        ]
        try:
            with open(self.log_path, "a", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow(row)
            logger.info(f"Log entry written: {status} for {employee_name}")
        except Exception as exc:
            logger.error(f"Failed to write log: {exc}")

    # ... (rest of your tracker.py methods remain the same)
