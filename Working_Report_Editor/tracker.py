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
        os.makedirs(LOG_DIR, exist_ok=True)
        self._init_csv()
        self._init_cache()

    def _init_csv(self):
        if not os.path.exists(PROCESSING_LOG_PATH):
            with open(PROCESSING_LOG_PATH, "w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow(_CSV_COLUMNS)

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
            with open(PROCESSING_LOG_PATH, "a", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow(row)
        except Exception as exc:
            logger.error(f"Failed to write log: {exc}")

    def _init_cache(self):
        if not os.path.exists(DUPLICATE_CACHE_PATH):
            with open(DUPLICATE_CACHE_PATH, "w") as fh:
                json.dump({}, fh)

    def _load_cache(self) -> Dict:
        try:
            with open(DUPLICATE_CACHE_PATH, "r") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def _save_cache(self, cache: Dict) -> None:
        try:
            with open(DUPLICATE_CACHE_PATH, "w") as fh:
                json.dump(cache, fh, indent=2)
        except Exception as exc:
            logger.error(f"Could not save cache: {exc}")

    def is_duplicate(self, email_hash: str) -> bool:
        if not email_hash:
            return False
        cache = self._load_cache()
        last_str = cache.get(email_hash)
        if not last_str:
            return False
        return datetime.now() - datetime.fromisoformat(last_str) < timedelta(hours=DUPLICATE_WINDOW_HOURS)

    def mark_processed(self, email_hash: str) -> None:
        if not email_hash:
            return
        cache = self._load_cache()
        cache[email_hash] = datetime.now().isoformat()
        cutoff = datetime.now() - timedelta(hours=DUPLICATE_WINDOW_HOURS * 2)
        cache = {k: v for k, v in cache.items() if datetime.fromisoformat(v) > cutoff}
        self._save_cache(cache)

    def get_statistics(self) -> Dict:
        try:
            with open(PROCESSING_LOG_PATH, "r", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        except Exception:
            rows = []
        total = len(rows)
        success = sum(1 for r in rows if r.get("Status") == "SUCCESS")
        failed = sum(1 for r in rows if r.get("Status") == "FAILED")
        duplicate = sum(1 for r in rows if r.get("Status") == "DUPLICATE")
        return {"total": total, "success": success, "failed": failed,
                "duplicate": duplicate, "success_rate": round(success / total * 100, 1) if total else 0.0}
