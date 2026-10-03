import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestClassifier

TRAIN_FILE = "ml_train.csv"
MODEL_FILE = "travelmate_recommender_final.pkl"

RANDOM_STATE = 42

train_df = pd.read_csv(TRAIN_FILE)

TARGET = "interaction_target"

ID_COLUMNS = [
    "user_id",
    "destination_id",
]

FEATURES = [
    "age",
    "travel_style",
    "budget",
    "preferred_category",
    "preferred_season",

    "category_match",
    "budget_difference",
    "season_match",

    "hotel_price_to_budget",
    "hotel_rating_available",

    "average_budget",
    "ideal_duration",

    "avg_hotel_price",
    "min_hotel_price",
    "max_hotel_price",
    "avg_hotel_rating",

    "avg_package_price",
    "avg_package_days",
    "avg_package_nights",

    "avg_restaurant_rating",
    "avg_restaurant_price_level",

    "avg_attraction_rating",

    "has_weather_data",
]

X = train_df[FEATURES].copy()
y = train_df[TARGET]

categorical_features = X.select_dtypes(
    include=["object"]
).columns.tolist()

numeric_features = X.select_dtypes(
    exclude=["object"]
).columns.tolist()

print("====================================")
print("FINAL TRAVELMATE MODEL")
print("====================================")

print("Training rows:", len(X))
print("Features:", len(FEATURES))
print("Numerical features:", len(numeric_features))
print("Categorical features:", len(categorical_features))

numeric_pipeline = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="median")
        )
    ]
)

categorical_pipeline = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(
                strategy="most_frequent"
            )
        ),
        (
            "encoder",
            OneHotEncoder(
                handle_unknown="ignore"
            )
        ),
    ]
)

preprocessor = ColumnTransformer(
    transformers=[
        (
            "numeric",
            numeric_pipeline,
            numeric_features
        ),
        (
            "categorical",
            categorical_pipeline,
            categorical_features
        ),
    ]
)

model = RandomForestClassifier(
    n_estimators=300,
    max_depth=12,
    min_samples_leaf=3,
    class_weight="balanced",
    random_state=RANDOM_STATE,
    n_jobs=-1,
)

pipeline = Pipeline(
    steps=[
        (
            "preprocessing",
            preprocessor
        ),
        (
            "model",
            model
        ),
    ]
)

print("\nTraining final model...")

pipeline.fit(
    X,
    y
)

print("Training complete.")

joblib.dump(
    pipeline,
    MODEL_FILE
)

print("\nSaved:")
print(MODEL_FILE)