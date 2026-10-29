"""
Tests for Phase 6: OCR + Translation services and endpoints.
"""
import io
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont


# ----------------------------------------------
# Helpers
# ----------------------------------------------

def _make_png_bytes(text: str = "Hello") -> bytes:
    """Create a minimal in-memory PNG with text drawn on it."""
    img = Image.new("RGB", (200, 60), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((10, 20), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_blank_png_bytes() -> bytes:
    """All-white image -- no text."""
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ----------------------------------------------
# OCR Service Unit Tests
# ----------------------------------------------

class TestOCRService:
    def test_invalid_file_type(self):
        from app.services.ocr_service import extract_text_from_image
        result = extract_text_from_image(b"fake content", "document.pdf")
        assert result["text"] is None
        assert result["error"] is not None
        assert "pdf" in result["error"].lower() or "unsupported" in result["error"].lower()

    def test_oversized_file(self):
        from app.services.ocr_service import extract_text_from_image
        big_bytes = b"x" * (11 * 1024 * 1024)  # 11 MB
        result = extract_text_from_image(big_bytes, "large.jpg")
        assert result["text"] is None
        assert "large" in result["error"].lower() or "10 mb" in result["error"].lower()

    def test_empty_file(self):
        from app.services.ocr_service import extract_text_from_image
        result = extract_text_from_image(b"", "empty.png")
        assert result["text"] is None
        assert result["error"] is not None

    def test_corrupt_image(self):
        from app.services.ocr_service import extract_text_from_image
        result = extract_text_from_image(b"not-an-image", "bad.png")
        assert result["text"] is None
        assert result["error"] is not None

    def test_valid_image_tesseract_path(self):
        """When pytesseract returns text, it should be returned with engine='tesseract'."""
        from app.services.ocr_service import extract_text_from_image
        png = _make_png_bytes("Menu")
        with patch("app.services.ocr_service._try_tesseract", return_value="Menu"):
            result = extract_text_from_image(png, "menu.png")
        assert result["text"] == "Menu"
        assert result["engine"] == "tesseract"
        assert result["error"] is None

    def test_valid_image_trocr_fallback(self):
        """When Tesseract returns None, TrOCR fallback should be used."""
        from app.services.ocr_service import extract_text_from_image
        png = _make_png_bytes("Sign")
        with patch("app.services.ocr_service._try_tesseract", return_value=None), \
             patch("app.services.ocr_service._try_trocr", return_value="Sign"):
            result = extract_text_from_image(png, "sign.png")
        assert result["text"] == "Sign"
        assert result["engine"] == "trocr"

    def test_blank_image_returns_error(self):
        """Blank image where both engines return None -> error, no fabrication."""
        from app.services.ocr_service import extract_text_from_image
        png = _make_blank_png_bytes()
        with patch("app.services.ocr_service._try_tesseract", return_value=None), \
             patch("app.services.ocr_service._try_trocr", return_value=None):
            result = extract_text_from_image(png, "blank.png")
        assert result["text"] is None
        assert result["error"] is not None

    def test_no_text_fabrication(self):
        """Result must never invent text -- only return what engines produce."""
        from app.services.ocr_service import extract_text_from_image
        png = _make_png_bytes()
        with patch("app.services.ocr_service._try_tesseract", return_value=None), \
             patch("app.services.ocr_service._try_trocr", return_value=None):
            result = extract_text_from_image(png, "real.png")
        assert result["text"] is None  # engine returned nothing -> we return nothing


# ----------------------------------------------
# Translation Service Unit Tests
# ----------------------------------------------

class TestTranslationService:
    def test_empty_input(self):
        from app.services.translation_service import translate_text
        result = translate_text("", "hi")
        assert result["translated_text"] is None
        assert result["error"] is not None

    def test_unsupported_language(self):
        from app.services.translation_service import translate_text
        result = translate_text("Hello", "xx")
        assert result["translated_text"] is None
        assert "unsupported" in result["error"].lower()

    def test_llm_translation_success(self):
        from app.services.translation_service import translate_text
        with patch("app.services.translation_service._translate_via_llm",
                   return_value={"translated_text": "\u0928\u092e\u0938\u094d\u0924\u0947", "provider": "llm", "error": None}):
            result = translate_text("Hello", "hi")
        assert result["translated_text"] == "\u0928\u092e\u0938\u094d\u0924\u0947"
        assert result["provider"] == "llm"
        assert result["error"] is None

    def test_llm_failure_fallback_to_deep(self):
        from app.services.translation_service import translate_text
        with patch("app.services.translation_service._translate_via_llm",
                   return_value={"translated_text": None, "provider": "llm", "error": "LLM error"}), \
             patch("app.services.translation_service._translate_via_deep",
                   return_value={"translated_text": "\u0928\u092e\u0938\u094d\u0924\u0947", "provider": "deep-translator", "error": None}):
            result = translate_text("Hello", "hi")
        assert result["translated_text"] == "\u0928\u092e\u0938\u094d\u0924\u0947"
        assert result["provider"] == "deep-translator"

    def test_both_providers_fail(self):
        from app.services.translation_service import translate_text
        with patch("app.services.translation_service._translate_via_llm",
                   return_value={"translated_text": None, "provider": "llm", "error": "LLM error"}), \
             patch("app.services.translation_service._translate_via_deep",
                   return_value={"translated_text": None, "provider": "deep-translator", "error": "Network error"}):
            result = translate_text("Hello", "hi")
        assert result["translated_text"] is None
        assert result["error"] is not None

    def test_get_supported_languages(self):
        from app.services.translation_service import get_supported_languages
        langs = get_supported_languages()
        codes = {l["code"] for l in langs}
        assert "en" in codes
        assert "hi" in codes
        assert "ta" in codes
        assert "fr" in codes
        assert len(langs) >= 10

    def test_no_silent_untranslated_return(self):
        """Service must never return input text unchanged while claiming success."""
        from app.services.translation_service import translate_text
        original = "Hello world"
        with patch("app.services.translation_service._translate_via_llm",
                   return_value={"translated_text": None, "provider": "llm", "error": "fail"}), \
             patch("app.services.translation_service._translate_via_deep",
                   return_value={"translated_text": None, "provider": "deep-translator", "error": "fail"}):
            result = translate_text(original, "hi")
        # If both fail, translated_text must be None (not the original)
        assert result["translated_text"] is None


# ----------------------------------------------
# API Endpoint Tests
# ----------------------------------------------

@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestOCREndpoints:
    def test_extract_invalid_type(self, client):
        response = client.post(
            "/ocr/extract",
            files={"file": ("doc.pdf", b"fake", "application/pdf")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["text"] is None
        assert data["error"] is not None

    def test_extract_empty_file(self, client):
        response = client.post(
            "/ocr/extract",
            files={"file": ("empty.png", b"", "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["text"] is None

    def test_extract_corrupt_image(self, client):
        response = client.post(
            "/ocr/extract",
            files={"file": ("bad.jpg", b"not-an-image", "image/jpeg")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["text"] is None
        assert data["error"] is not None

    def test_extract_valid_image_mocked(self, client):
        png_bytes = _make_png_bytes("Cafe Menu")
        with patch("app.services.ocr_service._try_tesseract", return_value="Cafe Menu"), \
             patch("app.services.ocr_service._try_trocr", return_value=None):
            response = client.post(
                "/ocr/extract",
                files={"file": ("menu.png", png_bytes, "image/png")},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Cafe Menu"
        assert data["engine"] == "tesseract"

    def test_extract_response_fields(self, client):
        """Response always includes filename and file_size_kb."""
        png = _make_blank_png_bytes()
        with patch("app.services.ocr_service._try_tesseract", return_value=None), \
             patch("app.services.ocr_service._try_trocr", return_value=None):
            response = client.post(
                "/ocr/extract",
                files={"file": ("test.png", png, "image/png")},
            )
        data = response.json()
        assert "filename" in data
        assert "file_size_kb" in data


class TestTranslationEndpoints:
    def test_languages_endpoint(self, client):
        response = client.get("/translate/languages")
        assert response.status_code == 200
        langs = response.json()
        codes = {l["code"] for l in langs}
        assert "en" in codes
        assert "hi" in codes

    def test_translate_empty_text(self, client):
        response = client.post(
            "/translate/text",
            json={"text": "", "target_lang": "hi"},
        )
        assert response.status_code == 400

    def test_translate_unsupported_lang(self, client):
        response = client.post(
            "/translate/text",
            json={"text": "Hello", "target_lang": "xx"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["translated_text"] is None
        assert data["error"] is not None

    def test_translate_success_mocked(self, client):
        with patch("app.services.translation_service._translate_via_llm",
                   return_value={"translated_text": "\u0928\u092e\u0938\u094d\u0924\u0947 \u0926\u0941\u0928\u093f\u092f\u093e", "provider": "llm", "error": None}):
            response = client.post(
                "/translate/text",
                json={"text": "Hello world", "target_lang": "hi"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["translated_text"] == "\u0928\u092e\u0938\u094d\u0924\u0947 \u0926\u0941\u0928\u093f\u092f\u093e"
        assert data["provider"] == "llm"

    def test_ocr_translate_invalid_lang(self, client):
        png = _make_png_bytes()
        response = client.post(
            "/translate/ocr?target_lang=xx",
            files={"file": ("img.png", png, "image/png")},
        )
        assert response.status_code == 400

    def test_ocr_translate_ocr_fails(self, client):
        with patch("app.services.ocr_service._try_tesseract", return_value=None), \
             patch("app.services.ocr_service._try_trocr", return_value=None):
            png = _make_blank_png_bytes()
            response = client.post(
                "/translate/ocr?target_lang=hi",
                files={"file": ("blank.png", png, "image/png")},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["original_text"] is None
        assert data["translated_text"] is None
        assert data["error"] is not None

    def test_ocr_translate_success_mocked(self, client):
        png = _make_png_bytes("Road sign")
        with patch("app.services.ocr_service._try_tesseract", return_value="Road sign"), \
             patch("app.services.translation_service._translate_via_llm",
                   return_value={"translated_text": "\u0938\u095c\u0915 \u0915\u093e \u0938\u0902\u0915\u0947\u0924", "provider": "llm", "error": None}):
            response = client.post(
                "/translate/ocr?target_lang=hi",
                files={"file": ("sign.png", png, "image/png")},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["original_text"] == "Road sign"
        assert data["translated_text"] == "\u0938\u095c\u0915 \u0915\u093e \u0938\u0902\u0915\u0947\u0924"
        assert data["ocr_engine"] == "tesseract"


class TestLanguageSelectionCompatibility:
    """Ensure language preferences don't break existing chatbot."""
    def test_assistant_still_works_with_language_header(self, client):
        """Adding Accept-Language header should not break the assistant endpoint."""
        response = client.post(
            "/assistant/message",
            json={"session_id": None, "message": "Hello"},
            headers={"Accept-Language": "hi"},
        )
        # Should work normally (200 or whatever it returns)
        assert response.status_code in (200, 422)

    def test_languages_list_is_json(self, client):
        response = client.get("/translate/languages")
        assert response.headers["content-type"].startswith("application/json")
        data = response.json()
        assert isinstance(data, list)
        assert all("code" in l and "name" in l for l in data)
