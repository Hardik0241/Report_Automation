# 📊 Report Automation System — Production Setup Guide

## Project Structure

```
project/
├── main.py              ← Pipeline orchestrator (run this)
├── dashboard.py         ← Streamlit UI
├── config.py            ← All settings (edit once)
├── gmail_reader.py      ← Gmail fetch + attachment download
├── gemini_parser.py     ← Email body → structured data (Gemini + regex fallback)
├── vision_parser.py     ← Callyzer screenshot → data (Gemini Vision)
├── sheets_service.py    ← Google Sheets read/write
├── validator.py         ← Name fuzzy-match, date check, field check, screenshot compare
├── tracker.py           ← CSV log + duplicate detection
├── error_handler.py     ← Custom exceptions + retry decorator
├── utils.py             ← Date/duration helpers
├── test_connection.py   ← Smoke tests (run before going live)
├── .env.example         ← Copy to .env and fill values
├── requirements.txt
└── logs/
    ├── processing_logs.csv
    ├── error_logs.jsonl
    └── duplicate_cache.json
```

---

## Step 1 — Install dependencies

```bash
pip install -r requirements.txt
```

---

## Step 2 — Google Cloud Setup (one-time)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create or select a project
3. **Enable APIs:**
   - Gmail API
   - Google Sheets API
   - Google Drive API
4. Go to **IAM & Admin → Service Accounts → Create Service Account**
5. Name it `report-automation`, click **Create**
6. Click on the service account → **Keys tab → Add Key → JSON** → Download
7. Rename the downloaded file to `credentials.json` and place it in this folder

---

## Step 3 — Share your Google Sheets

Open each spreadsheet (Sales + HR) → **Share** → paste the service account email
(looks like `report-automation@your-project.iam.gserviceaccount.com`) → **Editor** → Done.

---

## Step 4 — Configure .env

```bash
cp .env.example .env
```

Edit `.env`:

```
GEMINI_API_KEY=your_key_from_aistudio.google.com
SALES_SPREADSHEET_ID=the_id_from_your_sales_sheet_url
HR_SPREADSHEET_ID=the_id_from_your_hr_sheet_url
```

**How to find a Spreadsheet ID:**
```
https://docs.google.com/spreadsheets/d/THIS_IS_YOUR_ID/edit
```

---

## Step 5 — Update employee lists

Edit `config.py`:

```python
SALES_EMPLOYEES = [
    "Apoorva", "Abhijit", ...   # your list, in exact order
]

HR_EMPLOYEES = [
    "Priya", "Raj", ...         # your HR list
]
```

Also verify your sheet name format. Current setting: `"Mar-2026"` (3-letter month + year).
If your sheets use a different format (e.g. `"March-2026"`), change `SHEET_NAME_FORMAT` in `config.py`.

---

## Step 6 — Run smoke tests

```bash
python test_connection.py
```

All 5 tests should pass before continuing.

---

## Step 7 — Run

**One-time / manual:**
```bash
python main.py
```

**Dashboard:**
```bash
streamlit run dashboard.py
```

**Scheduled (Linux cron — every 2 hours):**
```bash
crontab -e
# Add:
0 */2 * * * cd /path/to/project && python main.py >> logs/cron.log 2>&1
```

**Windows Task Scheduler:**
Create a `.bat` file:
```bat
cd C:\path\to\project
python main.py
```
Schedule it to run every 2 hours.

---

## How the pipeline works

```
Email arrives (subject: "Working Report 25-03-2026")
        │
        ▼
① Duplicate check  →  skip if processed within 24h
        │
        ▼
② Extract date from subject  →  "25-03-2026"  →  sheet "Mar-2026"
        │
        ▼
③ Gemini parses email body  →  {name, dept, Total Dialed, …}
   └─ Regex fallback if Gemini fails
        │
        ▼
④ Validate employee name  →  exact → substring → fuzzy (80% threshold)
        │
        ▼
⑤ Check required fields present
        │
        ▼
⑥ Gemini Vision parses Callyzer screenshot
        │
        ▼
⑦ Compare email data vs screenshot (±5% tolerance on numbers)
   └─ REJECT if mismatch
        │
        ▼
⑧ Write to correct monthly sheet in Google Sheets
        │
        ▼
⑨ Log SUCCESS / FAILED to logs/processing_logs.csv
```

---

## Common Issues

| Problem | Fix |
|---|---|
| `WorksheetNotFound` | The monthly sheet doesn't exist yet — it will be auto-created on first run |
| Fuzzy name not matching | Add the employee's exact name to `SALES_EMPLOYEES` or `HR_EMPLOYEES` |
| Screenshot mismatch | Increase `tolerance_pct` in `VALIDATION_RULES` (default 5%) |
| Gmail auth error | Ensure the service account has Gmail API enabled and domain-wide delegation if using a Workspace account |
| Date not found in subject | Check the date format — system supports DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD |
