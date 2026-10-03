# app/ml/mood_predictor.py
import os
from sentence_transformers import SentenceTransformer
import joblib
from typing import Dict

BASE = os.path.dirname(__file__)
MODEL_DIR = os.path.join(BASE, "models")
CLF_PATH = os.path.join(MODEL_DIR, "mood_clf.joblib")

# lazy load
_embed_model = None
_clf = None

def _load():
    global _embed_model, _clf
    if _embed_model is None:
        _embed_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    if _clf is None:
        _clf = joblib.load(CLF_PATH)
    return _embed_model, _clf

def predict_text_mood(text: str) -> Dict:
    emb_model, clf = _load()
    vec = emb_model.encode([text], convert_to_numpy=True)
    pred = clf.predict(vec)[0]
    probs = None
    try:
        probs = clf.predict_proba(vec)[0].tolist()
    except:
        probs = None
    return {"mood": pred, "probs": probs}
