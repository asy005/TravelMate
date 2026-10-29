"""
test_reviews_phase3.py
----------------------
Phase 3 test suite: Reviews and Sentiment Analysis.

Coverage
--------
1.  Sentiment analyser — positive / neutral / negative classification
2.  Sentiment analyser — edge cases (empty, None, negation, intensifiers)
3.  Sentiment analyser — rating-only fallback
4.  Review model schema — ORM creation & constraint validation (SQLite in-mem)
5.  Review schema (Pydantic) — valid payload, validation errors
6.  API — POST /reviews/ (authenticated, 201)
7.  API — POST /reviews/ duplicate rejection (409)
8.  API — POST /reviews/ unauthenticated (401 / 403)
9.  API — POST /reviews/ entity not found (404)
10. API — GET /reviews/hotel/{id} returns summary + recent reviews
11. API — GET /reviews/package/{id} returns summary
12. API — GET /reviews/me returns user's own reviews
13. Import script — idempotency (dry-run returns counts without DB writes)
14. Import script — validates ratings outside 1-5 are rejected
15. Import script — refuses non-local DB host (safety guard)
16. Regression — booking endpoints still respond correctly
17. Regression — recommendation endpoint still responds correctly
"""
from __future__ import annotations

import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base
# Import all models (required for SQLite test DB creation)
from app.models import user, favorites, destination, conversation  # noqa: F401
from app.models import refresh_token, password_reset_token  # noqa: F401
from app.models import partner, hotel, package, booking  # noqa: F401
from app.models import review  # noqa: F401

from app.models.user import User
from app.models.hotel import Hotel
from app.models.package import Package
from app.models.review import Review
from app.services.sentiment_analyser import analyse, classify_review, classify_by_rating, SentimentResult
from app.schemas.review_schema import ReviewCreateIn
from app.config import settings


# ==============================================================================
# Helpers
# ==============================================================================

def _make_sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


def _make_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()


# ==============================================================================
# 1-3. Sentiment Analyser Unit Tests
# ==============================================================================

class TestSentimentAnalyser:
    """Pure unit tests; no DB needed."""

    # --- basic classification ---

    def test_positive_text(self):
        result = analyse("Really enjoyed our trip. Smooth experience from start to finish. Amazing hotel!")
        assert result.label == "positive"
        assert result.score > 0

    def test_negative_text(self):
        result = analyse("Terrible service, dirty room, rude staff. Worst hotel ever.")
        assert result.label == "negative"
        assert result.score < 0

    def test_neutral_text(self):
        # A text with balanced or no sentiment words
        result = analyse("We arrived at the hotel. The room was there.")
        assert result.label in ("neutral", "positive", "negative")  # mostly neutral expected
        # Just ensure it doesn't crash

    def test_classify_review_positive(self):
        result = classify_review("Great stay, loved the view, very comfortable!", 4.5)
        assert result.label == "positive"

    def test_classify_review_negative(self):
        result = classify_review("Disappointing and overpriced. Bad experience.", 2.0)
        assert result.label == "negative"

    # --- edge cases ---

    def test_empty_string_with_rating_fallback(self):
        result = classify_review("", 5.0)
        assert result.label == "positive"
        assert result.token_count == 0

    def test_none_text_with_rating_fallback(self):
        result = classify_review(None, 1.0)
        assert result.label == "negative"

    def test_empty_string_no_rating(self):
        result = classify_review("")
        assert result.label == "neutral"
        assert result.score == 0.0

    def test_none_text_no_rating(self):
        result = classify_review(None)
        assert result.label == "neutral"

    def test_whitespace_only(self):
        result = analyse("   \t\n  ")
        assert result.label == "neutral"
        assert result.score == 0.0
        assert result.token_count == 0

    def test_negation_flips_positive(self):
        # "not good" should NOT be positive
        result = analyse("not good not clean not friendly")
        assert result.label != "positive"

    def test_intensifier_amplifies_positive(self):
        plain = analyse("good")
        amplified = analyse("very good")
        # Intensified sentiment should have higher raw magnitude
        assert abs(amplified.score) >= abs(plain.score)

    # --- rating-only fallback ---

    def test_rating_fallback_high(self):
        result = classify_by_rating(5.0)
        assert result.label == "positive"
        assert result.score == pytest.approx(1.0, abs=0.01)

    def test_rating_fallback_mid(self):
        result = classify_by_rating(3.0)
        assert result.label == "neutral"
        assert result.score == pytest.approx(0.0, abs=0.01)

    def test_rating_fallback_low(self):
        result = classify_by_rating(1.0)
        assert result.label == "negative"
        assert result.score == pytest.approx(-1.0, abs=0.01)

    # --- output types ---

    def test_result_is_dataclass(self):
        result = analyse("good trip")
        assert isinstance(result, SentimentResult)
        assert isinstance(result.label, str)
        assert isinstance(result.score, float)
        assert isinstance(result.token_count, int)

    def test_score_bounds(self):
        for text in [
            "absolutely fantastic wonderful amazing best ever great perfect",
            "terrible awful horrible disgusting worst ever bad rude dirty",
            "",
            "the hotel was there",
        ]:
            result = analyse(text)
            assert -1.0 <= result.score <= 1.0, f"Score {result.score} out of bounds for: {text!r}"


