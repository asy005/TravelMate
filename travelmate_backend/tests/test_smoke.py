"""
M0 smoke/regression suite.

These tests intentionally avoid requiring a live Postgres connection so they
can run in any environment (including CI without a database). They target the
specific defects fixed in M0. Fuller integration tests that exercise the
database (favorites CRUD, auth signup/login, /travel/plan) belong in a
follow-up milestone once a test-database fixture is introduced -- adding one
here would be scope creep beyond M0's "fix, don't rewrite" mandate.
"""
import pytest


def test_app_imports_without_error():
    """
    Regression test for the requirements.txt / import-chain issues found in
    the audit (missing langchain/torch/etc. dependencies, and the deleted
    duplicate model files). If any of app.main's imports are broken, this
    fails at collection time.
    """
    import app.main  # noqa: F401
    assert app.main.app is not None


def test_mood_classify_no_recursion():
    """
    Regression test for the mood_routes.py self-recursion bug
    (classify_mood was being reassigned to classify_mood_route, which called
    classify_mood, causing infinite recursion / RecursionError).
    """
    from app.routes.mood_routes import classify_mood

    result = classify_mood("I feel adventurous and want to explore")
    assert result == {"mood": "Adventure"}

    # Call it a second time to make sure nothing was mutated/reassigned.
    result_again = classify_mood("I am so tired and sad")
    assert result_again == {"mood": "Relaxing"}


def test_only_one_user_model_is_importable():
    """
    Regression test for the triple-duplicate User model bug. Confirms the
    dead model files were actually removed and only one User model exists.
    """
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.models.auth_models")

    from app.models.user import User
    assert User.__tablename__ == "users"


def test_favorite_model_has_user_id_not_user_email():
    """
    Regression test for the favorites bug where the route queried a
    non-existent `Favorite.user_email` column.
    """
    from app.models.favorites import Favorite

    assert hasattr(Favorite, "user_id")
    assert not hasattr(Favorite, "user_email")


def test_destination_model_matches_plan_routes_usage():
    """
    Regression test for the Destination schema drift between the model,
    plan_routes.py, and the seed script.
    """
    from app.models.destination import Destination

    for field in ("name", "country", "description", "lat", "lon", "tags", "thumbnail_url", "avg_rating"):
        assert hasattr(Destination, field), f"Destination model missing expected field: {field}"

    # These field names should NOT exist -- if they do, plan_routes.py's old
    # (broken) assumptions may have crept back in.
    for stale_field in ("title", "climate", "safety_rating", "best_season", "image_url"):
        assert not hasattr(Destination, stale_field), (
            f"Unexpected field '{stale_field}' on Destination -- "
            "plan_routes.py and the seed script assume the model does NOT have this."
        )


def test_secrets_are_not_hardcoded_in_auth_utils():
    """
    Regression test for the hardcoded JWT secret bug -- confirms
    auth_utils.SECRET_KEY is sourced from Settings, not a literal string.
    """
    from app.services import auth_utils
    from app.config import settings

    assert auth_utils.SECRET_KEY == settings.SECRET_KEY
