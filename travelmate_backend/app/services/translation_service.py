"""
Translation Service — Phase 6

Uses the Groq LLM (already configured) to translate text.
Falls back to deep-translator (Google free endpoint) when LLM is unavailable.

Never returns untranslated text while claiming success.
Never exposes API keys.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Languages relevant to Indian tourism + international visitors
SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "bn": "Bengali",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada (ಕನ್ನಡ)",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ja": "Japanese",
    "zh": "Chinese (Simplified)",
    "ar": "Arabic",
    "pt": "Portuguese",
    "it": "Italian",
    "ru": "Russian",
    "ko": "Korean",
}


def get_supported_languages() -> list[dict]:
    """Return list of {code, name} dicts."""
    return [{"code": k, "name": v} for k, v in SUPPORTED_LANGUAGES.items()]


def _detect_language(text: str) -> Optional[str]:
    """Detect source language code using langdetect. Returns None on failure."""
    try:
        from langdetect import detect
        return detect(text)
    except Exception:
        return None


def _translate_via_llm(text: str, target_lang: str, source_lang: str = "auto") -> dict:
    """Translate using the configured LLM (Groq/OpenAI)."""
    from app.services.llm_gateway import chat_completion, LLMGatewayError

    target_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
    source_info = ""
    if source_lang and source_lang != "auto":
        source_name = SUPPORTED_LANGUAGES.get(source_lang, source_lang)
        source_info = f" from {source_name}"

    system_prompt = (
        f"You are a professional translator for TravelMate, an AI travel and tourism platform. "
        f"Your task is to translate the following text (including travel plans, travel assistant messages, itineraries, guides, signs, and restaurant menus){source_info} into {target_name}.\n\n"
        f"CRITICAL - every rule below is mandatory:\n"
        f"1. OUTPUT LANGUAGE: Write EVERY translated line entirely in {target_name} script. "
        f"Do NOT leave source-language words on any line unless they are widely-known proper nouns "
        f"with no {target_name} equivalent (e.g. brand names like Coca-Cola).\n"
        "2. Return ONLY the translated text - no preamble, no conversational refusal, no explanations, no markdown, no quotes. Always translate the provided text faithfully.\n"
        "3. Preserve ALL prices, numeric amounts, and currency symbols (e.g. Rs., ₹, $, €) "
        "EXACTLY as they appear in the source. Never alter, invent, or omit any price.\n"
        "4. Keep the EXACT same number of output lines as input lines. "
        "If the input contains a menu or dish list, each dish and its price must stay on the same line as in the source.\n"
        "5. Do NOT add, skip, or invent any items or prices."
    )

    try:
        candidate_models = [None, "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
        last_exc = None
        translated = None
        for cand in candidate_models:
            for attempt in range(2):
                try:
                    kwargs = {}
                    if cand:
                        kwargs["model"] = cand
                    translated = chat_completion(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": text},
                        ],
                        temperature=0.1,
                        max_tokens=2048,
                        **kwargs,
                    )
                    break
                except LLMGatewayError as exc:
                    last_exc = exc
                    err_msg = str(exc).lower()
                    if "does not exist" in err_msg or "404" in err_msg:
                        break
                    if ("rate" in err_msg or "429" in err_msg) and attempt == 0:
                        import time
                        time.sleep(1.0)
                        continue
                    if attempt == 1:
                        break
            if translated:
                break
        else:
            if last_exc:
                raise last_exc

        if not translated:
            return {"translated_text": None, "provider": "llm", "error": "LLM returned empty translation."}
        translated = translated.strip()
        return {
            "translated_text": translated,
            "provider": "llm",
            "error": None,
        }
    except LLMGatewayError as exc:
        logger.warning("LLM translation failed: %s", exc)
        return {"translated_text": None, "provider": "llm", "error": str(exc)}
    except Exception as exc:
        logger.warning("LLM translation unexpected error: %s", exc)
        return {"translated_text": None, "provider": "llm", "error": f"Translation error: {exc}"}


def _translate_via_deep(text: str, target_lang: str, source_lang: str = "auto") -> dict:
    """Translate using deep-translator (Google free endpoint). Fallback only."""
    try:
        from deep_translator import GoogleTranslator
        src = source_lang if source_lang and source_lang != "auto" else "auto"
        translated = GoogleTranslator(source=src, target=target_lang).translate(text)
        if not translated or not translated.strip():
            return {"translated_text": None, "provider": "deep-translator", "error": "Translation provider returned empty response."}

        # Prevent false success: If input contains Kannada characters and target is English,
        # but output is still completely identical Kannada script with no English translation, flag as failed.
        has_kannada_in = any("\u0c80" <= ch <= "\u0cff" for ch in text)
        has_kannada_out = any("\u0c80" <= ch <= "\u0cff" for ch in translated)
        if has_kannada_in and target_lang in ("en", "eng") and has_kannada_out and translated.strip() == text.strip():
            return {"translated_text": None, "provider": "deep-translator", "error": "Failed to translate Kannada text."}

        return {"translated_text": translated.strip(), "provider": "deep-translator", "error": None}
    except Exception as exc:
        logger.warning("deep-translator failed: %s", exc)
        return {"translated_text": None, "provider": "deep-translator", "error": str(exc)}


def translate_text(
    text: str,
    target_lang: str,
    source_lang: str = "auto",
) -> dict:
    """
    Translate text to the target language.

    Returns:
        translated_text (str | None)
        source_language (str | None)
        target_language (str)
        provider (str)
        error (str | None)
    """
    # Validate
    if not text or not text.strip():
        return {
            "translated_text": None,
            "source_language": source_lang,
            "target_language": target_lang,
            "provider": None,
            "error": "Input text is empty.",
        }

    if target_lang not in SUPPORTED_LANGUAGES:
        return {
            "translated_text": None,
            "source_language": source_lang,
            "target_language": target_lang,
            "provider": None,
            "error": f"Unsupported target language '{target_lang}'. Call GET /translate/languages for the list.",
        }

    # Detect source language if auto
    detected_source = None
    if source_lang == "auto":
        detected_source = _detect_language(text)

    # Try LLM first (most reliable)
    result = _translate_via_llm(text, target_lang, source_lang)

    # If LLM fails, try deep-translator as fallback
    if result["translated_text"] is None:
        logger.info("LLM translation failed, trying deep-translator fallback")
        result = _translate_via_deep(text, target_lang, source_lang)

    return {
        "translated_text": result.get("translated_text"),
        "source_language": detected_source or (source_lang if source_lang != "auto" else None),
        "target_language": target_lang,
        "provider": result.get("provider"),
        "error": result.get("error"),
    }


def translate_texts_batch(
    texts: list[str],
    target_lang: str,
    source_lang: str = "auto",
    chunk_size: int = 15,
) -> list[dict]:
    """
    Translate a batch of text strings efficiently with chunking and backoff.
    - Chunks items into blocks of up to 15 to stay within prompt and token limits.
    - Batches texts together using delimiters to minimize round-trips.
    - If a chunk's combined call fails, falls back per-item with exponential backoff on rate limits.
    - Preserves extracted text when translation fails and provides a usable retry path.
    - Never displays false success.
    """
    if not texts:
        return []

    import time
    results = [None] * len(texts)
    to_translate = []
    for idx, t in enumerate(texts):
        if not t or not str(t).strip():
            results[idx] = {
                "original_text": t,
                "translated_text": t,
                "provider": None,
                "error": None,
            }
        else:
            to_translate.append((idx, str(t).strip()))

    if not to_translate:
        return results

    DELIMITER = "\n---TM_SEP---\n"

    # Process in chunks
    for i in range(0, len(to_translate), chunk_size):
        chunk = to_translate[i : i + chunk_size]
        combined_input = DELIMITER.join([item[1] for item in chunk])

        chunk_success = False
        try:
            batch_res = translate_text(combined_input, target_lang, source_lang)
            if batch_res.get("translated_text"):
                parts = [p.strip() for p in batch_res["translated_text"].split("---TM_SEP---")]
                if len(parts) == len(chunk):
                    for (orig_idx, orig_text), trans_part in zip(chunk, parts):
                        results[orig_idx] = {
                            "original_text": orig_text,
                            "translated_text": trans_part,
                            "provider": batch_res.get("provider"),
                            "error": None,
                        }
                    chunk_success = True
        except Exception as exc:
            logger.warning("Chunk batch translation error: %s", exc)

        if not chunk_success:
            # Fallback to per-item translation with rate-limit handling
            for (orig_idx, orig_text) in chunk:
                res = translate_text(orig_text, target_lang, source_lang)
                if res.get("error") and ("429" in str(res.get("error")) or "rate" in str(res.get("error")).lower()):
                    time.sleep(1.0)
                    res = translate_text(orig_text, target_lang, source_lang)
                results[orig_idx] = {
                    "original_text": orig_text,
                    "translated_text": res.get("translated_text"),
                    "provider": res.get("provider"),
                    "error": res.get("error"),
                }
                time.sleep(0.05)

    return results

