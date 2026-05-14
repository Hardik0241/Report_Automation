# 📊 Report Automation System — Production Setup Guide

## Project Structure

Report_Automation/
├── .github/
│ └── workflows/
│ └── scheduler.yml ← GitHub Actions scheduler (runs every 30 min, 7 PM - 11:59 PM IST)
├── Working_Report_Editor/
│ ├── main.py ← Pipeline orchestrator
│ ├── dashboard.py ← Streamlit monitoring dashboard
│ ├── config.py ← All configuration settings
│ ├── config.yaml ← Model configuration
│ ├── gmail_reader.py ← Gmail fetch + attachment download (READ ONLY)
│ ├── gemini_parser.py ← Email body → structured data (Gemini + regex fallback)
│ ├── vision_parser.py ← Callyzer screenshot → data (Gemini Vision + OCR fallback)
│ ├── sheets_service.py ← Google Sheets read/write (Cached API calls, Calibri 13, borders)
│ ├── validator.py ← Name fuzzy-match, date check, field validation
│ ├── tracker.py ← CSV logging + permanent duplicate detection
│ ├── error_handler.py ← Custom exceptions + retry decorator
│ ├── utils.py ← Date/duration/email helpers (handles +7 minutes addition)
│ ├── test_connection.py ← Smoke tests (run before going live)
│ ├── encode_token.py ← Encode token.pickle for GitHub secrets
│ ├── get_refresh_token.py ← Get OAuth refresh token
│ ├── scheduler.py ← Local scheduler (for local deployment)
│ ├── requirements.txt ← Python dependencies
│ ├── runtime.txt ← Python version (3.11)
│ ├── .python-version ← Python version for GitHub Actions
│ ├── .env.example ← Copy to .env and fill values
│ └── logs/
│ ├── processing_logs.csv ← Success/failure logs (auto-committed to GitHub)
│ ├── error_logs.jsonl ← Detailed error logs
│ └── duplicate_cache.json ← Permanent duplicate tracking (24-hour window)
├── .gitignore ← Git ignore rules (allows processing_logs.csv)
├── LICENSE
└── README.md



---

## 📋 System Overview

This automated system reads daily work reports from Gmail, extracts data using Gemini AI, validates against Callyzer screenshots (for Sales), and writes structured data to Google Sheets.

### Key Features

| Feature | Description |
|---------|-------------|
| **Automated Email Processing** | Runs every 30 minutes between 7:00 PM - 11:59 PM IST |
| **Department Detection** | Auto-detects Sales/HR based on email content and sender maps |
| **Screenshot Validation** | Compares email data with Callyzer screenshots for Sales reports (OPTIONAL, email is source of truth) |
| **Flexible Email Formats** | Handles various writing styles, extra text, missing colons, and `+7 minutes` addition patterns |
| **Duplicate Prevention** | Permanent cache prevents re-processing same email within 24 hours |
| **Google Sheets Caching** | 60-second TTL cache prevents 429 rate limit errors |
| **Gemini Quota Fallback** | Regex fallback parser activates when Gemini API quota is exceeded |
| **Google Sheets Formatting** | Calibri font, size 13, dark black text, all borders |
| **Status Tracking** | Valid, Invalid, Quota Error, No Screenshot, Not Sent, Email Only, Email (screenshot mismatch) |
| **Real-time Dashboard** | Streamlit dashboard with manual refresh, deduplicated stats |
| **CSV Logging** | Every email processing result logged (one entry per employee per day) |
| **Weekday-Only Processing** | Scheduler only runs Monday-Friday (skips weekends) |
| **Date Validation** | Only processes emails from today's date (ignores previous days) |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- Gmail account
- Google Cloud Project with APIs enabled
- Gemini API key (Google AI Studio)

---

## Step 1 — Install Dependencies

```bash
cd Working_Report_Editor
pip install -r requirements.txt


Step 2 — Google Cloud Setup (One-time)
2.1 Create Project & Enable APIs
Go to console.cloud.google.com

Create a new project or select existing

Enable these APIs:

Gmail API

Google Sheets API

Google Drive API

2.2 Create OAuth 2.0 Credentials (for Gmail)
Go to APIs & Services → Credentials

Click + CREATE CREDENTIALS → OAuth client ID

Application type: Desktop app

Name: Report Automation

Download JSON and rename to client_secret.json

2.3 Get Refresh Token
bash
python get_refresh_token.py
Follow the browser authentication. Copy the client_id, client_secret, and refresh_token for GitHub Secrets.

2.4 Create Service Account (for Sheets)
Go to IAM & Admin → Service Accounts

Click + CREATE SERVICE ACCOUNT

Name: report-automation

Click CREATE AND CONTINUE

Role: Editor

Click DONE

Click on the service account → Keys → Add Key → JSON → Download

Rename to credentials.json

2.5 Share Google Sheets
Open each spreadsheet (Sales + HR) → Share → Add the service account email with Editor access.

Step 3 — Get Gemini API Key
Go to aistudio.google.com

Click Get API Key

Copy the key (starts with AIza)

Step 4 — Configure GitHub Secrets
Go to your GitHub repository → Settings → Secrets and variables → Actions → Add these secrets:

Secret Name	Value
GOOGLE_CREDENTIALS	Full content of credentials.json (the entire JSON)
GEMINI_API_KEY	Your Gemini API key
SALES_SPREADSHEET_ID	ID from Sales Google Sheet URL
HR_SPREADSHEET_ID	ID from HR Google Sheet URL
CLIENT_ID	OAuth client ID (from get_refresh_token.py)
CLIENT_SECRET	OAuth client secret (from get_refresh_token.py)
REFRESH_TOKEN	OAuth refresh token (from get_refresh_token.py)
How to find Spreadsheet ID:

text
https://docs.google.com/spreadsheets/d/THIS_IS_YOUR_ID/edit
Step 5 — Configure Streamlit Cloud Secrets
If deploying dashboard to Streamlit Cloud, add the same secrets in Streamlit Cloud → Settings → Secrets.

Step 6 — Update Employee Lists
Edit config.py:

python
SALES_EMPLOYEES = [
    "Apoorva", "Abhijit", "Sakib", "Jayesh", "Saif", "Rajesh",
    "Manasvi", "Praful", "Sachin", "Aishwary", "Supriya", "Sayli", 
    "Dhanshree", "Muskan", "Komal", "Siddhesh",
]

HR_EMPLOYEES = [
    "Ruwaida", "Amanpreet", "Mehvish", "Salomi",
]
Email to Name Mapping
Update email maps in config.py:

python
SALES_EMAIL_MAP = {
    "apoorva.edujam@gmail.com": "Apoorva",
    "abhijit.edujam@gmail.com": "Abhijit",
    # ... add all employees
}

HR_EMAIL_MAP = {
    "ruwaida.hredujam@gmail.com": "Ruwaida",
    "amanpreet.hredujam@gmail.com": "Amanpreet",
    "mehvish.hredujam@gmail.com": "Mehvish",
    "salomi.hredujam@gmail.com": "Salomi",
}
Step 7 — Configure Schedule
The scheduler runs on GitHub Actions:

Time (IST)	Action
7:00 PM - 11:30 PM	Every 30 minutes (process emails)
11:59 PM	Final run (marks "Not Sent" for missing Sales employees)
Weekends (Sat-Sun)	No processing (scheduler skips)
To modify schedule, edit .github/workflows/scheduler.yml:

yaml
- cron: '30,0 13-18 * * 1-5'   # Every 30 min from 13:30 to 18:30 UTC, Monday-Friday
- cron: '30 18 * * 1-5'          # Final run at 18:30 UTC, Monday-Friday
Step 8 — Run Smoke Tests
bash
cd Working_Report_Editor
python test_connection.py
All 5 tests should pass before continuing.

Step 9 — Deploy
Local / Manual Run
bash
python main.py
Streamlit Dashboard
bash
streamlit run dashboard.py
GitHub Actions (Automatic)
Push to GitHub - scheduler runs automatically. No manual intervention needed.

📧 Email Format Guidelines
Sales Department (Recommended Format)
text
Total Dialed: 150
Total Connected: 120
Duration: 2h 30m 45s
Prospect: 45
Also accepts these variations:

Total Dialed- 150 (dash instead of colon)

Total Dialed 150 (space only)

Total Dialed-150 (no space after dash)

Duration: 2h 23m 14s +7 minutes (addition patterns supported)

Extra text after numbers is ignored

HR Department (Recommended Format)
text
Total Dialed: 98
Connected: 38
Duration: 46m 48s
Today Held-0
Total Line up for Tomorrow- 0
Also accepts these variations:

Connected: 38 (colon format supported)

Connected 38 (space format)

Today Held: 0 (colon format)

Total Line ups for tomorrow: 0

Subject Line
Any subject is fine (system uses sender email for identification). Emails are filtered by sender email (only allowed senders).

📊 Google Sheet Formatting
Property	Value
Font	Calibri
Font Size	13
Text Color	Dark black (#000000)
Alignment	Center (horizontal & vertical)
Borders	All borders on data cells
Sales Sheet Columns
A	B	C	D	E	F	G	H	I	J
Date	Employee Name	Total Dialed	Total Connected	Duration	Prospect	Ref Added	status Viewed	Document Collected	Report Status
HR Sheet Columns
A	B	C	D	E	F	G
Date	Employee Name	Total Calls	Connected Calls	Duration	Tomorrow Interview Lineups	Interview Held
Report Status Values (Sales only)
Status	Meaning
Valid	Email data matches screenshot
Invalid	Email data does NOT match screenshot (employee's fault)
Quota Error	Gemini API quota exceeded (model's fault - NOT written to sheet)
No Screenshot	Email received without screenshot attachment
Not Sent	No email received by deadline (auto-marked at start of day)
Email Only	Default status when no screenshot
Email (screenshot mismatch)	Mismatch detected but email values written
🔄 How the Pipeline Works
text
Unread email detected (from allowed sender)
        │
        ▼
① Duplicate check (permanent cache, 24-hour window)
   → Already processed → SKIPPED (skip, no log entry)
        │
        ▼
② Parse email body (Gemini AI + regex fallback when quota exceeded)
   → Extract: name, department, numbers, duration (handles +7 minutes addition)
        │
        ▼
③ Determine department (sender email map → body detection)
        │
        ▼
④ Validate employee name (exact → substring → fuzzy match)
        │
        ▼
⑤ Validate required fields present
        │
        ▼
⑥ For Sales: Parse screenshot attachment (Gemini Vision + OCR fallback)
   │  └─ Compare email vs screenshot values (OPTIONAL - email is source of truth)
   │     └─ Match → "Valid", Mismatch → "Email (screenshot mismatch)"
        │
        ▼
⑦ Mark all employees as "Not Sent" for this date (first email of the day)
        │
        ▼
⑧ Write email body values to Google Sheet (clears "Not Sent" status)
   └─ Apply formatting: Calibri 13, black text, all borders (using cached API calls)
        │
        ▼
⑨ Log SUCCESS/FAILED/SKIPPED to CSV (one entry per employee per day)
        │
        ▼
⑩ Auto-commit logs to GitHub (dashboard updates)
📊 Dashboard Features
Section	Description
KPI Cards	Total Processed, Success, Failed, Success Rate, Today's Success (deduplicated stats)
Recent Activity	Latest 15 unique processed emails (one per employee per day, SUCCESS preferred)
Department Distribution	Pie chart of Sales vs HR reports (unique employees)
Refresh Button	Manual refresh (resets dashboard, clears logs file)
Employee Registry	Shows Sales Team (16) and HR Team (4) counts
Dashboard URL: (after deploying to Streamlit Cloud)

🛠️ Common Issues & Fixes
Problem	Cause	Fix
WorksheetNotFound	Monthly sheet doesn't exist	Auto-created on first run
Fuzzy name not matching	Name not in employee list	Add exact name to SALES_EMPLOYEES or HR_EMPLOYEES
Screenshot mismatch	Wrong screenshot attached	Ensure correct Callyzer screenshot (mismatch doesn't mark Invalid anymore)
Gmail 0 emails found	No unread emails from allowed senders	Check email is unread, sender in email map
429 Quota exceeded (Gemini)	Free tier limit reached	Regex fallback parser activates automatically
429 Quota exceeded (Sheets)	Too many read requests	Caching (60s TTL) prevents this error
Dashboard shows 0	Logs file not committed	Check GitHub Actions logs, ensure commit step runs
Duplicate entries in logs	Same email processed multiple times	Fixed by permanent duplicate cache + sheet check
HR emails detected as Sales	Missing HR keywords	Add "hr", "interview", "recruitment" to email body
Duration off by minutes	Email had +7 minutes pattern	Parser now handles addition patterns
Weekend processing	Scheduler runs on weekends	Added is_weekday() check
Previous day's emails processed	No date validation	Added _is_today_date() check
🔧 Configuration Tweaks
Reduce Quota Usage
In config.py:

python
MAX_EMAILS_PER_RUN = 5  # Process only 5 emails per run
Change Active Window

ACTIVE_START_HOUR = 19    # 7:00 PM
ACTIVE_START_MINUTE = 0
ACTIVE_END_HOUR = 23      # 11:59 PM
ACTIVE_END_MINUTE = 59

Change Duplicate Window

DUPLICATE_WINDOW_HOURS = 48  # Prevent re-processing for 2 days

Skip Screenshot Validation (Temporary)
In main.py, add at the top:

SKIP_SCREENSHOT_VALIDATION = True

Cache TTL for Sheets API
In sheets_service.py:

self._cache_ttl_seconds = 60  # Cache expires after 60 seconds (increase to reduce API calls)

📝 File Descriptions
File	Purpose
main.py	Main orchestrator - processes emails, validates, writes to sheets
gmail_reader.py	Fetches unread emails from allowed senders (READ ONLY)
gemini_parser.py	Extracts structured data from email body (Gemini + regex fallback)
vision_parser.py	Extracts numbers from Callyzer screenshots (Gemini Vision + OCR fallback)
sheets_service.py	Google Sheets operations with caching, Calibri 13, black text, borders
tracker.py	CSV logging + permanent duplicate detection + unique employee tracking
validator.py	Name validation, date validation, field validation
utils.py	Date extraction, duration parsing (handles +7 minutes), email helpers
error_handler.py	Custom exceptions, retry decorator
dashboard.py	Streamlit monitoring dashboard with deduplicated stats
scheduler.py	Local scheduler (for local deployment)
config.py	All configuration settings
test_connection.py	Smoke tests
.github/workflows/scheduler.yml	GitHub Actions workflow (runs every 30 min, weekdays only)
🚨 Support
If you encounter issues:

Check GitHub Actions logs for errors

Check logs/processing_logs.csv in your repository

Run python test_connection.py locally

Verify all secrets are correctly set in GitHub

📜 License
This project is proprietary and confidential.

✅ Final Checklist
Python 3.11 installed

Dependencies installed (pip install -r requirements.txt)

Google Cloud APIs enabled (Gmail, Sheets, Drive)

OAuth credentials obtained (client_secret.json)

Service account created (credentials.json)

Google Sheets shared with service account

Gemini API key obtained

GitHub Secrets configured

Employee lists updated in config.py

Email maps updated in config.py

Smoke tests passed

Workflow pushed to GitHub

Dashboard deployed to Streamlit Cloud


## Key Updates Made to README:

1. **Added new features:**
   - Google Sheets caching (60-second TTL)
   - Gemini quota fallback (regex parser)
   - Duration addition pattern support (`+7 minutes`)
   - Weekday-only processing
   - Date validation (today's emails only)
   - Deduplicated dashboard stats
   - New status values (Email Only, Email (screenshot mismatch))

2. **Updated employee counts:** Sales Team = 16, HR Team = 4

3. **Updated status descriptions:** Removed "Quota Error" from sheet (not written)

4. **Added new error fixes:**
   - 429 Quota exceeded (Gemini) → Regex fallback
   - 429 Quota exceeded (Sheets) → Caching
   - Duration off by minutes → Addition pattern handling
   - Weekend processing → Weekday-only scheduler
   - Previous day's emails → Date validation

5. **Updated pipeline diagram** with new steps (caching, fallback, date validation)

6. **Added new configuration tweaks** for cache TTL
