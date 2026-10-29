"""
Focused unit & integration tests for Menu OCR, Google Cloud Vision,
improved image preprocessing, and reliable translation.
"""
import io
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image, ImageDraw, ImageFont

from app.services.ocr_service import (
    extract_text_from_image,
    _clean_menu_ocr_text,
    _preprocess_for_ocr,
    _try_google_vision,
)
from app.services.translation_service import (
    translate_text,
    translate_texts_batch,
    _translate_via_deep,
)


def _make_menu_sample_png() -> bytes:
    """Create a realistic Kannada + English menu test image."""
    img = Image.new("RGB", (700, 320), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/Nirmala.ttc", 22)
    except Exception:
        font = None
    draw.text((20, 20), "Hotel Udupi Upahar", fill=(0, 0, 0), font=font)
    draw.text((20, 70), "Masala Dosa ............. Rs. 60", fill=(0, 0, 0), font=font)
    draw.text((20, 120), "Idli Vada ................ Rs. 40", fill=(0, 0, 0), font=font)
    draw.text((20, 170), "Filter Coffee ............ Rs. 20", fill=(0, 0, 0), font=font)
    draw.text((20, 220), "Tea ...................... Rs. 15", fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestGoogleCloudVisionOCR:
    def test_gvision_unconfigured_falls_back_to_tesseract(self):
        """When GOOGLE_VISION_API_KEY is not set, skips Vision and uses Tesseract."""
        png_bytes = _make_menu_sample_png()
        with patch.dict("os.environ", {}, clear=True), \
             patch("app.config.settings.GOOGLE_VISION_API_KEY", ""):
            res = extract_text_from_image(png_bytes, "menu.png", lang="eng")
            assert res["error"] is None
            assert res["engine"] in ("tesseract", "trocr")

    def test_gvision_success_returns_vision_engine(self):
        """When GOOGLE_VISION_API_KEY is set and API responds with text, use google-cloud-vision."""
        png_bytes = _make_menu_sample_png()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "responses": [
                {
                    "fullTextAnnotation": {
                        "text": "Hotel Udupi Upahar\nMasala Dosa ... Rs. 60\nIdli Vada ... Rs. 40"
                    }
                }
            ]
        }

        with patch.dict("os.environ", {"GOOGLE_VISION_API_KEY": "fake_test_key"}), \
             patch("httpx.Client.post", return_value=mock_response):
            res = extract_text_from_image(png_bytes, "menu.png", lang="kan+eng")
            assert res["error"] is None
            assert res["engine"] == "google-cloud-vision"
            assert "Masala Dosa" in res["text"]
            assert "Rs. 60" in res["text"]

    def test_gvision_api_failure_falls_back_to_tesseract(self):
        """When Google Vision API fails (e.g. 500 or timeout), seamlessly fallback to Tesseract."""
        png_bytes = _make_menu_sample_png()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.dict("os.environ", {"GOOGLE_VISION_API_KEY": "fake_key"}), \
             patch("httpx.Client.post", return_value=mock_response):
            res = extract_text_from_image(png_bytes, "menu.png", lang="eng")
            assert res["error"] is None
            assert res["engine"] in ("tesseract", "trocr")


class TestMenuTextPreprocessing:
    def test_clean_menu_ocr_text_cleans_leaders_and_noise(self):
        raw = "Hotel Udupi\n.....\nMasala Dosa .......... Rs. 60\n---~\nIdli Vada ..... Rs. 40\n"
        cleaned = _clean_menu_ocr_text(raw)
        assert cleaned is not None
        assert "Masala Dosa ... Rs. 60" in cleaned
        assert "Idli Vada ... Rs. 40" in cleaned
        assert "-----~" not in cleaned
        # Isolated noise line should be removed
        lines = cleaned.splitlines()
        assert not any(l == "....." for l in lines)

    def test_preprocess_for_ocr_caps_upscaling(self):
        """Ensure small images are not scaled beyond 2.2x to prevent Lanczos ringing."""
        small_img = Image.new("RGB", (300, 100), color=(255, 255, 255))
        processed = _preprocess_for_ocr(small_img, lang="kan")
        w, h = processed.size
        # With cap 2.2x on 300px, long side should not exceed 300 * 2.2 = 660px
        assert max(w, h) <= 660
        assert processed.mode == "L"  # Grayscale for cleaner thresholding


class TestTranslationReliability:
    def test_translate_texts_batch_preserves_original_and_handles_items(self):
        items = ["Masala Dosa - Rs. 60", "Idli Vada - Rs. 40", ""]
        with patch("app.services.translation_service.translate_text") as mock_t:
            mock_t.return_value = {
                "translated_text": "Masala Dosa - Rs. 60\n---TM_SEP---\nIdli Vada - Rs. 40",
                "provider": "llm",
                "error": None,
            }
            results = translate_texts_batch(items, "hi", chunk_size=10)
            assert len(results) == 3
            assert results[0]["original_text"] == "Masala Dosa - Rs. 60"
            assert results[0]["translated_text"] == "Masala Dosa - Rs. 60"
            assert results[2]["original_text"] == ""
            assert results[2]["translated_text"] == ""

    def test_translate_texts_batch_per_item_fallback_on_delimiter_mismatch(self):
        items = ["Masala Dosa - Rs. 60", "Idli Vada - Rs. 40"]
        # Batch combined call returns unexpected format -> falls back per item
        with patch("app.services.translation_service.translate_text") as mock_t:
            mock_t.side_effect = [
                {"translated_text": "Single block output without delimiter", "provider": "llm", "error": None},
                {"translated_text": "मसाला डोसा - Rs. 60", "provider": "llm", "error": None},
                {"translated_text": "इडली वड़ा - Rs. 40", "provider": "llm", "error": None},
            ]
            results = translate_texts_batch(items, "hi", chunk_size=10)
            assert len(results) == 2
            assert results[0]["translated_text"] == "मसाला डोसा - Rs. 60"
            assert results[1]["translated_text"] == "इडली वड़ा - Rs. 40"

    def test_deep_translator_rejects_untranslated_kannada_false_success(self):
        """When Kannada input returns identical Kannada text in English target, fail rather than false success."""
        with patch("deep_translator.GoogleTranslator.translate", return_value="ನಮಸ್ಕಾರ ಕರ್ನಾಟಕ"):
            res = _translate_via_deep("ನಮಸ್ಕಾರ ಕರ್ನಾಟಕ", "en", "kn")
            assert res["translated_text"] is None
            assert res["error"] is not None
            assert "kannada" in res["error"].lower()
