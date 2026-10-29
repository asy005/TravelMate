import json
import requests
from typing import List, Dict, Any, Optional
from app.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

class LLMGatewayError(Exception):
    """Raised when an LLM request fails or returns an invalid response."""

def _provider_config() -> Dict[str, Any]:
    provider = (settings.LLM_PROVIDER or "groq").strip().lower()

    if provider == "openai":
        return {
            "url": OPENAI_URL,
            "api_key": settings.OPENAI_API_KEY,
            "model": settings.OPENAI_MODEL,
        }

    if provider == "groq":
        return {
            "url": GROQ_URL,
            "api_key": settings.GROQ_API_KEY,
            "model": settings.GROQ_MODEL,
        }

    raise LLMGatewayError(
        f"Unsupported LLM_PROVIDER '{provider}'. Use 'groq' or 'openai'."
    )

def chat_completion(
    messages: List[Dict[str, str]],
    json_mode: bool = False,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    model: Optional[str] = None,
) -> str:
    cfg = _provider_config()
    chosen_model = model or cfg["model"]

    if not cfg["api_key"]:
        raise LLMGatewayError(
            f"No API key configured for LLM_PROVIDER="
            f"'{settings.LLM_PROVIDER}'. Check your backend .env file."
        )

    if not chosen_model:
        raise LLMGatewayError(
            f"No model configured for LLM_PROVIDER="
            f"'{settings.LLM_PROVIDER}'. Check your backend settings."
        )

    payload: Dict[str, Any] = {
        "model": chosen_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(
            cfg["url"],
            headers=headers,
            json=payload,
            timeout=45,
        )
        response.raise_for_status()

        data = response.json()
        choices = data.get("choices", [])

        if not choices:
            raise LLMGatewayError(
                "The LLM provider returned no completion choices."
            )

        message = choices[0].get("message", {})
        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise LLMGatewayError(
                "The LLM provider returned an empty response."
            )

        if json_mode:
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                raise LLMGatewayError(
                    f"The LLM provider returned invalid JSON: {exc}"
                ) from exc

            if not isinstance(parsed, dict):
                raise LLMGatewayError(
                    "The LLM JSON response must be an object."
                )

        return content

    except requests.exceptions.Timeout as exc:
        raise LLMGatewayError(
            "The LLM request timed out. Please try again."
        ) from exc

    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"

        if exc.response is not None:
            try:
                error_data = exc.response.json()
                detail = str(error_data.get("error", {}).get("message", ""))
            except (ValueError, AttributeError):
                detail = ""

        message = f"LLM provider returned HTTP {status}."
        if detail:
            message += f" Provider detail: {detail[:300]}"

        raise LLMGatewayError(message) from exc

    except requests.exceptions.RequestException as exc:
        raise LLMGatewayError(
            f"Could not connect to the LLM provider: {exc}"
        ) from exc

    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMGatewayError(
            f"Unexpected LLM response format: {exc}"
        ) from exc