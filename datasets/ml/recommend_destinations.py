import pandas as pd
import joblib
from recommendation_features import (
    build_user_destination_features,
)

DESTINATION_FILE = "destination_features.csv"
MODEL_FILE = "travelmate_recommender_final.pkl"

model = joblib.load(
    MODEL_FILE
)

destinations = pd.read_csv(
    DESTINATION_FILE
)

def recommend(
    user_profile,
    top_k=5
):
    enriched_df, features = (
        build_user_destination_features(
            user_profile,
            destinations
        )
    )
    scores = model.predict_proba(
        features
    )[:, 1]

    enriched_df[
        "recommendation_score"
    ] = scores
    ranked = enriched_df.sort_values(
        "recommendation_score",
        ascending=False
    )

    return ranked.head(
        top_k
    )

if __name__ == "__main__":

    user = {
        "age": 22,
        "travel_style": "Solo",
        "budget": "Medium",
        "preferred_category": "Hill Station",
        "preferred_season": "Winter",
    }

    recommendations = recommend(
        user,
        top_k=10
    )

    print("\n====================================")
    print("TRAVELMATE RECOMMENDATIONS")
    print("====================================")

    columns = [
        "destination_id",
        "destination_name",
        "state",
        "city",
        "category",
        "average_budget",
        "ideal_duration",
        "recommendation_score",
    ]

    print(
        recommendations[
            columns
        ].to_string(
            index=False
        )
    )