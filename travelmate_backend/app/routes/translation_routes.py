"""
Translation Routes — Phase 6 & Phase 6.2 (Kannada Support)
POST /translate/text  — translate arbitrary text
GET  /translate/languages — list supported languages
POST /translate/ocr   — OCR + translate in one call (English, Kannada, etc.)
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.services.translation_service import translate_text, get_supported_languages, translate_texts_batch
from app.services.ocr_service import extract_text_from_image

router = APIRouter(prefix="/translate", tags=["translation"])


class TranslateRequest(BaseModel):
    text: str
    target_lang: str
    source_lang: str = "auto"


class TranslateResponse(BaseModel):
    translated_text: Optional[str] = None
    source_language: Optional[str] = None
    target_language: str
    provider: Optional[str] = None
    error: Optional[str] = None


class LanguageInfo(BaseModel):
    code: str
    name: str


class OCRTranslateResponse(BaseModel):
    original_text: Optional[str] = None
    translated_text: Optional[str] = None
    source_language: Optional[str] = None
    target_language: str
    ocr_lang: Optional[str] = "eng"
    ocr_engine: Optional[str] = None
    translation_provider: Optional[str] = None
    filename: str
    error: Optional[str] = None


@router.post("/text", response_model=TranslateResponse)
def translate_text_endpoint(payload: TranslateRequest):
    """
    Translate text to a target language.

    - source_lang: ISO 639-1 code or 'auto' for automatic detection.
    - target_lang: ISO 639-1 code (see GET /translate/languages for options).
    - Uses Groq LLM as primary; deep-translator as fallback.
    - Returns error clearly; never returns untranslated text claiming success.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="text cannot be empty")

    result = translate_text(payload.text, payload.target_lang, payload.source_lang)
    return TranslateResponse(**result)


@router.get("/languages", response_model=list[LanguageInfo])
def list_languages():
    """Return all supported language codes and names."""
    return get_supported_languages()


@router.post("/ocr", response_model=OCRTranslateResponse)
async def ocr_and_translate(
    file: UploadFile = File(...),
    target_lang: str = "en",
    ocr_lang: str = Query("eng", description="OCR language: 'eng', 'kan', or 'kan+eng'"),
):
    """
    Upload an image, extract text via OCR (English or Kannada), then translate to target_lang.

    Combined convenience endpoint for the OCR+Translate UI flow.
    """
    if target_lang not in {lang["code"] for lang in get_supported_languages()}:
        raise HTTPException(status_code=400, detail=f"Unsupported target_lang '{target_lang}'")

    image_bytes = await file.read()
    filename = file.filename or "upload"

    # Step 1: OCR
    ocr_result = extract_text_from_image(image_bytes, filename, lang=ocr_lang)
    original_text = ocr_result.get("text")
    ocr_engine = ocr_result.get("engine")
    actual_ocr_lang = ocr_result.get("lang", ocr_lang)
    ocr_error = ocr_result.get("error")

    if not original_text:
        return OCRTranslateResponse(
            original_text=None,
            translated_text=None,
            source_language=None,
            target_language=target_lang,
            ocr_lang=actual_ocr_lang,
            ocr_engine=ocr_engine,
            translation_provider=None,
            filename=filename,
            error=ocr_error or "OCR produced no text.",
        )

    # Step 2: Translate (hint source_lang if ocr_lang is kn)
    source_hint = "kn" if "kan" in actual_ocr_lang and "eng" not in actual_ocr_lang else "auto"
    trans_result = translate_text(original_text, target_lang, source_lang=source_hint)

    return OCRTranslateResponse(
        original_text=original_text,
        translated_text=trans_result.get("translated_text"),
        source_language=trans_result.get("source_language"),
        target_language=target_lang,
        ocr_lang=actual_ocr_lang,
        ocr_engine=ocr_engine,
        translation_provider=trans_result.get("provider"),
        filename=filename,
        error=trans_result.get("error"),
    )

class BatchTranslateRequest(BaseModel):
    texts: list[str]
    target_lang: str
    source_lang: str = "auto"


class BatchTranslateItem(BaseModel):
    original_text: str
    translated_text: Optional[str] = None
    provider: Optional[str] = None
    error: Optional[str] = None


class BatchTranslateResponse(BaseModel):
    items: list[BatchTranslateItem]
    target_language: str


@router.post("/batch", response_model=BatchTranslateResponse)
def translate_batch_endpoint(payload: BatchTranslateRequest):
    """
    Batch translate multiple texts to reduce round-trips and avoid rate limits.
    Combines text blocks where supported and handles per-item errors gracefully.
    """
    if not payload.texts:
        return BatchTranslateResponse(items=[], target_language=payload.target_lang)

    results = translate_texts_batch(payload.texts, payload.target_lang, payload.source_lang)
    items = [
        BatchTranslateItem(
            original_text=r.get("original_text", ""),
            translated_text=r.get("translated_text"),
            provider=r.get("provider"),
            error=r.get("error"),
        )
        for r in results
    ]
    return BatchTranslateResponse(items=items, target_language=payload.target_lang)

