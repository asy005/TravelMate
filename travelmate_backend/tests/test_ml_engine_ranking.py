import numpy as np
import pandas as pd

from app.services.ml_engine import MLEngine


class _FixedModel:
    def predict_proba(self, features):
        # sklearn's second column is the positive-class probability.
        return np.array([
            [0.05, 0.95],  # Bengaluru: highest overall, but wrong category
            [0.20, 0.80],  # Anjuna
            [0.30, 0.70],  # Pondicherry
        ])


def test_model_score_is_authoritative_and_category_filter_precedes_top_k():
    engine = MLEngine()
    engine.model = _FixedModel()
    engine.destinations = pd.DataFrame([
        {
            "destination_id": "D1", "destination_name": "Bengaluru",
            "state": "Karnataka", "city": "Bengaluru", "category": "Urban",
            "average_budget": 2000, "ideal_duration": 2,
        },
        {
            "destination_id": "D2", "destination_name": "Anjuna",
            "state": "Goa", "city": "Anjuna", "category": "Beach",
            "average_budget": 2200, "ideal_duration": 4,
        },
        {
            "destination_id": "D3", "destination_name": "Pondicherry",
            "state": "Puducherry", "city": "Pondicherry", "category": "Beach",
            "average_budget": 2500, "ideal_duration": 3,
        },
    ])

    def build_features(profile, destinations):
        enriched = destinations.copy()
        enriched["category_match"] = (
            enriched["category"] == profile["preferred_category"]
        ).astype(int)
        enriched["season_match"] = 0.0
        return enriched, pd.DataFrame({"test_feature": [1, 2, 3]})

    engine.build_features = build_features
    profile = {
        "age": 30,
        "travel_style": "Relaxing",
        "budget": "Low",
        "preferred_category": "Beach",
        "preferred_season": "Winter",
    }

    results = engine.recommend_profile(
        profile, top_k=2, category_filter="Beach"
    )

    assert [item["destination_name"] for item in results] == [
        "Anjuna", "Pondicherry"
    ]
    assert all(
        item["recommendation_score"] == item["ml_score"]
        for item in results
    )