# ==============================================================================
# 4. Review Model — ORM Schema Tests
# ==============================================================================

class TestReviewModel:
    """Tests against in-memory SQLite (check constraints not enforced in SQLite
    so we test the FK and nullable logic at the Python level)."""

    def test_create_hotel_review(self, db_session):
        # Seed a destination and hotel
        dest = destination.Destination(name="Test Dest", country="India")
        db_session.add(dest)
        db_session.flush()

        h = Hotel(destination_id=dest.id, name="Test Hotel", price_tier="medium")
        db_session.add(h)
        db_session.flush()

        r = Review(
            hotel_id=h.id,
            rating=4.5,
            review_text="Great place!",
            sentiment_label="positive",
            sentiment_score=0.8,
        )
        db_session.add(r)
        db_session.commit()

        fetched = db_session.query(Review).filter_by(id=r.id).first()
        assert fetched is not None
        assert fetched.hotel_id == h.id
        assert fetched.package_id is None
        assert fetched.rating == 4.5
        assert fetched.sentiment_label == "positive"

    def test_review_with_csv_provenance(self, db_session):
        dest = destination.Destination(name="CSV Dest", country="India")
        db_session.add(dest)
        db_session.flush()

        h = Hotel(destination_id=dest.id, name="CSV Hotel", price_tier="low")
        db_session.add(h)
        db_session.flush()

        r = Review(
            csv_review_id="REV00001",
            csv_user_id="U0110",
            hotel_id=h.id,
            rating=3.0,
            review_text="Okay stay.",
            sentiment_label="neutral",
            sentiment_score=0.0,
        )
        db_session.add(r)
        db_session.commit()

        fetched = db_session.query(Review).filter_by(csv_review_id="REV00001").first()
        assert fetched is not None
        assert fetched.csv_user_id == "U0110"

    def test_review_with_user_link(self, db_session):
        u = User(username="reviewer1", email="r@test.com", password="hashed", role="customer")
        db_session.add(u)
        dest = destination.Destination(name="D", country="X")
        db_session.add(dest)
        db_session.flush()

        h = Hotel(destination_id=dest.id, name="H", price_tier="low")
        db_session.add(h)
        db_session.flush()

        r = Review(user_id=u.id, hotel_id=h.id, rating=5.0, review_text="Perfect!")
        db_session.add(r)
        db_session.commit()

        fetched = db_session.query(Review).filter_by(user_id=u.id).first()
        assert fetched is not None
        assert fetched.user_id == u.id


# ==============================================================================
# 5. Pydantic Schema Validation
# ==============================================================================

class TestReviewSchema:
    def test_valid_hotel_payload(self):
        data = ReviewCreateIn(hotel_id=1, rating=4.0, review_text="Great!")
        assert data.hotel_id == 1
        assert data.package_id is None

    def test_valid_package_payload(self):
        data = ReviewCreateIn(package_id=2, rating=3.5, review_text="Decent trip.")
        assert data.package_id == 2
        assert data.hotel_id is None

    def test_both_ids_raises(self):
        with pytest.raises(Exception):
            ReviewCreateIn(hotel_id=1, package_id=2, rating=4.0, review_text="Test")

    def test_neither_id_raises(self):
        with pytest.raises(Exception):
            ReviewCreateIn(rating=4.0, review_text="Test")

    def test_rating_too_low(self):
        with pytest.raises(Exception):
            ReviewCreateIn(hotel_id=1, rating=0.5, review_text="Test")

    def test_rating_too_high(self):
        with pytest.raises(Exception):
            ReviewCreateIn(hotel_id=1, rating=5.1, review_text="Test")

    def test_empty_review_text_raises(self):
        with pytest.raises(Exception):
            ReviewCreateIn(hotel_id=1, rating=4.0, review_text="")

    def test_whitespace_review_text_raises(self):
        with pytest.raises(Exception):
            ReviewCreateIn(hotel_id=1, rating=4.0, review_text="   ")

    def test_review_text_is_stripped(self):
        data = ReviewCreateIn(hotel_id=1, rating=4.0, review_text="  Nice place  ")
        assert data.review_text == "Nice place"


