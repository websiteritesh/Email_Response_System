import os
import json
import uuid
import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv
from google import genai
import re
import time

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- Database setup ---
from sqlalchemy import create_engine, text
db_engine = create_engine(os.getenv("DATABASE_URL"))

def init_db():
    with db_engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS email_records (
                id TEXT PRIMARY KEY,
                sender TEXT,
                original_email TEXT,
                category TEXT,
                urgency TEXT,
                sentiment TEXT,
                summary TEXT,
                draft_reply TEXT,
                status TEXT,
                timestamp TEXT
            )
        """))
        conn.commit()

# --- Structured output schema ---
# Instead of trusting json.loads() on raw AI text (which breaks the moment
# Gemini adds a code fence or a stray sentence), we validate the parsed
# JSON against this schema. If a field is missing or misspelled, Pydantic
# tells us exactly what's wrong instead of silently returning defaults.
class EmailClassification(BaseModel):
    category: str
    urgency: str
    sentiment: str
    summary: str

# --- Retry helper ---
# The AI provider's servers can be temporarily overloaded (503 errors).
# This retries a few times with increasing wait time before giving up.
def call_ai_with_retry(prompt_text, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(model="gemini-3.6-flash", contents=prompt_text)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            print(f"AI call failed ({e}), retrying in {wait_time}s...")
            time.sleep(wait_time)

def describe_ai_error(e: Exception) -> str:
    """Turn a raw exception into a short, honest message a person can act on,
    instead of one generic 'temporarily unavailable' for every kind of failure."""
    text = str(e)
    if "RESOURCE_EXHAUSTED" in text or "429" in text:
        return "Daily AI request limit reached for this API key. Try again later, or use a different key."
    if "UNAVAILABLE" in text or "503" in text:
        return "The AI service is temporarily overloaded. Please try again in a minute."
    return "The AI service returned an unexpected error. Check the server logs for details."

def extract_json(raw_text: str) -> dict:
    """Gemini sometimes wraps JSON in ```json ... ``` or adds a stray
    sentence before/after it. This pulls out just the {...} block so
    json.loads() has a real chance of succeeding."""
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in AI response: {raw_text[:200]}")
    return json.loads(match.group(0))

app = FastAPI(title="Email Response System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.on_event("startup")
def startup():
    init_db()
    print("Database ready")

class EmailRequest(BaseModel):
    email_text: str
    sender: str = "customer@example.com"

class UpdateRequest(BaseModel):
    email_id: str
    status: str

@app.get("/")
def home():
    return {"status": "Email Response System running"}

@app.post("/process")
def process_email(request: EmailRequest):
    # Step 1 - Classify the email
    classify_prompt = f"""You are an email classifier for a customer service team.
Read this email and return ONLY this JSON:
{{
  "category": "Refund or Shipping or Product or Billing or General",
  "urgency": "High or Medium or Low",
  "sentiment": "Angry or Frustrated or Neutral or Happy",
  "summary": "one sentence max 12 words"
}}
Return only JSON. No extra text.
Email: {request.email_text}"""

    try:
        classify_response = call_ai_with_retry(classify_prompt)
        raw_json = extract_json(classify_response.text)
        classification = EmailClassification(**raw_json)
    except (ValueError, ValidationError, Exception) as e:
        # We land here if the AI service is down, or if it returned
        # something that doesn't match our schema. Either way, we log the
        # real reason instead of silently guessing — that's the fix for
        # the original bare "except:" that hid every failure.
        print(f"[CLASSIFY FAILED] {type(e).__name__}: {e}")
        if isinstance(e, (ValueError, ValidationError)):
            # The AI responded, but the JSON was malformed or missing a field
            summary_text = "AI response didn't match the expected format — please review manually"
        else:
            # The AI service itself failed (outage, quota limit, etc.)
            summary_text = describe_ai_error(e)
        classification = EmailClassification(
            category="General", urgency="Medium", sentiment="Neutral", summary=summary_text,
        )

    # Step 2 - Draft a professional reply
    reply_prompt = f"""You are a professional customer service agent.
Write a helpful and empathetic reply to this customer email.
Keep it under 100 words. Be professional and solution-focused.
Start with: Dear Customer,
End with: Best regards, Customer Support Team

Customer email: {request.email_text}"""

    try:
        reply_response = call_ai_with_retry(reply_prompt)
        reply_text = reply_response.text
    except Exception as e:
        print(f"[REPLY FAILED] {type(e).__name__}: {e}")
        reply_text = f"Could not draft a reply automatically. {describe_ai_error(e)}"

    # Create email record
    email_record = {
        "id": str(uuid.uuid4()),
        "sender": request.sender,
        "original_email": request.email_text,
        "category": classification.category,
        "urgency": classification.urgency,
        "sentiment": classification.sentiment,
        "summary": classification.summary,
        "draft_reply": reply_text,
        "status": "Pending",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    with db_engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO email_records
                (id, sender, original_email, category, urgency, sentiment, summary, draft_reply, status, timestamp)
            VALUES
                (:id, :sender, :original_email, :category, :urgency, :sentiment, :summary, :draft_reply, :status, :timestamp)
        """), email_record)
        conn.commit()

    return email_record

@app.get("/emails")
def get_emails():
    with db_engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM email_records ORDER BY timestamp DESC"))
        emails = [dict(row._mapping) for row in rows]
    return {"emails": emails, "total": len(emails)}

@app.patch("/update")
def update_status(request: UpdateRequest):
    with db_engine.connect() as conn:
        result = conn.execute(
            text("UPDATE email_records SET status = :status WHERE id = :id"),
            {"status": request.status, "id": request.email_id}
        )
        conn.commit()
        if result.rowcount == 0:
            return {"error": "Email not found"}
    return {"message": f"Email {request.status}"}

@app.delete("/clear")
def clear_emails():
    with db_engine.connect() as conn:
        conn.execute(text("DELETE FROM email_records"))
        conn.commit()
    return {"message": "All emails cleared"}

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/app")
def serve_frontend():
    return FileResponse("frontend/index.html")