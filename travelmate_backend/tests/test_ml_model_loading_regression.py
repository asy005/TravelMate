from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest

from app.services import ml_engine as ml_mod
from app.services.ml_engine import MLEngine, validate_ml_artifacts


def test_ml_engine_init_is_lazy():
    """MLEngine initialization should be lazy — artifacts are not loaded in __init__."""
    engine = MLEngine()
    assert engine.model is None
    assert engine.destinations is None
    assert engine._feature_names is None


def test_model_not_deserialized_twice_on_first_use():
    """Startup validation loads/caches the model; first recommendation use reuses it without re-loading."""
    mock_model = MagicMock()
    mock_model.predict_proba.return_value = np.array([[0.1, 0.9]])
    mock_model.classes_ = [0, 1]
    mock_model.feature_names_in_ = ["category_match"]

    with patch("joblib.load", return_value=mock_model) as mock_joblib_load:
        # Reset module-level cache for this test
        old_cached_model = ml_mod._cached_model
        old_cached_dest = ml_mod._cached_destinations
        old_cached_feat = ml_mod._cached_feature_names
        try:
            ml_mod._cached_model = None
            ml_mod._cached_destinations = None
            ml_mod._cached_feature_names = None

            # 1. Startup validation (simulates application boot)
            valid = validate_ml_artifacts()
            assert valid is True
            assert mock_joblib_load.call_count == 1
            assert ml_mod._cached_model is mock_model

            # 2. First recommendation use via MLEngine instance
            engine = MLEngine()
            assert engine.model is None  # lazy before use

            dummy_dest = pd.DataFrame([{
                "destination_id": "D1",
                "destination_name": "Goa",
                "category": "Beach",
                "average_budget": 20000,
                "best_season": "Winter",
            }])
            with patch("pandas.read_csv", return_value=dummy_dest):
                engine._load_artifacts()

            # The model should be the cached model, and joblib.load must NOT be called again
            assert engine.model is mock_model
            assert mock_joblib_load.call_count == 1  # STILL 1, not 2!

            # 3. Subsequent recommendation or _load_artifacts call should also reuse cache
            engine._load_artifacts()
            assert mock_joblib_load.call_count == 1
        finally:
            ml_mod._cached_model = old_cached_model
            ml_mod._cached_destinations = old_cached_dest
            ml_mod._cached_feature_names = old_cached_feat


def test_recommend_profile_works_with_cached_model():
    """Recommendations succeed and produce correct ranking using the cached model."""
    mock_model = MagicMock()
    # 2 destinations
    mock_model.predict_proba.return_value = np.array([
        [0.2, 0.8],  # Dest 1
        [0.6, 0.4],  # Dest 2
    ])
    mock_model.classes_ = [0, 1]

    engine = MLEngine()
    engine.model = mock_model
    engine.destinations = pd.DataFrame([
        {
            "destination_id": "D1", "destination_name": "Goa",
            "state": "Goa", "city": "Panaji", "category": "Beach",
            "average_budget": 15000, "best_season": "Winter",
        },
        {
            "destination_id": "D2", "destination_name": "Gokarna",
            "state": "Karnataka", "city": "Gokarna", "category": "Beach",
            "average_budget": 12000, "best_season": "Winter",
        },
    ])

    profile = {
        "age": 28,
        "travel_style": "Relaxing",
        "budget": "Medium",
        "preferred_category": "Beach",
        "preferred_season": "Winter",
    }

    results = engine.recommend_profile(profile, top_k=2)
    assert len(results) == 2
    assert results[0]["destination_name"] == "Goa"
    assert results[0]["match_label"] == "Top Match"
    assert results[1]["destination_name"] == "Gokarna"
    assert results[1]["match_label"] == "Great Match"


def test_missing_model_file_raises_filenotfound():
    """Missing model artifact raises FileNotFoundError with helpful error."""
    old_cached = ml_mod._cached_model
    fake_path = MagicMock()
    fake_path.is_file.return_value = False

    try:
        ml_mod._cached_model = None
        engine = MLEngine()
        with patch.object(ml_mod, "MODEL_PATH", fake_path):
            with pytest.raises(FileNotFoundError, match="Model not found"):
                engine._load_artifacts()
    finally:
        ml_mod._cached_model = old_cached