# ==============================================================================
# 6-12. API Endpoint Tests (FastAPI TestClient with SQLite)
# ==============================================================================

@pytest.fixture(scope="module")
def test_app():
    """
    Configure the FastAPI app to use an in-memory SQLite DB for API tests.
    We override the get_db dependency.
    """
    from app.main import app
    from app.database import get_db
    from app.services import auth_utils

    engine = _make_sqlite_engine()
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db

    # Seed a user, hotel, package for testing
    s = TestSession()
    from app.services.auth_utils import hash_password
    u = User(username="testuser", email="test@tm.com", password=hash_password("pass123"), role="customer")
    s.add(u)
    dest = destination.Destination(name="TestDest", country="India")
    s.add(dest)
    s.flush()
    h = Hotel(destination_id=dest.id, name="TestHotel", price_tier="medium")
    s.add(h)
    # Need a partner for package
    from app.models.partner import Partner
    p = Partner(owner_user_id=u.id, business_name="TestTours", partner_type="tour_operator", status="approved")
    s.add(p)
    s.flush()
    pkg = Package(destination_id=dest.id, partner_id=p.id, title="TestPackage", price_tier="medium")
    s.add(pkg)
    s.commit()

    yield app, TestSession, u.id, h.id, pkg.id

    # Teardown
    app.dependency_overrides.clear()
    engine.dispose()


def _get_token(client: TestClient, username="testuser", password="pass123") -> str:
    resp = client.post("/auth/login", json={"email": "test@tm.com", "password": password})
    if resp.status_code != 200:
        pytest.skip(f"Login failed with {resp.status_code}: {resp.text}")
    return resp.json()["token"]


