"""
Tests for Phase 6.2: Kannada OCR and Translation Support.

Verifies:
1. Real Kannada text image extraction via Tesseract (kan.traineddata).
2. Real English text image extraction via Tesseract (eng.traineddata).
3. English-to-Kannada and Kannada-to-English translation.
4. Graceful handling of missing Kannada language data with descriptive error message.
5. Error handling for invalid file types, empty files, corrupt images, and blank images.
6. Language normalization (kn/kan/kannada -> kan).
7. Kannada language display name formatting as 'Kannada (ಕನ್ನಡ)'.
8. API endpoints for OCR and Translation with Kannada support.
"""
import io
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app
from app.services.ocr_service import (
    extract_text_from_image,
    normalize_ocr_lang,
    get_available_ocr_languages,
    SUPPORTED_OCR_LANGUAGES,
)
from app.services.translation_service import (
    translate_text,
    get_supported_languages,
    SUPPORTED_LANGUAGES,
)


@pytest.fixture
def client():
    return TestClient(app)


def _make_kannada_png_bytes(text: str = "ನಮಸ್ಕಾರ ಕರ್ನಾಟಕ") -> bytes:
    """Create a high-contrast PNG with authentic Kannada text rendered using system font."""
    img = Image.new("RGB", (650, 160), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/Nirmala.ttc", 36)
    except Exception:
        font = None
    draw.text((25, 30), text, fill=(0, 0, 0), font=font)
    draw.text((25, 90), "ಪ್ರವಾಸೋದ್ಯಮ ಇಲಾಖೆ", fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_english_png_bytes(text: str = "Welcome to Bengaluru, Karnataka!") -> bytes:
    """Create a PNG with clear English text."""
    img = Image.new("RGB", (650, 120), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 32)
    except Exception:
        font = None
    draw.text((25, 40), text, fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_blank_png_bytes() -> bytes:
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ============================================================================
# 1. Kannada OCR Service Unit & Real Image Tests
# ============================================================================

class TestKannadaOCRService:
    def test_normalize_ocr_language(self):
        assert normalize_ocr_lang("kan") == "kan"
        assert normalize_ocr_lang("kn") == "kan"
        assert normalize_ocr_lang("kannada") == "kan"
        assert normalize_ocr_lang("KANNADA") == "kan"
        assert normalize_ocr_lang("eng") == "eng"
        assert normalize_ocr_lang("en") == "eng"
        assert normalize_ocr_lang("english") == "eng"
        assert normalize_ocr_lang("kan+eng") == "kan+eng"
        assert normalize_ocr_lang("kn+en") == "kan+eng"
        assert normalize_ocr_lang(None) == "eng"
        assert normalize_ocr_lang("") == "eng"

    def test_available_ocr_languages_includes_kan_and_eng(self):
        langs = get_available_ocr_languages()
        assert "eng" in langs, "English traineddata must be present"
        assert "kan" in langs, "Kannada traineddata must be present in tessdata"

    def test_real_kannada_image_ocr_extraction(self):
        """Test OCR extraction on an actual image containing Kannada Unicode text."""
        kannada_png = _make_kannada_png_bytes("ನಮಸ್ಕಾರ ಕರ್ನಾಟಕ")
        result = extract_text_from_image(kannada_png, "kannada_sign.png", lang="kan")

        assert result["error"] is None, f"Expected successful extraction, got error: {result['error']}"
        assert result["engine"] == "tesseract"
        assert result["lang"] == "kan"
        assert result["text"] is not None and len(result["text"]) > 0

        # Verify that extracted text contains actual Kannada Unicode block characters (U+0C80 to U+0CFF)
        has_kannada_chars = any("\u0c80" <= ch <= "\u0cff" for ch in result["text"])
        assert has_kannada_chars, f"Extracted text should contain Kannada script characters, got: {result['text']}"

    def test_real_english_image_ocr_preserved(self):
        """Preserve existing English OCR functionality."""
        english_png = _make_english_png_bytes("Welcome to Bengaluru")
        result = extract_text_from_image(english_png, "english_menu.png", lang="eng")

        assert result["error"] is None
        assert result["engine"] == "tesseract"
        assert result["lang"] == "eng"
        assert result["text"] is not None
        assert "Bengaluru" in result["text"] or "Welcome" in result["text"]

    def test_missing_kannada_traineddata_error_handling(self):
        """When kan.traineddata is missing, service returns a clear, helpful error message."""
        kannada_png = _make_kannada_png_bytes()
        with patch("app.services.ocr_service.get_available_ocr_languages", return_value=["eng"]):
            result = extract_text_from_image(kannada_png, "kannada.png", lang="kan")

        assert result["text"] is None
        assert result["error"] is not None
        assert "kan.traineddata" in result["error"].lower() or "kannada ocr language data" in result["error"].lower()

    def test_invalid_file_format_rejected(self):
        result = extract_text_from_image(b"%PDF-1.4 fake pdf", "document.pdf", lang="kan")
        assert result["text"] is None
        assert result["error"] is not None
        assert "unsupported" in result["error"].lower() or "pdf" in result["error"].lower()

    def test_empty_file_rejected(self):
        result = extract_text_from_image(b"", "empty.png", lang="kan")
        assert result["text"] is None
        assert "empty" in result["error"].lower()

    def test_corrupt_image_rejected(self):
        result = extract_text_from_image(b"not-a-valid-image-data", "bad.png", lang="kan")
        assert result["text"] is None
        assert "corrupt" in result["error"].lower() or "decoded" in result["error"].lower()

    def test_blank_image_returns_error_no_fabrication(self):
        blank_png = _make_blank_png_bytes()
        result = extract_text_from_image(blank_png, "blank.png", lang="kan")
        assert result["text"] is None
        assert result["error"] is not None
        assert "no text could be extracted" in result["error"].lower()


# ============================================================================
# 2. Kannada Translation Tests (Bidirectional & UI Label)
# ============================================================================

class TestKannadaTranslationService:
    def test_kannada_display_name_in_supported_languages(self):
        langs = get_supported_languages()
        kn_entry = next((item for item in langs if item["code"] == "kn"), None)
        assert kn_entry is not None, "Kannada ('kn') must be in supported languages"
        assert kn_entry["name"] == "Kannada (ಕನ್ನಡ)", "Must display as 'Kannada (ಕನ್ನಡ)'"

    def test_english_to_kannada_translation(self):
        """English text translates to authentic Kannada script."""
        english_text = "Welcome to Karnataka! Enjoy your trip."
        result = translate_text(english_text, target_lang="kn", source_lang="en")

        assert result["error"] is None
        assert result["translated_text"] is not None
        assert result["target_language"] == "kn"

        # Check for Kannada Unicode characters
        has_kannada = any("\u0c80" <= ch <= "\u0cff" for ch in result["translated_text"])
        assert has_kannada, f"Expected Kannada script output, got: {result['translated_text']}"

    def test_kannada_to_english_translation(self):
        """Kannada script translates to English."""
        kannada_text = "ನಮಸ್ಕಾರ, ಕರ್ನಾಟಕಕ್ಕೆ ಸುಸ್ವಾಗತ!"
        result = translate_text(kannada_text, target_lang="en", source_lang="kn")

        assert result["error"] is None
        assert result["translated_text"] is not None
        assert result["target_language"] == "en"
        text_lower = result["translated_text"].lower()
        assert any(word in text_lower for word in ["hello", "welcome", "karnataka"])


# ============================================================================
# 3. Kannada Endpoints Integration Tests
# ============================================================================

class TestKannadaEndpoints:
    def test_get_ocr_languages_endpoint(self, client):
        res = client.get("/ocr/languages")
        assert res.status_code == 200
        data = res.json()
        codes = {item["code"]: item for item in data}
        assert "kan" in codes
        assert "eng" in codes
        assert codes["kan"]["name"] == "Kannada (ಕನ್ನಡ)"
        assert codes["kan"]["installed"] is True

    def test_extract_endpoint_kannada_image(self, client):
        png_bytes = _make_kannada_png_bytes("ಕರ್ನಾಟಕ ಪ್ರವಾಸ")
        res = client.post(
            "/ocr/extract?lang=kan",
            files={"file": ("sign.png", png_bytes, "image/png")},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["lang"] == "kan"
        assert data["engine"] == "tesseract"
        assert data["text"] is not None
        has_kannada = any("\u0c80" <= ch <= "\u0cff" for ch in data["text"])
        assert has_kannada

    def test_ocr_and_translate_endpoint_kannada_to_english(self, client):
        png_bytes = _make_kannada_png_bytes("ಕರ್ನಾಟಕ ಸುಸ್ವಾಗತ")
        res = client.post(
            "/translate/ocr?target_lang=en&ocr_lang=kan",
            files={"file": ("kannada_board.png", png_bytes, "image/png")},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["ocr_lang"] == "kan"
        assert data["ocr_engine"] == "tesseract"
        assert data["original_text"] is not None
        assert data["translated_text"] is not None
        assert data["target_language"] == "en"

    def test_ocr_and_translate_endpoint_english_to_kannada(self, client):
        png_bytes = _make_english_png_bytes("Tourist Information Center")
        res = client.post(
            "/translate/ocr?target_lang=kn&ocr_lang=eng",
            files={"file": ("sign.png", png_bytes, "image/png")},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["ocr_lang"] == "eng"
        assert data["original_text"] is not None
        assert data["translated_text"] is not None
        assert data["target_language"] == "kn"
        has_kannada = any("\u0c80" <= ch <= "\u0cff" for ch in data["translated_text"])
        assert has_kannada
