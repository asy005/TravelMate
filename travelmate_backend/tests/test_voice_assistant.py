# travelmate_backend/tests/test_voice_assistant.py
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.voice_service import (
    clean_speech_text,
    validate_voice_transcript,
    summarize_for_speech,
)
from app.models.destination import Destination
from app.services.plan_orchestrator import generate_plan

client = TestClient(app)


class TestVoiceSpeechCleanup:
    """Verifies that markdown and symbols are properly cleaned for browser speech synthesis."""

    def test_clean_speech_text_strips_markdown_and_links(self):
        raw = "Here is your plan for **Goa**:\n* Visit [Baga Beach](https://example.com/baga)!\n* Try seafood."
        cleaned = clean_speech_text(raw)
        assert "**" not in cleaned
        assert "[" not in cleaned
        assert "]" not in cleaned
        assert "http" not in cleaned
        assert "Baga Beach" in cleaned
        assert "Try seafood." in cleaned

    def test_clean_speech_text_converts_rupee_symbols(self):
        raw = "The total estimated cost is ₹25,000 or Rs. 20000 for transport."
        cleaned = clean_speech_text(raw)
        assert "₹" not in cleaned
        assert "25,000 rupees" in cleaned
        assert "20000 rupees" in cleaned

    def test_clean_speech_text_handles_code_and_headers(self):
        raw = "# Day 1 in Shimla\n```python\nprint('code')\n```\nEnjoy `hiking` in the hills."
        cleaned = clean_speech_text(raw)
        assert "#" not in cleaned
        assert "print('code')" not in cleaned
        assert "Enjoy hiking in the hills." in cleaned

    def test_clean_speech_text_empty_input(self):
        assert clean_speech_text("") == ""
        assert clean_speech_text(None) == ""


class TestVoiceTranscriptValidation:
    """Verifies transcript validation and error categorization."""

    def test_valid_speech_transcript(self):
        res = validate_voice_transcript("I want to visit Manali next weekend with friends")
        assert res["valid"] is True
        assert res["error"] is None
        assert res["clean_transcript"] == "I want to visit Manali next weekend with friends"

    def test_empty_speech_transcript(self):
        res = validate_voice_transcript("   ")
        assert res["valid"] is False
        assert res["error"] == "empty_transcript"

    def test_symbols_only_transcript(self):
        res = validate_voice_transcript("... ??? ---")
        assert res["valid"] is False
        assert res["error"] == "unintelligible"


class TestVoiceSummarization:
    """Verifies speech summarization for long responses."""

    def test_summarize_for_speech_short_text(self):
        text = "Welcome to your trip to Jaipur."
        summary = summarize_for_speech(text, max_words=20)
        assert summary == text

    def test_summarize_for_speech_long_text_truncated_cleanly(self):
        text = (
            "Here is a comprehensive overview of your journey across the desert. "
            "Day one features a guided palace walk. "
            "Day two includes camel trekking and folk dancing under the stars. "
            "Day three offers local bazaar shopping and sunset views from the historic fortress walls. "
            "Make sure to bring water, sunglasses, and comfortable footwear for walking."
        )
        summary = summarize_for_speech(text, max_words=25)
        assert len(summary.split()) <= 26
        assert summary.endswith(".") or summary.endswith("...")


class TestVoiceAssistantEndpoints:
    """Verifies FastAPI voice routes."""

    def test_voice_status_endpoint(self):
        res = client.get("/voice/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ready"
        assert data["features"]["paid_apis"] is False
        assert "Web Speech API" in data["provider"]

    def test_voice_clean_text_endpoint(self):
        res = client.post(
            "/voice/clean-text",
            json={"text": "Explore **Lalbagh** and spend ₹500 for entry."},
        )
        assert res.status_code == 200
        data = res.json()
        assert "**" not in data["clean_text"]
        assert "500 rupees" in data["clean_text"]
        assert data["word_count"] > 0

    def test_voice_validate_transcript_endpoint(self):
        res = client.post(
            "/voice/validate-transcript",
            json={"transcript": "Plan a 3 day trip to Goa"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["clean_transcript"] == "Plan a 3 day trip to Goa"


class TestVoiceIntegrationWithConversationPipeline:
    """Verifies that voice-recognized transcripts integrate cleanly with the assistant pipeline."""

    def test_voice_input_routes_through_assistant_conversation(self, db_session):
        dest = Destination(
            name="Goa",
            country="India",
            lat=15.2993,
            lon=74.1240,
            tags="beach, relaxing",
            avg_rating=4.5,
        )
        db_session.add(dest)
        db_session.commit()

        # Simulate speech-to-text recognized query
        speech_recognized_message = "I want to take a 3 day relaxing trip to Goa with a budget of 40000 for 2 travelers"

        res = client.post(
            "/assistant/message",
            json={"message": speech_recognized_message},
        )
        assert res.status_code == 200
        data = res.json()
        assert "reply" in data
        assert data["slots"]["duration_days"] == 3
        assert data["slots"]["travelers"] == 2
        # Cleaned speech version of the reply can be generated without error
        clean_reply = clean_speech_text(data["reply"])
        assert len(clean_reply) > 0
