# Reply Desk — Email Response System

An AI triage system for customer support email. It classifies incoming emails, drafts a reply, and keeps a human in the loop — no reply goes out without someone approving it first.

Built with FastAPI, PostgreSQL, and Google Gemini.

## Features

- **Structured classification** — every email is classified by category, urgency, and sentiment using a Pydantic schema, not loose text parsing
- **Resilient AI calls** — automatic retries with exponential backoff if the AI provider is temporarily overloaded, and honest error messages that distinguish a quota limit from a real outage
- **Human-in-the-loop** — the AI drafts a reply, but every email stays "Pending" until a person approves or rejects it
- **Persistent storage** — every email and its status is saved to PostgreSQL, so nothing is lost on restart
- **Mocked tests** — the test suite fakes the AI response instead of calling the real API, so tests run in seconds and never touch your request quota
- **Dockerized** — runs identically anywhere via Docker Compose
- **CI** — GitHub Actions runs the full test suite automatically on every push

## Tech stack

| Layer | Tools |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| AI | Google Gemini API (`gemini-3.6-flash`) |
| Validation | Pydantic |
| Database | PostgreSQL via Supabase, SQLAlchemy |
| Testing | pytest, httpx, unittest.mock |
| Deployment | Docker, Docker Compose |
| CI/CD | GitHub Actions |

## Project structure

```
backend/
├── main.py              # FastAPI app: classification, replies, storage
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── tests/
│   └── test_main.py
└── .github/workflows/
    └── ci.yml
```

## Running locally

1. Create `backend/.env` with:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   DATABASE_URL=your_postgres_connection_string
   ```
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run:
   ```
   uvicorn main:app --reload
   ```
4. Open `http://127.0.0.1:8000/app`, paste a customer email, and process it.

## Running with Docker

```
docker compose up --build
```

## Running tests

```
pytest -v
```

Tests use a mocked AI response, so they don't consume your Gemini API quota and run in under a second.

## How it works

1. A customer email is pasted in through the dashboard
2. The AI classifies it into a category, urgency level, and sentiment, validated against a Pydantic schema
3. If the AI's response isn't valid JSON or is missing a field, the system falls back to safe defaults instead of crashing
4. The AI drafts a reply
5. The email, classification, and draft reply are saved to PostgreSQL with status "Pending"
6. A human reviews it on the dashboard and approves or rejects the reply — no email is ever sent automatically



