from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from recommendation_features import (
    MODEL_FEATURES,
    BUDGET_VALUES,
)
BASE_DIR = Path(__file__).resolve().parent
TEST_FILE = BASE_DIR / "ml_test.csv"
MODEL_FILE = BASE_DIR / "travelmate_recommender_final.pkl"
OUTPUT_FILE = (
    BASE_DIR / "experiments" / "preference_ranking_evaluation.csv"
)

TOP_K = 5
def add_preference_scores(df):
    """Calculate ranking signals without changing the trained ML features."""
    result = df.copy()
    result["category_signal"] = (
        pd.to_numeric(result["category_match"], errors="coerce")
        .fillna(0)
        .clip(0, 1)
    )

    result["season_signal"] = (
        pd.to_numeric(result["season_match"], errors="coerce")
        .fillna(0)
        .clip(0, 1)
    )

    user_budget = (
        result["budget"]
        .map(BUDGET_VALUES)
        .fillna(BUDGET_VALUES["Medium"])
    )

    destination_budget = pd.to_numeric(
        result["average_budget"],
        errors="coerce",
    )

    result["budget_signal"] = (
        1
        - (
            (destination_budget - user_budget).clip(lower=0)
            / user_budget
        )
    ).clip(0, 1).fillna(0.5)

    return result

def ranking_metrics(group, score_column, k=5):
    """Evaluate a ranked candidate list for one user."""
    ranked = group.sort_values(
        score_column,
        ascending=False,
    )

    effective_k = min(k, len(ranked))
    top = ranked.head(effective_k)

    relevance = ranked["interaction_target"].astype(int).to_numpy()
    top_relevance = top["interaction_target"].astype(int).to_numpy()

    total_positives = int(relevance.sum())
    hits = int(top_relevance.sum())

    precision = hits / effective_k if effective_k else 0.0
    recall = hits / total_positives if total_positives else np.nan
    hit_rate = float(hits > 0)

    discounts = 1 / np.log2(np.arange(2, effective_k + 2))
    dcg = float((top_relevance * discounts).sum())

    ideal_relevance = np.sort(relevance)[::-1][:effective_k]
    ideal_dcg = float((ideal_relevance * discounts).sum())

    ndcg = dcg / ideal_dcg if ideal_dcg else np.nan

    return {
        f"Precision@{k}": precision,
        f"Recall@{k}": recall,
        f"HitRate@{k}": hit_rate,
        f"NDCG@{k}": ndcg,
        f"CategoryMatch@{k}": float(top["category_signal"].mean()),
        f"SeasonMatch@{k}": float(top["season_signal"].mean()),
        f"BudgetCompatibility@{k}": float(top["budget_signal"].mean()),
    }

def main():
    test = pd.read_csv(
        TEST_FILE,
        dtype={"user_id": str, "destination_id": str},
    )

    model = joblib.load(MODEL_FILE)

    missing = sorted(set(MODEL_FEATURES) - set(test.columns))
    if missing:
        raise ValueError(f"Missing model features in test data: {missing}")

    if test["interaction_target"].isna().any():
        raise ValueError("Test data contains missing interaction targets.")

    if not set(test["interaction_target"].unique()).issubset({0, 1}):
        raise ValueError("interaction_target must contain only 0 and 1.")

    features = test[MODEL_FEATURES].copy()

    test["ml_score"] = model.predict_proba(features)[:, 1]
    test = add_preference_scores(test)

    strategies = {
        "ML only": (1.00, 0.00, 0.00, 0.00),
        "Current 70/15/10/5": (0.70, 0.15, 0.10, 0.05),
        "Stronger preferences 55/25/15/5": (
            0.55, 0.25, 0.15, 0.05
        ),
    }

    for name, weights in strategies.items():
        ml_w, category_w, season_w, budget_w = weights

        test[f"score_{name}"] = (
            ml_w * test["ml_score"]
            + category_w * test["category_signal"]
            + season_w * test["season_signal"]
            + budget_w * test["budget_signal"]
        )

    results = []

    for strategy in strategies:
        score_column = f"score_{strategy}"

        per_user = []
        for user_id, group in test.groupby("user_id"):
            metrics = ranking_metrics(group, score_column, TOP_K)
            metrics["user_id"] = user_id
            per_user.append(metrics)

        user_metrics = pd.DataFrame(per_user)

        summary = {
            "strategy": strategy,
            "users_evaluated": len(user_metrics),
            "candidate_rows": len(test),
        }

        metric_columns = [
            f"Precision@{TOP_K}",
            f"Recall@{TOP_K}",
            f"HitRate@{TOP_K}",
            f"NDCG@{TOP_K}",
            f"CategoryMatch@{TOP_K}",
            f"SeasonMatch@{TOP_K}",
            f"BudgetCompatibility@{TOP_K}",
        ]

        for metric in metric_columns:
            summary[metric] = user_metrics[metric].mean()

        results.append(summary)

    summary_df = pd.DataFrame(results)
    summary_df.to_csv(OUTPUT_FILE, index=False)

    print("=" * 78)
    print("TRAVELMATE — PREFERENCE RANKING EVALUATION")
    print("=" * 78)
    print(f"Test rows: {len(test)}")
    print(f"Unique users: {test['user_id'].nunique()}")
    print(f"Top-K evaluated: {TOP_K}")
    print()
    print(
        summary_df.to_string(
            index=False,
            float_format=lambda value: f"{value:.4f}",
        )
    )
    print()
    print(f"Saved results to: {OUTPUT_FILE}")
    print()
    print(
        "Caution: interaction metrics use sampled candidates. "
        "Unobserved destinations are not necessarily disliked."
    )
if __name__ == "__main__":
    main()