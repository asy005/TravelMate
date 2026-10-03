# Simple ML scaffold for personalization (train and predict)
from typing import Dict, List

class MLEngine:
    def __init__(self):
        # load persisted model or set up training pipeline
        self.model = None

    def train(self, data):
        # train a recommender/ranker
        self.model = "trained"
        return {"status": "trained"}

    def recommend(self, user_id: int, top_k: int = 10) -> List[Dict]:
        # return dummy recommendations
        return [{"destination_id": 1, "score": 0.9}]
