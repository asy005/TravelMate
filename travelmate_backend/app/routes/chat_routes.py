# app/routes/chat_routes.py
from fastapi import APIRouter
import os, requests, json

router = APIRouter(prefix="/chat", tags=["chat"])
HF = os.getenv("HUGGINGFACEHUB_API_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

@router.post("/bot")
def chat_bot(message: dict):
    # message: {"prompt": "User input"} from frontend
    prompt = message.get("prompt", "")
    if not prompt:
        return {"error":"empty prompt"}

    # prefer Hugging Face inference
    if HF:
        url = "https://api-inference.huggingface.co/models/tiiuae/falcon-7b-instruct"
        headers = {"Authorization": f"Bearer {HF}"}
        payload = {"inputs": prompt, "parameters": {"max_new_tokens": 200, "temperature":0.2}}
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            # many HF text models return list/dict with generated_text
            if isinstance(data, list) and "generated_text" in data[0]:
                return {"reply": data[0]["generated_text"]}
            if isinstance(data, dict) and "generated_text" in data:
                return {"reply": data["generated_text"]}
            return {"reply": json.dumps(data)}
        else:
            return {"error": f"HF {r.status_code}: {r.text}"}

    # fallback: echo + safe message
    return {"reply": f"I couldn't find an LLM key — you said: {prompt}"}
