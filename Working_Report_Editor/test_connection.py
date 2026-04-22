"""
test_connection.py — Smoke-test to verify every integration before going live.

Run:  python test_connection.py
"""

import sys

PASS = "✅"
FAIL = "❌"


def test_config():
    print("\n[1/5] Config & .env …", end=" ")
    try:
        from config import (
            GEMINI_API_KEY, HR_SPREADSHEET_ID, SALES_EMPLOYEES,
            SALES_SPREADSHEET_ID, SERVICE_ACCOUNT_FILE,
        )
        assert SALES_EMPLOYEES, "SALES_EMPLOYEES is empty"
        assert GEMINI_API_KEY not in ("", None), "GEMINI_API_KEY not set"
        assert SALES_SPREADSHEET_ID != "YOUR_SALES_SPREADSHEET_ID", "Sales ID not set"
        assert HR_SPREADSHEET_ID    != "YOUR_HR_SPREADSHEET_ID",    "HR ID not set"
        print(PASS)
        return True
    except Exception as e:
        print(f"{FAIL}  {e}")
        return False


def test_sheets():
    print("[2/5] Google Sheets connection …", end=" ")
    try:
        from sheets_service import SheetsService
        svc    = SheetsService()
        sheets = svc.list_sheets("Sales")
        print(f"{PASS}  Sales sheets found: {sheets}")
        return True
    except Exception as e:
        print(f"{FAIL}  {e}")
        return False


def test_gemini():
    print("[3/5] Gemini text API …", end=" ")
    try:
        import google.generativeai as genai
        from config import GEMINI_API_KEY, GEMINI_MODEL
        genai.configure(api_key=GEMINI_API_KEY)
        model    = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content("Reply with just the word: OK")
        assert response.text.strip(), "Empty response"
        print(f"{PASS}  Response: {response.text.strip()!r}")
        return True
    except Exception as e:
        print(f"{FAIL}  {e}")
        return False


def test_gmail():
    print("[4/5] Gmail connection …", end=" ")
    try:
        from gmail_reader import GmailReader
        reader = GmailReader()
        svc    = reader._get_service()
        # Just list labels — a cheap read-only operation
        labels = svc.users().labels().list(userId="me").execute()
        print(f"{PASS}  Labels found: {len(labels.get('labels', []))}")
        return True
    except Exception as e:
        print(f"{FAIL}  {e}")
        return False


def test_utils():
    print("[5/5] Utils (date extraction) …", end=" ")
    try:
        from utils import extract_date_from_subject, date_to_sheet_name, parse_duration
        d = extract_date_from_subject("Working Report 25-03-2026 Sales")
        assert d == "25-03-2026", f"Expected '25-03-2026', got {d!r}"
        s = date_to_sheet_name("25-03-2026")
        assert s == "Mar-2026", f"Expected 'Mar-2026', got {s!r}"
        dur = parse_duration("2:30:45")
        assert dur == "02:30:45", f"Duration mismatch: {dur!r}"
        print(f"{PASS}  date={d!r}, sheet={s!r}, duration={dur!r}")
        return True
    except Exception as e:
        print(f"{FAIL}  {e}")
        return False


if __name__ == "__main__":
    print("=" * 55)
    print("  Report Automation — Connection & Smoke Tests")
    print("=" * 55)

    results = [
        test_config(),
        test_utils(),
        test_gemini(),
        test_sheets(),
        test_gmail(),
    ]

    ok  = sum(results)
    bad = len(results) - ok
    print("\n" + "=" * 55)
    print(f"  Results: {ok}/{len(results)} passed  |  {bad} failed")
    print("=" * 55)

    sys.exit(0 if bad == 0 else 1)
