# app/services/llm_engine.py
import requests
from typing import Optional

class LLMEngine:
    def __init__(self, model_name: str = "phi3", ollama_url: str = "http://localhost:11434/api/generate"):
        self.model_name = model_name
        self.ollama_url = ollama_url

    def generate(self, prompt: str, stream: bool = False, **kwargs) -> str:
        """
        Send a prompt to Ollama and return the model's response.
        """
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": stream,
            **kwargs
        }

        try:
            response = requests.post(self.ollama_url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            # Ollama's API may return different keys depending on version; try common ones:
            return data.get("response") or data.get("text") or data.get("generated_text") or ""
        except requests.exceptions.RequestException as e:
            # Return a clear error string so the API can surface it
            return f"Error communicating with Ollama: {str(e)}"

# Convenience singleton and function so older imports still work:
_default_llm = LLMEngine()

def generate_response(prompt: str, model_name: Optional[str] = None) -> str:
    """
    Simple wrapper used by legacy code. If model_name is provided, creates a temporary LLM engine.
    """
    if model_name:
        engine = LLMEngine(model_name=model_name)
        return engine.generate(prompt)
    return _default_llm.generate(prompt)
