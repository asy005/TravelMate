import io
import os
import shutil
import logging
from typing import Optional, List
from PIL import Image

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
except Exception:
    pass

logger = logging.getLogger(__name__)
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/jpg"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

SUPPORTED_OCR_LANGUAGES = {
    "eng": "English",
    "en": "English",
    "kan": "Kannada (ಕನ್ನಡ)",
    "kn": "Kannada (ಕನ್ನಡ)",
    "kan+eng": "Kannada + English",
    "eng+kan": "English + Kannada",
}

INDIAN_OCR_LANGUAGES: dict = {
    "eng": "English",
    "kan": "Kannada (ಕನ್ನಡ)",
    "hin": "Hindi (हिन्दी)",
    "tam": "Tamil (தமிழ்)",
    "tel": "Telugu (తెలుగు)",
    "mal": "Malayalam (മലയാളം)",
    "ben": "Bengali (বাংলা)",
    "mar": "Marathi (मराठी)",
    "guj": "Gujarati (ગુજરાતી)",
    "pan": "Punjabi (ਪੰਜਾਬੀ)",
    "ori": "Odia (ଓଡ଼ିଆ)",
    "asm": "Assamese (অসমীয়া)",
    "urd": "Urdu (اردو)",
}

BILINGUAL_COMBOS: list = [
    ("kan+eng", "Kannada + English"),
    ("hin+eng", "Hindi + English"),
    ("tam+eng", "Tamil + English"),
    ("tel+eng", "Telugu + English"),
    ("mal+eng", "Malayalam + English"),
    ("ben+eng", "Bengali + English"),
    ("mar+eng", "Marathi + English"),
]

_trocr_processor = None
_trocr_model = None

def _ensure_ocr_paths():
    cmd = os.getenv("TESSERACT_CMD")
    if not cmd or not os.path.exists(cmd):
        for candidate in [
            r"C:\TesseractOCR\tesseract.exe",
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]:
            if os.path.exists(candidate):
                os.environ["TESSERACT_CMD"] = candidate
                break

    cmd = os.getenv("TESSERACT_CMD")
    if cmd and os.path.exists(cmd) and not os.getenv("TESSDATA_PREFIX"):
        candidate_data = os.path.join(os.path.dirname(cmd), "tessdata")
        if os.path.exists(candidate_data):
            os.environ["TESSDATA_PREFIX"] = candidate_data

_ensure_ocr_paths()

def is_tesseract_available() -> bool:
    _ensure_ocr_paths()
    cmd = os.getenv("TESSERACT_CMD")
    if cmd and os.path.exists(cmd):
        return True
    return shutil.which("tesseract") is not None

def is_trocr_available() -> bool:
    global _trocr_processor, _trocr_model
    if _trocr_processor is not None and _trocr_model is not None:
        return True
    try:
        from transformers import TrOCRProcessor
        TrOCRProcessor.from_pretrained("microsoft/trocr-base-printed", local_files_only=True)
        return True
    except Exception:
        return False

def get_available_ocr_languages() -> List[str]:
    _ensure_ocr_paths()
    if not is_tesseract_available():
        return []
    try:
        import pytesseract
        cmd = os.getenv("TESSERACT_CMD")
        if cmd and os.path.exists(cmd):
            pytesseract.pytesseract.tesseract_cmd = cmd
        tessdata = os.getenv("TESSDATA_PREFIX")
        if tessdata:
            os.environ["TESSDATA_PREFIX"] = tessdata
        langs = pytesseract.get_languages()
        if langs:
            return langs
    except Exception as exc:
        logger.debug("pytesseract.get_languages() exception: %s", exc)

    tessdata = os.getenv("TESSDATA_PREFIX")
    if tessdata and os.path.isdir(tessdata):
        return [
            f[:-12]
            for f in os.listdir(tessdata)
            if f.endswith(".traineddata")
        ]
    return ["eng"]

def normalize_ocr_lang(lang: Optional[str]) -> str:
    if not lang:
        return "eng"
    code = lang.strip().lower()
    _ALIAS = {
        "kn": "kan", "kannada": "kan",
        "en": "eng", "english": "eng",
        "hi": "hin", "hindi": "hin",
        "ta": "tam", "tamil": "tam",
        "te": "tel", "telugu": "tel",
        "ml": "mal", "malayalam": "mal",
        "bn": "ben", "bengali": "ben",
        "mr": "mar", "marathi": "mar",
        "gu": "guj", "gujarati": "guj",
        "pa": "pan", "punjabi": "pan",
        "or": "ori", "odia": "ori", "oriya": "ori",
        "as": "asm", "assamese": "asm",
        "ur": "urd", "urdu": "urd",
    }
    if "+" in code:
        parts = [_ALIAS.get(p.strip(), p.strip()) for p in code.split("+")]
        return "+".join(parts)
    return _ALIAS.get(code, code)

def _validate_image(image_bytes: bytes, filename: str) -> Optional[str]:
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        return f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        return f"File too large ({len(image_bytes)//1024//1024} MB). Maximum allowed: 10 MB"
    if len(image_bytes) == 0:
        return "Empty file uploaded."
    return None


