# app/services/llm_gateway.py
"""
Provider-agnostic chat-completion gateway.

Groq and OpenAI both expose an OpenAI-compatible /chat/completions wire
format, so swapping providers is a Settings/.env change (LLM_PROVIDER=openai)
rather than a code change. This is the single place any AI feature should go
through for LLM calls — it intentionally does not know about travel, slots,
or conversation state; that logic lives in conversation_engine.py.
"""
import json
import requests
from typing import List, Dict, Optional

from app.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class LLMGatewayError(Exception):
    pass


def _provider_config():
    provider = (settings.LLM_PROVIDER or "groq").lower()
    if provider == "openai":
        return {
            "url": OPENAI_URL,
            "api_key": settings.OPENAI_API_KEY,
            "model": settings.OPENAI_MODEL,
        }
    # default: groq
    return {
        "url": GROQ_URL,
        "api_key": settings.GROQ_API_KEY,
        "model": settings.GROQ_MODEL,
    }


def chat_completion(
    messages: List[Dict[str, str]],
    json_mode: bool = False,
    temperature: float = 0.4,
    max_tokens: int = 1024,
) -> str:
    """
    messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
    json_mode: if True, asks the provider to return valid JSON only
               (used by conversation_engine for structured slot extraction).
    Returns the raw text content of the model's reply.
    Raises LLMGatewayError on failure — callers are expected to catch this
    and fall back to a safe, non-AI response rather than crash the endpoint.
    """
    cfg = _provider_config()

    if not cfg["api_key"]:
        raise LLMGatewayError(
            f"No API key configured for LLM_PROVIDER='{settings.LLM_PROVIDER}'."
        )

    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(cfg["url"], headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        raise LLMGatewayError(f"LLM request failed: {e}")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise LLMGatewayError(f"Unexpected LLM response shape: {e}")
