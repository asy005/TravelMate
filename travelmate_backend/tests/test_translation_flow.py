"""
Tests for the improved OCR→Translation flow:
- Language code accuracy: 'hi', 'ta', 'ja' reach the LLM prompt correctly
- Prompt enforces target language output and price preservation
- Retry / fallback path after translation failure
- Combined endpoint forwards target_lang correctly
"""
import io
import pytest
from unittest.mock import patch, MagicMock, call
from PIL import Image, ImageDraw


def _make_menu_png() -> bytes:
    img = Image.new("RGB", (500, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((10, 20), "Masala Dosa ... Rs. 60", fill=(0, 0, 0))
    draw.text((10, 70), "Filter Coffee .. Rs. 20", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def client():
    from app.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


# ─── 1. Language code routing ─────────────────────────────────────────────────

class TestLanguageCodeRouting:
    """Verify the target_lang parameter reaches translate_text correctly."""

    def _capture_system_prompt(self, target_lang: str, translated_return: str = "translated output") -> str:
        """Helper: call _translate_via_llm, capture system prompt, return it."""
        from app.services.translation_service import _translate_via_llm
        captured = []

        # chat_completion is locally imported from llm_gateway inside _translate_via_llm
        def fake_chat(messages, **kw):
            for m in messages:
                if m.get("role") == "system":
                    captured.append(m["content"])
            return translated_return

        with patch("app.services.llm_gateway.chat_completion", side_effect=fake_chat):
            _translate_via_llm("Masala Dosa ... Rs. 60", target_lang, "en")

        return captured[0] if captured else ""

    def test_system_prompt_contains_hindi_when_target_is_hi(self):
        prompt = self._capture_system_prompt("hi", "मसाला डोसा ... Rs. 60")
        assert "Hindi" in prompt, f"Expected 'Hindi' in prompt, got: {prompt[:300]}"

    def test_system_prompt_contains_tamil_when_target_is_ta(self):
        prompt = self._capture_system_prompt("ta", "மசாலா தோசை ... Rs. 60")
        assert "Tamil" in prompt, f"Expected 'Tamil' in prompt, got: {prompt[:300]}"

    def test_system_prompt_contains_japanese_when_target_is_ja(self):
        prompt = self._capture_system_prompt("ja", "マサラドーサ ... Rs. 60")
        assert "Japanese" in prompt, f"Expected 'Japanese' in prompt, got: {prompt[:300]}"

    def test_prompt_output_language_instruction_present(self):
        """Improved prompt must explicitly tell LLM to write in target language."""
        prompt = self._capture_system_prompt("hi")
        assert any(kw in prompt for kw in ["OUTPUT LANGUAGE", "entirely in", "EVERY translated line"]), (
            f"No output-language instruction found in prompt: {prompt[:400]}"
        )

    def test_target_lang_is_forwarded_in_combined_endpoint(self, client):
        """/translate/ocr endpoint must pass target_lang='hi' to translate_text."""
        png = _make_menu_png()
        forwarded_langs = []

        def capturing_translate(text, target_lang, source_lang="auto"):
            forwarded_langs.append(target_lang)
            return {
                "translated_text": "मसाला डोसा ... Rs. 60",
                "source_language": "en",
                "target_language": target_lang,
                "provider": "llm",
                "error": None,
            }

        with patch("app.services.ocr_service._try_tesseract",
                   return_value="Masala Dosa ... Rs. 60\nFilter Coffee .. Rs. 20"), \
             patch("app.routes.translation_routes.translate_text", side_effect=capturing_translate):
            response = client.post(
                "/translate/ocr?target_lang=hi&ocr_lang=eng",
                files={"file": ("menu.png", png, "image/png")},
            )

        assert response.status_code == 200
        data = response.json()
        assert forwarded_langs == ["hi"], f"Expected ['hi'], got: {forwarded_langs}"
        assert data["target_language"] == "hi"

    def test_translate_text_endpoint_forwards_target_lang(self, client):
        """POST /translate/text passes target_lang to the service correctly."""
        forwarded = []

        def capturing_translate(text, target_lang, source_lang="auto"):
            forwarded.append(target_lang)
            return {
                "translated_text": "தமிழ் உணவு",
                "source_language": "en",
                "target_language": target_lang,
                "provider": "llm",
                "error": None,
            }

        with patch("app.routes.translation_routes.translate_text", side_effect=capturing_translate):
            response = client.post(
                "/translate/text",
                json={"text": "Tamil food", "target_lang": "ta", "source_lang": "en"},
            )

        assert response.status_code == 200
        assert forwarded == ["ta"], f"Expected ['ta'], got: {forwarded}"
        assert response.json()["target_language"] == "ta"


# ─── 2. Price preservation ────────────────────────────────────────────────────

class TestPricePreservation:
    """The service must never invent or drop prices."""

    def test_ocr_translate_preserves_price_in_llm_output(self, client):
        png = _make_menu_png()
        with patch("app.services.ocr_service._try_tesseract",
                   return_value="Masala Dosa ... Rs. 60"), \
             patch("app.services.translation_service._translate_via_llm",
                   return_value={"translated_text": "मसाला डोसा ... Rs. 60", "provider": "llm", "error": None}):
            response = client.post(
                "/translate/ocr?target_lang=hi&ocr_lang=eng",
                files={"file": ("menu.png", png, "image/png")},
            )
        data = response.json()
        assert "Rs. 60" in data["translated_text"], (
            f"Price 'Rs. 60' missing from translation: {data['translated_text']}"
        )

    def test_translate_text_endpoint_preserves_price(self, client):
        with patch("app.services.translation_service._translate_via_llm",
                   return_value={"translated_text": "தோசை ... Rs. 60", "provider": "llm", "error": None}):
            response = client.post(
                "/translate/text",
                json={"text": "Dosa ... Rs. 60", "target_lang": "ta", "source_lang": "en"},
            )
        assert response.status_code == 200
        assert "Rs. 60" in response.json()["translated_text"]

    def test_price_instruction_in_prompt(self):
        """System prompt must instruct LLM to preserve prices exactly."""
        from app.services.translation_service import _translate_via_llm
        captured = []

        def fake_chat(messages, **kw):
            for m in messages:
                if m.get("role") == "system":
                    captured.append(m["content"])
            return "output"

        with patch("app.services.llm_gateway.chat_completion", side_effect=fake_chat):
            _translate_via_llm("Masala Dosa Rs. 60", "ja", "en")

        prompt = captured[0] if captured else ""
        assert "price" in prompt.lower() or "rs." in prompt.lower() or "preserve" in prompt.lower(), (
            f"No price instruction in prompt: {prompt[:400]}"
        )


# ─── 3. Retry / error path ────────────────────────────────────────────────────

class TestRetryPath:
    """LLM failure → deep-translator fallback; full failure → error, not silent original."""

    def test_llm_failure_triggers_deep_translator_fallback(self):
        from app.services.translation_service import translate_text
        with patch("app.services.translation_service._translate_via_llm",
                   return_value={"translated_text": None, "provider": "llm", "error": "timeout"}), \
             patch("app.services.translation_service._translate_via_deep",
                   return_value={"translated_text": "मसाला डोसा", "provider": "deep-translator", "error": None}):
            result = translate_text("Masala Dosa", "hi")
        assert result["translated_text"] == "मसाला डोसा"
        assert result["provider"] == "deep-translator"
        assert result["error"] is None

    def test_full_failure_returns_error_not_original(self):
        from app.services.translation_service import translate_text
        original = "Masala Dosa ... Rs. 60"
        with patch("app.services.translation_service._translate_via_llm",
                   return_value={"translated_text": None, "provider": "llm", "error": "LLM fail"}), \
             patch("app.services.translation_service._translate_via_deep",
                   return_value={"translated_text": None, "provider": "deep-translator", "error": "network error"}):
            result = translate_text(original, "ta")
        assert result["translated_text"] is None, "Must not silently return untranslated text"
        assert result["error"] is not None

    def test_ocr_endpoint_returns_error_on_full_translation_failure(self, client):
        png = _make_menu_png()
        with patch("app.services.ocr_service._try_tesseract", return_value="Masala Dosa"), \
             patch("app.services.translation_service._translate_via_llm",
                   return_value={"translated_text": None, "provider": "llm", "error": "fail"}), \
             patch("app.services.translation_service._translate_via_deep",
                   return_value={"translated_text": None, "provider": "deep-translator", "error": "fail"}):
            response = client.post(
                "/translate/ocr?target_lang=ja",
                files={"file": ("menu.png", png, "image/png")},
            )
        data = response.json()
        assert data["translated_text"] is None
        assert data["error"] is not None

    def test_unsupported_lang_returns_clear_error(self):
        from app.services.translation_service import translate_text
        result = translate_text("Hello", "xx")
        assert result["translated_text"] is None
        assert result["error"] is not None
        assert "unsupported" in result["error"].lower()