def _load_image(image_bytes: bytes) -> Optional[Image.Image]:
    try:
        from PIL import ImageOps
        img = Image.open(io.BytesIO(image_bytes))
        try:
            img = ImageOps.exif_transpose(img)
        except Exception as exif_exc:
            logger.debug("EXIF transpose skipped: %s", exif_exc)
        img = img.convert("RGB")
        img.load()  
        return img
    except Exception as exc:
        logger.warning("Failed to open image: %s", exc)
        return None

def _clean_menu_ocr_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    import re

    cleaned_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^[\.\,\-\_\:\;\|\~\'\`\^\*\s\¬\°\¢\©\®\§\+\=\<\>]+$", line):
            continue
        line = re.sub(r"\s*[\.·]{3,}\s*", " ... ", line)
        line = re.sub(r"\s*[-–—]{3,}\s*", " --- ", line)
        line = re.sub(r"(?i)\b(?:rs|re)\.?\s*(\d+)", r"Rs. \1", line)
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines) if cleaned_lines else None

def _try_google_vision(image_bytes: bytes, lang: str = "eng") -> Optional[str]:
    api_key = os.getenv("GOOGLE_VISION_API_KEY") or os.getenv("GOOGLE_CLOUD_VISION_API_KEY")
    if not api_key:
        try:
            from app.config import settings
            api_key = getattr(settings, "GOOGLE_VISION_API_KEY", "")
        except Exception:
            pass

    if not api_key or not api_key.strip():
        return None

    try:
        import base64
        import httpx

        b64_content = base64.b64encode(image_bytes).decode("utf-8")
        is_kannada = "kan" in lang
        language_hints = ["kn", "en"] if is_kannada else ["en"]

        payload = {
            "requests": [
                {
                    "image": {"content": b64_content},
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                    "imageContext": {"languageHints": language_hints},
                }
            ]
        }

        url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key.strip()}"
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                responses = data.get("responses", [])
                if responses:
                    res = responses[0]
                    if "error" in res:
                        logger.warning("Google Cloud Vision API error response: %s", res["error"])
                        return None
                    full_text = res.get("fullTextAnnotation", {}).get("text")
                    if full_text and full_text.strip():
                        return _clean_menu_ocr_text(full_text.strip())
                    annotations = res.get("textAnnotations", [])
                    if annotations and annotations[0].get("description"):
                        return _clean_menu_ocr_text(annotations[0]["description"].strip())
            else:
                logger.warning(
                    "Google Cloud Vision HTTP error %s: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return None
    except Exception as exc:
        logger.warning("Google Cloud Vision request exception: %s", exc)
        return None

    return None

def _preprocess_for_ocr(img: Image.Image, lang: str = "eng") -> Image.Image:
    try:
        from PIL import ImageEnhance, ImageOps

        w, h = img.size
        is_kannada = "kan" in lang

        target_long_side = 1400 if is_kannada else 1200
        long_side = max(w, h)
        if long_side < target_long_side:
            scale = min(2.2, target_long_side / long_side)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        gray = img.convert("L")

        gray = ImageOps.autocontrast(gray, cutoff=0.5)

        sharpener = ImageEnhance.Sharpness(gray)
        processed = sharpener.enhance(1.3 if is_kannada else 1.2)

        return processed
    except Exception as exc:
        logger.debug("Image preprocessing skipped: %s", exc)
        return img

def is_ocr_text_corrupted(text: Optional[str]) -> bool:
    """
    Check if the extracted OCR text is severely degraded or corrupted.
    Returns True if:
    - Text is None or empty.
    - Too few recognizable alphanumeric/script characters.
    - High proportion of Unicode replacement characters ('\\ufffd') or non-alphanumeric noise symbols.
    """
    if not text or not text.strip():
        return True

    clean = text.strip()
    total_chars = len(clean)
    if total_chars < 5:
        return True

    # High proportion of replacement characters
    if clean.count("\ufffd") / total_chars > 0.15:
        return True

    import unicodedata
    legible_count = 0
    noise_count = 0
    for ch in clean:
        if ch.isspace():
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("L") or cat.startswith("N"):
            legible_count += 1
        elif ch in ".,:;/-–—'\"()[]{}!?₹$€¥%#@*&":
            pass
        else:
            noise_count += 1

    if legible_count < 4:
        return True

    if legible_count / (legible_count + noise_count + 1) < 0.35:
        return True

    return False


def _try_tesseract(img: Image.Image, lang: str = "eng") -> Optional[str]:
    try:
        import pytesseract
        cmd = os.getenv("TESSERACT_CMD")
        if cmd and os.path.exists(cmd):
            pytesseract.pytesseract.tesseract_cmd = cmd
        tessdata = os.getenv("TESSDATA_PREFIX")
        if tessdata:
            os.environ["TESSDATA_PREFIX"] = tessdata

        processed = _preprocess_for_ocr(img, lang=lang)

        is_kannada = "kan" in lang

        # PSM 6: Uniform block of text (optimal for tabular restaurant menus)
        # PSM 4: Single column of variable text sizes
        # PSM 3: Fully automatic page segmentation
        for psm in [6, 4, 3]:
            config = f"--oem 1 --psm {psm}"
            raw_text = pytesseract.image_to_string(processed, lang=lang, config=config)
            cleaned = _clean_menu_ocr_text(raw_text)
            if cleaned and not is_ocr_text_corrupted(cleaned):
                return cleaned

        if is_kannada:
            config_sparse = "--oem 1 --psm 11"
            raw_sparse = pytesseract.image_to_string(processed, lang=lang, config=config_sparse)
            cleaned_sparse = _clean_menu_ocr_text(raw_sparse)
            if cleaned_sparse and not is_ocr_text_corrupted(cleaned_sparse):
                logger.debug("PSM 11 (sparse) recovered text.")
                return cleaned_sparse

        # Fallback to any cleaned text if available
        if cleaned:
            return cleaned

        return None
    except pytesseract.TesseractNotFoundError:
        logger.info("Tesseract binary not found; skipping pytesseract.")
        return None
    except Exception as exc:
        logger.warning("pytesseract error: %s", exc)
        return None

def _load_trocr():
    global _trocr_processor, _trocr_model
    if _trocr_processor is None:
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        logger.info("Loading TrOCR model (first call — may take a moment)...")
        _trocr_processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-printed")
        _trocr_model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-printed")
        logger.info("TrOCR loaded.")
    return _trocr_processor, _trocr_model

def _try_trocr(img: Image.Image) -> Optional[str]:
    if not is_trocr_available():
        return None
    try:
        import torch
        processor, model = _load_trocr()
        pixel_values = processor(images=img, return_tensors="pt").pixel_values
        with torch.no_grad():
            generated_ids = model.generate(pixel_values)
        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return text.strip() if text.strip() else None
    except Exception as exc:
        logger.warning("TrOCR error: %s", exc)
        return None

def extract_text_from_image(
    image_bytes: bytes,
    filename: str,
    lang: str = "eng",
    use_trocr: bool = True,
) -> dict:
    err = _validate_image(image_bytes, filename)
    if err:
        return {"text": None, "engine": None, "lang": lang, "error": err}

    norm_lang = normalize_ocr_lang(lang)

    gvision_text = _try_google_vision(image_bytes, lang=norm_lang)
    if gvision_text:
        return {
            "text": gvision_text,
            "engine": "google-cloud-vision",
            "lang": norm_lang,
            "error": None,
        }

    if is_tesseract_available():
        avail_langs = get_available_ocr_languages()
        req_parts = norm_lang.split("+")
        missing_parts = [p for p in req_parts if p not in avail_langs]

        if missing_parts:
            if "kan" in missing_parts:
                return {
                    "text": None,
                    "engine": None,
                    "lang": norm_lang,
                    "error": (
                        "Kannada OCR language data ('kan.traineddata') is not installed in the Tesseract tessdata directory. "
                        "Please install 'kan.traineddata' to enable Kannada OCR."
                    ),
                }
            return {
                "text": None,
                "engine": None,
                "lang": norm_lang,
                "error": f"OCR language '{lang}' is not installed in Tesseract (available: {', '.join(avail_langs)}).",
            }

    img = _load_image(image_bytes)
    if img is None:
        return {
            "text": None,
            "engine": None,
            "lang": norm_lang,
            "error": "Image could not be decoded. The file may be corrupt or unreadable.",
        }

    text = _try_tesseract(img, lang=norm_lang)
    if text:
        return {"text": text, "engine": "tesseract", "lang": norm_lang, "error": None}

    if norm_lang in ("kan+eng", "eng+kan") and is_tesseract_available():
        avail_langs = get_available_ocr_languages()
        if "kan" in avail_langs:
            text_kan = _try_tesseract(img, lang="kan")
            if text_kan:
                return {"text": text_kan, "engine": "tesseract (kan-fallback)", "lang": "kan", "error": None}
        if "eng" in avail_langs:
            text_eng = _try_tesseract(img, lang="eng")
            if text_eng:
                return {"text": text_eng, "engine": "tesseract (eng-fallback)", "lang": "eng", "error": None}

    if use_trocr and norm_lang == "eng":
        text = _try_trocr(img)
        if text:
            return {"text": text, "engine": "trocr", "lang": norm_lang, "error": None}

    if not is_tesseract_available() and not (use_trocr and is_trocr_available()):
        error_detail = (
            "OCR engines are unavailable in this environment: Tesseract executable is not installed "
            "on system PATH, and TrOCR model weights ('microsoft/trocr-base-printed') are not cached locally. "
            "Please install Tesseract-OCR or provide offline weights."
        )
    else:
        lang_label = "Kannada" if "kan" in norm_lang else "English"
        error_detail = (
            f"No text could be extracted from this image ({lang_label}). "
            "The image may be blank, too blurry, or contain no readable text."
        )

    return {
        "text": None,
        "engine": None,
        "lang": norm_lang,
        "error": error_detail,
    }