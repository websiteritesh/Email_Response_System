"""
Tests for the Email Response System API.
Run with: pytest -v      (from inside the backend folder)

These tests MOCK the AI call instead of using the real Gemini API. That
means: no API quota used, tests run in under a second, and results are
100% predictable instead of depending on what the AI happens to say.
"""
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app, db_engine
from sqlalchemy import text

client = TestClient(app)


class FakeAIResponse:
    """A stand-in for whatever client.models.generate_content() normally
    returns — main.py only ever reads its .text attribute, so that's all
    this fake object needs to have."""
    def __init__(self, text):
        self.text = text


def setup_function():
    """Runs before every test — start each test with an empty table so
    tests don't interfere with each other."""
    with db_engine.connect() as conn:
        conn.execute(text("DELETE FROM email_records"))
        conn.commit()


def test_home_endpoint_is_reachable():
    response = client.get("/")
    assert response.status_code == 200


def test_emails_list_starts_empty():
    response = client.get("/emails")
    assert response.status_code == 200
    assert response.json()["total"] == 0


@patch("main.call_ai_with_retry")
def test_process_email_with_mocked_ai(mock_ai):
    # The classify call happens first, then the reply call — side_effect
    # gives them different fake responses in that order.
    mock_ai.side_effect = [
        FakeAIResponse('{"category": "Refund", "urgency": "High", "sentiment": "Angry", "summary": "Wants a refund"}'),
        FakeAIResponse("Dear Customer, we're sorry to hear that. Best regards, Support Team"),
    ]

    response = client.post("/process", json={
        "email_text": "My order arrived broken, I want a refund!",
        "sender": "test@example.com",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "Refund"
    assert body["urgency"] == "High"
    assert body["sentiment"] == "Angry"
    assert "sorry" in body["draft_reply"].lower()


@patch("main.call_ai_with_retry")
def test_process_email_handles_malformed_ai_response(mock_ai):
    """If the AI returns text that ISN'T valid JSON, we should fall back
    gracefully instead of crashing — this proves the extract_json /
    Pydantic validation safety net from earlier today actually works."""
    mock_ai.side_effect = [
        FakeAIResponse("Sorry, I can't help with that."),  # not JSON at all
        FakeAIResponse("A reply anyway."),
    ]

    response = client.post("/process", json={
        "email_text": "Some email",
        "sender": "test@example.com",
    })

    assert response.status_code == 200
    body = response.json()
    # Falls back to safe defaults instead of crashing
    assert body["category"] == "General"


@patch("main.call_ai_with_retry")
def test_update_status(mock_ai):
    mock_ai.side_effect = [
        FakeAIResponse('{"category": "General", "urgency": "Low", "sentiment": "Neutral", "summary": "A question"}'),
        FakeAIResponse("Thanks for reaching out."),
    ]

    process_response = client.post("/process", json={"email_text": "Hi", "sender": "a@b.com"})
    email_id = process_response.json()["id"]

    update_response = client.patch("/update", json={"email_id": email_id, "status": "Approved"})
    assert update_response.status_code == 200

    emails = client.get("/emails").json()["emails"]
    updated = next(e for e in emails if e["id"] == email_id)
    assert updated["status"] == "Approved"


def test_update_nonexistent_email_returns_error():
    response = client.patch("/update", json={"email_id": "not-a-real-id", "status": "Approved"})
    assert response.json().get("error") is not None


def test_clear_removes_all_emails():
    with db_engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO email_records (id, sender, original_email, category, urgency, sentiment, summary, draft_reply, status, timestamp) "
            "VALUES ('test-1', 'a@b.com', 'hi', 'General', 'Low', 'Neutral', 'test', 'reply', 'Pending', '2026-01-01 00:00')"
        ))
        conn.commit()

    response = client.delete("/clear")
    assert response.status_code == 200
    assert client.get("/emails").json()["total"] == 0