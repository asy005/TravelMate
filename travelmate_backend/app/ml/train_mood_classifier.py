# app/ml/train_mood_classifier.py
import os
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# --- tiny example dataset (expand it for better results) ---
data = [
    ("I want to relax and read at the beach", "Relaxing"),
    ("I want a quiet place to meditate and unwind", "Relaxing"),
    ("I want extreme water sports and hiking", "Adventure"),
    ("Looking for hiking trails and mountain treks", "Adventure"),
    ("Surprise getaway for my partner, candlelight dinners", "Romantic"),
    ("Planning a romantic trip with dinners and sunsets", "Romantic"),
    ("Show me budget friendly local spots", "Neutral"),
    ("I want cheap hostels and street food", "Neutral"),
]

texts, labels = zip(*data)

# Use sentence-transformers embeddings
embed_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

X = embed_model.encode(list(texts), convert_to_numpy=True)
y = list(labels)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

clf = LogisticRegression(max_iter=1000)
clf.fit(X_train, y_train)

pred = clf.predict(X_test)
print(classification_report(y_test, pred))

# Save models
joblib.dump(clf, os.path.join(MODEL_DIR, "mood_clf.joblib"))
# Optionally save encoder separately (we just re-init it in runtime)
print("Saved mood classifier to", MODEL_DIR)
