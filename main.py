import os
import json
import uuid
import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key="AIza-your-actual-key-here")

app = FastAPI(title="Email Response System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Store emails in memory
emails = []

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

    classify_response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=classify_prompt
    )

    try:
        classification = json.loads(classify_response.text)
    except:
        classification = {
            "category": "General",
            "urgency": "Medium",
            "sentiment": "Neutral",
            "summary": "Customer inquiry"
        }

    # Step 2 - Draft a professional reply
    reply_prompt = f"""You are a professional customer service agent.
Write a helpful and empathetic reply to this customer email.
Keep it under 100 words. Be professional and solution-focused.
Start with: Dear Customer,
End with: Best regards, Customer Support Team

Customer email: {request.email_text}"""

    reply_response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=reply_prompt
    )

    # Create email record
    email_record = {
        "id": str(uuid.uuid4()),
        "sender": request.sender,
        "original_email": request.email_text,
        "category": classification.get("category", "General"),
        "urgency": classification.get("urgency", "Medium"),
        "sentiment": classification.get("sentiment", "Neutral"),
        "summary": classification.get("summary", "Customer inquiry"),
        "draft_reply": reply_response.text,
        "status": "Pending",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    emails.append(email_record)

    return email_record

@app.get("/emails")
def get_emails():
    return {"emails": emails, "total": len(emails)}

@app.patch("/update")
def update_status(request: UpdateRequest):
    for email in emails:
        if email["id"] == request.email_id:
            email["status"] = request.status
            return {"message": f"Email {request.status}", "email": email}
    return {"error": "Email not found"}

@app.delete("/clear")
def clear_emails():
    emails.clear()
    return {"message": "All emails cleared"}

app.mount("/static", StaticFiles(directory="../frontend"), name="static")

@app.get("/app")
def serve_frontend():
    return FileResponse("../frontend/index.html")