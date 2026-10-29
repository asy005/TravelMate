"""
OCR Routes — Phase 6 & Phase 6.2 (Kannada Support)
POST /ocr/extract  — extract text from uploaded image (English, Kannada, or bilingual)
GET  /ocr/languages — list supported OCR languages
"""
from fastapi import APIRouter, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional, List

from app.services.ocr_service import (
    extract_text_from_image,
    get_available_ocr_languages,
    SUPPORTED_OCR_LANGUAGES,
)

router = APIRouter(prefix="/ocr", tags=["ocr"])


class OCRResponse(BaseModel):
    text: Optional[str] = None
    engine: Optional[str] = None
    lang: Optional[str] = "eng"
    filename: str
    file_size_kb: float
    error: Optional[str] = None


class OCRLanguageInfo(BaseModel):
    code: str
    name: str
    installed: bool


@router.get("/languages", response_model=List[OCRLanguageInfo])
def list_ocr_languages():
    """Return available OCR languages and installation status in Tesseract."""
    installed = set(get_available_ocr_languages())
    results = [
        OCRLanguageInfo(
            code="eng",
            name="English",
            installed="eng" in installed,
        ),
        OCRLanguageInfo(
            code="kan",
            name="Kannada (ಕನ್ನಡ)",
            installed="kan" in installed,
        ),
        OCRLanguageInfo(
            code="kan+eng",
            name="Kannada + English (ಮಿಶ್ರಿತ)",
            installed="kan" in installed and "eng" in installed,
        ),
    ]
    return results


@router.post("/extract", response_model=OCRResponse)
async def extract_text(
    file: UploadFile = File(...),
    lang: str = Query("eng", description="OCR language ('eng' for English, 'kan' for Kannada, 'kan+eng' for bilingual)"),
):
    """
    Upload an image (jpg/jpeg/png/webp/bmp) and extract text.

    - Supports English, Kannada (ಕನ್ನಡ), and bilingual documents.
    - Max file size: 10 MB.
    - Returns extracted text, language, and the OCR engine used.
    """
    image_bytes = await file.read()
    filename = file.filename or "upload"

    result = extract_text_from_image(image_bytes, filename, lang=lang)

    return OCRResponse(
        text=result["text"],
        engine=result["engine"],
        lang=result.get("lang", lang),
        filename=filename,
        file_size_kb=round(len(image_bytes) / 1024, 2),
        error=result["error"],
    )
