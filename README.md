@"
# Automated Email Response System

AI-powered system that reads customer emails, classifies them,
drafts professional replies, and lets humans approve before sending.

## What it does
- Paste any customer email
- AI classifies: category, urgency, sentiment
- AI drafts a professional reply automatically
- Human reviews and approves or rejects the reply
- Dashboard shows all emails with stats

## Tools used
- Python
- FastAPI
- Google Gemini API (gemini-3.6-flash)
- Uvicorn

## How to run
1. Add your Google API key to .env file
2. Run: uvicorn main:app --reload
3. Open: http://127.0.0.1:8000/app
4. Paste a customer email and click Process Email
"@ | Out-File -FilePath README.md -Encoding utf8