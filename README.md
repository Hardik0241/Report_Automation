📊 Report Automation System — Production Setup Guide
📁 Project Structure
Report_Automation/
├── .github/
│   └── workflows/
│       └── scheduler.yml        # GitHub Actions scheduler
├── Working_Report_Editor/
│   ├── main.py                 # Pipeline orchestrator
│   ├── dashboard.py            # Streamlit dashboard
│   ├── config.py               # Config settings
│   ├── config.yaml             # Model config
│   ├── gmail_reader.py         # Gmail fetch (READ ONLY)
│   ├── gemini_parser.py        # Email → structured data
│   ├── vision_parser.py        # Screenshot → data
│   ├── sheets_service.py       # Google Sheets writer
│   ├── validator.py            # Validation logic
│   ├── tracker.py              # Logging + duplicates
│   ├── error_handler.py        # Retry + exceptions
│   ├── utils.py                # Helper functions
│   ├── test_connection.py      # Smoke tests
│   ├── encode_token.py
│   ├── get_refresh_token.py
│   ├── scheduler.py
│   ├── requirements.txt
│   ├── runtime.txt
│   ├── .python-version
│   ├── .env.example
│   └── logs/
│       ├── processing_logs.csv
│       ├── error_logs.jsonl
│       └── duplicate_cache.json
├── .gitignore
├── LICENSE
└── README.md
📋 System Overview

Automates daily reporting by:

Reading emails from Gmail
Extracting structured data using Gemini AI
Validating Sales reports via screenshots
Writing clean data into Google Sheets
Tracking logs + duplicates
Providing a real-time dashboard
✨ Key Features
⏱ Runs every 30 mins (7 PM – 11:59 PM IST)
🧠 AI-powered parsing (Gemini + fallback regex)
📸 Screenshot validation (Sales only)
🔁 Duplicate prevention (24-hour cache)
📊 Auto-formatted Google Sheets (Calibri 13, borders)
📈 Streamlit dashboard
📁 CSV logging + GitHub auto-commit
🚀 Quick Start
Prerequisites
Python 3.11+
Gmail account
Google Cloud project
Gemini API key
⚙️ Installation
cd Working_Report_Editor
pip install -r requirements.txt
☁️ Google Cloud Setup
1. Enable APIs
Gmail API
Google Sheets API
Google Drive API
2. OAuth (Gmail)
Create OAuth Client ID (Desktop App)
Download → rename to client_secret.json
python get_refresh_token.py

Save:

CLIENT_ID
CLIENT_SECRET
REFRESH_TOKEN
3. Service Account (Sheets)
Create Service Account
Role → Editor
Download JSON → rename credentials.json
4. Share Sheets

Give Editor access to service account email.

🔑 Gemini API

Get API key from Google AI Studio.

🔐 GitHub Secrets

Add these in repo → Settings → Secrets

Key	Value
GOOGLE_CREDENTIALS	credentials.json content
GEMINI_API_KEY	API key
SALES_SPREADSHEET_ID	Sheet ID
HR_SPREADSHEET_ID	Sheet ID
CLIENT_ID	OAuth
CLIENT_SECRET	OAuth
REFRESH_TOKEN	OAuth
👥 Employee Configuration

Edit config.py:

SALES_EMPLOYEES = ["Apoorva", "Abhijit", "Sakib", ...]
HR_EMPLOYEES = ["Ruwaida", "Amanpreet", "Mehvish"]
Email Mapping
SALES_EMAIL_MAP = {
    "apoorva.edujam@gmail.com": "Apoorva",
}

HR_EMAIL_MAP = {
    "ruwaida.hredujam@gmail.com": "Ruwaida",
}
⏰ Scheduler (GitHub Actions)

Runs automatically:

- cron: '30,0 13-18 * * *'
- cron: '30 18 * * *'
🧪 Smoke Test
python test_connection.py

All tests must pass ✅

🚀 Run System
Manual
python main.py
Dashboard
streamlit run dashboard.py
Automatic

Push to GitHub → runs via Actions

📧 Email Format
Sales
Total Dialed: 150
Total Connected: 120
Duration: 2h 30m 45s
Prospect: 45

✔ Flexible formats supported

HR
Total Calls: 70
Connected Calls: 23
Duration: 1h 22m 3s
Tomorrow Interview Lineups: 2
Interview Held: 0
📊 Google Sheet Format
Sales Columns
Date	Name	Dialed	Connected	Duration	Prospect	Status
HR Columns

| Date | Name | Calls | Connected | Duration | Lineups | Held |

📌 Status Types
✅ Valid
❌ Invalid
⚠️ Quota Error
📸 No Screenshot
⛔ Not Sent
🔄 Pipeline Flow
Email → Duplicate Check → Parse → Validate → Screenshot Check
      → Write to Sheet → Log → Commit → Dashboard
📊 Dashboard Features
KPI metrics
Recent activity
Trends
Department distribution
Manual refresh
🛠 Common Issues
Issue	Fix
No emails	Check sender + unread
Quota error	Reduce API usage
Name mismatch	Update employee list
Duplicate logs	Handled automatically
Sheet not found	Auto-created
⚙️ Config Tweaks
MAX_EMAILS_PER_RUN = 5
DUPLICATE_WINDOW_HOURS = 48
Skip Screenshot Validation
SKIP_SCREENSHOT_VALIDATION = True
📁 Important Files
File	Purpose
main.py	Core pipeline
dashboard.py	UI
gmail_reader.py	Fetch emails
gemini_parser.py	Parse text
vision_parser.py	Parse images
sheets_service.py	Write to Sheets
tracker.py	Logs + duplicates
🚨 Support Checklist
Check GitHub Actions logs
Verify secrets
Run smoke tests
Check logs CSV
📜 License

Proprietary & Confidential

✅ Final Checklist
Python installed
APIs enabled
OAuth configured
Service account ready
Sheets shared
Secrets added
Employees configured
Tests passed
Workflow running
