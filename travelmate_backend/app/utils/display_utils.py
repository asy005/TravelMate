# app/utils/display_utils.py
import re
from typing import Optional


def clean_display_name(text: Optional[str]) -> str:
    """
    Strips internal demo labels such as '[Demo]', '(Demo)', 'Demo -', etc.
    from user-facing strings while preserving genuine business, package, and hotel names.
    Idempotent and safe with None / empty strings.
    """
    if not text:
        return ""
    cleaned = re.sub(r"^\s*\[demo\]\s*", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*\(demo\)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*demo\s*[:-]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[demo\]\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()