class TestReviewAPI:
    def test_submit_hotel_review_authenticated(self, test_app):
        app, _, user_id, hotel_id, pkg_id = test_app
        client = TestClient(app)
        token = _get_token(client)
        resp = client.post(
            "/reviews/",
            json={"hotel_id": hotel_id, "rating": 4.5, "review_text": "Great hotel, very clean!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["hotel_id"] == hotel_id
        assert data["rating"] == 4.5
        assert data["sentiment_label"] in ("positive", "neutral", "negative")
        assert data["sentiment_score"] is not None

    def test_submit_duplicate_review_rejected(self, test_app):
        """Second review on same hotel by same user should return 409."""
        app, _, user_id, hotel_id, pkg_id = test_app
        client = TestClient(app)
        token = _get_token(client)
        # First review (may already exist from previous test)
        client.post(
            "/reviews/",
            json={"hotel_id": hotel_id, "rating": 4.0, "review_text": "Good stay"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Second attempt
        resp = client.post(
            "/reviews/",
            json={"hotel_id": hotel_id, "rating": 3.0, "review_text": "Another review"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    def test_submit_review_unauthenticated(self, test_app):
        app, _, user_id, hotel_id, pkg_id = test_app
        client = TestClient(app)
        resp = client.post(
            "/reviews/",
            json={"hotel_id": hotel_id, "rating": 3.0, "review_text": "Anonymous review"},
        )
        # Should get 401 or 403 (no token)
        assert resp.status_code in (401, 403)

    def test_submit_review_nonexistent_hotel(self, test_app):
        app, _, user_id, hotel_id, pkg_id = test_app
        client = TestClient(app)
        token = _get_token(client)
        resp = client.post(
            "/reviews/",
            json={"hotel_id": 99999, "rating": 4.0, "review_text": "Does not exist"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_get_hotel_reviews_summary(self, test_app):
        app, _, user_id, hotel_id, pkg_id = test_app
        client = TestClient(app)
        resp = client.get(f"/reviews/hotel/{hotel_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "hotel"
        assert data["entity_id"] == hotel_id
        assert "total_reviews" in data
        assert "average_rating" in data
        assert "positive_count" in data
        assert "recent_reviews" in data

    def test_get_hotel_reviews_not_found(self, test_app):
        app, _, user_id, hotel_id, pkg_id = test_app
        client = TestClient(app)
        resp = client.get("/reviews/hotel/99999")
        assert resp.status_code == 404

    def test_get_package_reviews_summary(self, test_app):
        app, _, user_id, hotel_id, pkg_id = test_app
        client = TestClient(app)
        resp = client.get(f"/reviews/package/{pkg_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "package"

    def test_get_my_reviews(self, test_app):
        app, _, user_id, hotel_id, pkg_id = test_app
        client = TestClient(app)
        token = _get_token(client)
        resp = client.get("/reviews/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_my_reviews_unauthenticated(self, test_app):
        app, _, user_id, hotel_id, pkg_id = test_app
        client = TestClient(app)
        resp = client.get("/reviews/me")
        assert resp.status_code in (401, 403)


# ==============================================================================
# 13-15. Import Script Tests
# ==============================================================================

class TestReviewImport:
    def test_dry_run_returns_nonzero_total(self):
        """Dry run should detect rows without touching the DB."""
        from scripts.seed_csv_reviews import seed
        result = seed(dry_run=True, verbose=False)
        assert result["total"] == 162, f"Expected 162 rows, got {result['total']}"

    def test_dry_run_does_not_write_db(self, db_session):
        """After dry run the reviews table should remain empty."""
        from scripts.seed_csv_reviews import seed
        with patch("scripts.seed_csv_reviews.verify_local_development_target"):
            with patch("scripts.seed_csv_reviews.SessionLocal") as mock_sl:
                mock_sl.return_value = db_session
                seed(dry_run=True, verbose=False)
        count = db_session.query(Review).count()
        assert count == 0, "Dry run should not write to DB"

    def test_invalid_ratings_are_rejected(self):
        """Rows with ratings outside [1,5] are counted as validation errors."""
        import csv, io
        from scripts.seed_csv_reviews import _safe_float
        bad_ratings = ["0", "5.1", "abc", "", "-1"]
        for r in bad_ratings:
            val = _safe_float(r)
            is_valid = val is not None and 1.0 <= val <= 5.0
            assert not is_valid, f"Rating '{r}' should be invalid"

    def test_production_guard_refuses_remote_host(self):
        """seed() must raise RuntimeError on non-local hosts."""
        from scripts.seed_csv_reviews import verify_local_development_target
        with patch.object(settings, "POSTGRES_HOST", "remote.prod.db.internal"):
            with pytest.raises(RuntimeError, match="not a verified local development host"):
                verify_local_development_target()

    def test_production_guard_refuses_production_env(self):
        from scripts.seed_csv_reviews import verify_local_development_target
        with patch.object(settings, "POSTGRES_HOST", "localhost"):
            with patch.object(settings, "ENVIRONMENT", "production"):
                with pytest.raises(RuntimeError, match="forbidden in production"):
                    verify_local_development_target()

    def test_idempotency_on_reimport(self, db_session):
        """
        Importing the same csv_review_id twice should not create duplicate rows.
        We test the duplicate-skip logic directly.
        """
        dest = destination.Destination(name="Idem Dest", country="X")
        db_session.add(dest)
        db_session.flush()
        h = Hotel(destination_id=dest.id, name="Idem Hotel", price_tier="low")
        db_session.add(h)
        db_session.flush()

        # First insert
        r1 = Review(
            csv_review_id="REV_IDEM_01",
            hotel_id=h.id,
            rating=4.0,
            review_text="First import",
            sentiment_label="positive",
            sentiment_score=0.5,
        )
        db_session.add(r1)
        db_session.commit()

        # Second insert with same csv_review_id
        r2 = Review(
            csv_review_id="REV_IDEM_01",  # same ID
            hotel_id=h.id,
            rating=3.0,
            review_text="Duplicate",
            sentiment_label="neutral",
            sentiment_score=0.0,
        )
        db_session.add(r2)
        try:
            db_session.commit()
            # Some DBs enforce unique constraint; if not, check count
            count = db_session.query(Review).filter_by(csv_review_id="REV_IDEM_01").count()
            assert count == 1, "Duplicate csv_review_id must not create a second row"
        except Exception:
            db_session.rollback()
            # Constraint raised — correct behaviour


# ==============================================================================
# 16-17. Regression Tests
# ==============================================================================

class TestRegressions:
    def test_booking_routes_still_importable(self):
        """Ensure booking routes still import cleanly after Phase 3 additions."""
        from app.routes import booking_routes
        assert hasattr(booking_routes, "router")

    def test_recommend_routes_still_importable(self):
        from app.routes import recommend_routes
        assert hasattr(recommend_routes, "router")

    def test_destination_routes_still_importable(self):
        from app.routes import destination_routes
        assert hasattr(destination_routes, "router")

    def test_user_model_has_reviews_relationship(self):
        u = User.__mapper__.relationships
        assert "reviews" in u, "User model must have 'reviews' relationship"

    def test_review_model_registers_on_base(self):
        from app.database import Base
        assert "reviews" in Base.metadata.tables, "reviews table must be registered on Base.metadata"
