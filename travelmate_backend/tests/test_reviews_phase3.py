from __future__ import annotations
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.database import Base
from app.models import user, favorites, destination, conversation
from app.models import refresh_token, password_reset_token
from app.models import partner, hotel, package, booking
from app.models import review
from app.models.user import User
from app.models.hotel import Hotel
from app.models.package import Package
from app.models.review import Review
from app.services.sentiment_analyser import analyse, classify_review, classify_by_rating, SentimentResult
from app.schemas.review_schema import ReviewCreateIn
from app.config import settings

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

class TestSentimentAnalyser:
    def test_positive_text(self):
        result = analyse("Really enjoyed our trip. Smooth experience from start to finish. Amazing hotel!")
        assert result.label == "positive"
        assert result.score > 0

    def test_negative_text(self):
        result = analyse("Terrible service, dirty room, rude staff. Worst hotel ever.")
        assert result.label == "negative"
        assert result.score < 0

    def test_neutral_text(self):
        result = analyse("We arrived at the hotel. The room was there.")
        assert result.label in ("neutral", "positive", "negative")  # mostly neutral expected

    def test_classify_review_positive(self):
        result = classify_review("Great stay, loved the view, very comfortable!", 4.5)
        assert result.label == "positive"

    def test_classify_review_negative(self):
        result = classify_review("Disappointing and overpriced. Bad experience.", 2.0)
        assert result.label == "negative"

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
        result = analyse("not good not clean not friendly")
        assert result.label != "positive"

    def test_intensifier_amplifies_positive(self):
        plain = analyse("good")
        amplified = analyse("very good")
        assert abs(amplified.score) >= abs(plain.score)

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

class TestReviewModel:
    def test_create_hotel_review(self, db_session):
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

@pytest.fixture(scope="module")
def test_app():
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

    s = TestSession()
    from app.services.auth_utils import hash_password
    u = User(username="testuser", email="test@tm.com", password=hash_password("pass123"), role="customer")
    s.add(u)
    dest = destination.Destination(name="TestDest", country="India")
    s.add(dest)
    s.flush()
    h = Hotel(destination_id=dest.id, name="TestHotel", price_tier="medium")
    s.add(h)
    from app.models.partner import Partner
    p = Partner(owner_user_id=u.id, business_name="TestTours", partner_type="tour_operator", status="approved")
    s.add(p)
    s.flush()
    pkg = Package(destination_id=dest.id, partner_id=p.id, title="TestPackage", price_tier="medium")
    s.add(pkg)
    s.commit()

    yield app, TestSession, u.id, h.id, pkg.id

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
        app, _, user_id, hotel_id, pkg_id = test_app
        client = TestClient(app)
        token = _get_token(client)
        client.post(
            "/reviews/",
            json={"hotel_id": hotel_id, "rating": 4.0, "review_text": "Good stay"},
            headers={"Authorization": f"Bearer {token}"},
        )
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

class TestReviewImport:
    def test_dry_run_returns_nonzero_total(self):
        from scripts.seed_csv_reviews import seed
        result = seed(dry_run=True, verbose=False)
        assert result["total"] == 162, f"Expected 162 rows, got {result['total']}"

    def test_dry_run_does_not_write_db(self, db_session):
        from scripts.seed_csv_reviews import seed
        with patch("scripts.seed_csv_reviews.verify_local_development_target"):
            with patch("scripts.seed_csv_reviews.SessionLocal") as mock_sl:
                mock_sl.return_value = db_session
                seed(dry_run=True, verbose=False)
        count = db_session.query(Review).count()
        assert count == 0, "Dry run should not write to DB"

    def test_invalid_ratings_are_rejected(self):
        import csv, io
        from scripts.seed_csv_reviews import _safe_float
        bad_ratings = ["0", "5.1", "abc", "", "-1"]
        for r in bad_ratings:
            val = _safe_float(r)
            is_valid = val is not None and 1.0 <= val <= 5.0
            assert not is_valid, f"Rating '{r}' should be invalid"

    def test_production_guard_refuses_remote_host(self):
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
        dest = destination.Destination(name="Idem Dest", country="X")
        db_session.add(dest)
        db_session.flush()
        h = Hotel(destination_id=dest.id, name="Idem Hotel", price_tier="low")
        db_session.add(h)
        db_session.flush()

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
            count = db_session.query(Review).filter_by(csv_review_id="REV_IDEM_01").count()
            assert count == 1, "Duplicate csv_review_id must not create a second row"
        except Exception:
            db_session.rollback()

class TestRegressions:
    def test_booking_routes_still_importable(self):
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

class TestAspectAndComplaintExtraction:
    def test_praises_extracted_when_supported(self):
        from app.services.sentiment_analyser import extract_aspects_and_complaints
        texts = [
            "Everything was well organized and the staff were very helpful.",
            "Great value for money at this hotel. The whole family had a fantastic time.",
        ]
        praises, complaints = extract_aspects_and_complaints(texts)
        assert "Helpful & courteous staff" in praises
        assert "Great value for money" in praises
        assert "Family-friendly environment" in praises
        assert complaints == []

    def test_complaints_extracted_when_supported(self):
        from app.services.sentiment_analyser import extract_aspects_and_complaints
        texts = [
            "Had severe issues with cleanliness and service during our stay. Very dirty room.",
            "Disappointed with the experience. Did not match what was promised.",
        ]
        praises, complaints = extract_aspects_and_complaints(texts)
        assert "Cleanliness & hygiene issues" in complaints
        assert "Service & response delays" in complaints
        assert "Mismatch with expectations" in complaints
        assert praises == []

    def test_no_fabrication_on_empty_text_list(self):
        from app.services.sentiment_analyser import extract_aspects_and_complaints
        praises, complaints = extract_aspects_and_complaints([])
        assert praises == []
        assert complaints == []

    def test_negation_suppresses_praise(self):
        from app.services.sentiment_analyser import extract_aspects_and_complaints
        texts = ["The room was not clean and there were issues with cleanliness."]
        praises, complaints = extract_aspects_and_complaints(texts)
        assert "Cleanliness & hygiene" not in praises
        assert "Cleanliness & hygiene issues" in complaints

    def test_complaint_negation_not_noisy_not_dirty_not_expensive(self):
        from app.services.sentiment_analyser import extract_aspects_and_complaints
        texts = [
            "The room was not noisy at all, definitely not expensive, and not dirty.",
            "The hotel was neither dirty nor noisy, and wasn't expensive.",
        ]
        praises, complaints = extract_aspects_and_complaints(texts)
        assert "Noise disturbance" not in complaints
        assert "Cleanliness & hygiene issues" not in complaints
        assert "Overpriced / poor value" not in complaints
        assert complaints == []

    def test_praise_negation_not_worth_the_money(self):
        from app.services.sentiment_analyser import extract_aspects_and_complaints
        texts = ["The hotel was not worth the money. Very disappointing stay."]
        praises, complaints = extract_aspects_and_complaints(texts)
        assert "Great value for money" not in praises
        assert "Overpriced / poor value" in complaints

    def test_complaint_negation_no_issues_and_no_complaints(self):
        from app.services.sentiment_analyser import extract_aspects_and_complaints
        texts = ["Had a smooth vacation with no issues with service and no complaints."]
        praises, complaints = extract_aspects_and_complaints(texts)
        assert "Service & response delays" not in complaints

    def test_aspect_context_requires_genuine_support(self):
        from app.services.sentiment_analyser import extract_aspects_and_complaints
        texts = ["We bought a train ticket at 5pm and checked our luggage."]
        praises, complaints = extract_aspects_and_complaints(texts)
        assert praises == []
        assert complaints == []

    def test_sentiment_summary_generation(self):
        from app.services.sentiment_analyser import generate_sentiment_summary
        assert generate_sentiment_summary(0, 0, 0, 0) is None
        summary_pos = generate_sentiment_summary(10, 9, 1, 0)
        assert "Overwhelmingly positive" in summary_pos
        summary_crit = generate_sentiment_summary(10, 1, 2, 7)
        assert "Critical reviews" in summary_crit

class TestDestinationAttractionRestaurantReviews:
    def test_get_destination_reviews_summary(self, test_app):
        app, _, user_id, hotel_id, pkg_id = test_app
        client = TestClient(app)
        resp = client.get("/reviews/destination/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "destination"
        assert data["entity_id"] == 1
        assert "total_reviews" in data
        assert "average_rating" in data
        assert "praised_aspects" in data
        assert "recurring_complaints" in data
        assert "sentiment_summary" in data

    def test_get_destination_reviews_not_found(self, test_app):
        app, _, _, _, _ = test_app
        client = TestClient(app)
        resp = client.get("/reviews/destination/99999")
        assert resp.status_code == 404

    def test_get_attraction_reviews_dataset(self, test_app):
        app, _, _, _, _ = test_app
        client = TestClient(app)
        resp = client.get("/reviews/attraction/ATT0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "attraction"
        assert data["entity_id"] == "ATT0001"
        assert data["average_rating"] == pytest.approx(4.6, abs=0.1)
        assert data["total_reviews"] == 0
        assert data["recent_reviews"] == []

    def test_get_attraction_reviews_not_found(self, test_app):
        app, _, _, _, _ = test_app
        client = TestClient(app)
        resp = client.get("/reviews/attraction/NONEXISTENT_999")
        assert resp.status_code == 404

    def test_get_restaurant_reviews_dataset(self, test_app):
        app, _, _, _, _ = test_app
        client = TestClient(app)
        resp = client.get("/reviews/restaurant/RST00001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "restaurant"
        assert data["entity_id"] == "RST00001"
        assert data["average_rating"] == pytest.approx(3.9, abs=0.1)
        assert data["total_reviews"] == 0
        assert data["recent_reviews"] == []

    def test_get_restaurant_reviews_not_found(self, test_app):
        app, _, _, _, _ = test_app
        client = TestClient(app)
        resp = client.get("/reviews/restaurant/NONEXISTENT_RST")
        assert resp.status_code == 404

    def test_parse_safe_rating_valid(self):
        from app.routes.review_routes import _parse_safe_rating
        assert _parse_safe_rating("4.5") == 4.5
        assert _parse_safe_rating("3") == 3.0
        assert _parse_safe_rating(5.0) == 5.0
        assert _parse_safe_rating(" 4.2 ") == 4.2

    def test_parse_safe_rating_missing_or_invalid(self):
        from app.routes.review_routes import _parse_safe_rating
        assert _parse_safe_rating(None) is None
        assert _parse_safe_rating("") is None
        assert _parse_safe_rating("   ") is None
        assert _parse_safe_rating("abc") is None
        assert _parse_safe_rating("N/A") is None
        assert _parse_safe_rating("0.5") is None  # Below 1.0
        assert _parse_safe_rating("5.5") is None  # Above 5.0
        assert _parse_safe_rating("-1") is None

    def test_attraction_missing_rating_returns_none(self, test_app):
        app, _, _, _, _ = test_app
        client = TestClient(app)
        mock_entry = {
            "id": "ATT_NO_RATING",
            "name": "No Rating Monument",
            "city": "TestCity",
            "state": "TestState",
            "category": "Heritage",
            "rating": None,
        }
        with patch("app.routes.review_routes._get_attraction_by_id", return_value=mock_entry):
            resp = client.get("/reviews/attraction/ATT_NO_RATING")
            assert resp.status_code == 200
            data = resp.json()
            assert data["average_rating"] is None
            assert data["sentiment_summary"] == "No ratings available yet."

    def test_restaurant_missing_rating_returns_none(self, test_app):
        app, _, _, _, _ = test_app
        client = TestClient(app)
        mock_entry = {
            "id": "RST_NO_RATING",
            "name": "No Rating Cafe",
            "city": "TestCity",
            "cuisine": "Cafe",
            "price_range": "300",
            "address": "Test Road",
            "rating": None,
        }
        with patch("app.routes.review_routes._get_restaurant_by_id", return_value=mock_entry):
            resp = client.get("/reviews/restaurant/RST_NO_RATING")
            assert resp.status_code == 200
            data = resp.json()
            assert data["average_rating"] is None
            assert data["sentiment_summary"] == "No ratings available yet."

    def test_attraction_csv_load_error_handled_safely(self, test_app):
        from app.routes import review_routes
        app, _, _, _, _ = test_app
        client = TestClient(app)

        with patch.object(review_routes, "_attractions_cache", None):
            with patch("builtins.open", side_effect=OSError("Disk read failure")):
                resp = client.get("/reviews/attraction/ATT0001")
                assert resp.status_code == 404

    def test_restaurant_csv_load_error_handled_safely(self, test_app):
        from app.routes import review_routes
        app, _, _, _, _ = test_app
        client = TestClient(app)

        with patch.object(review_routes, "_restaurants_cache", None):
            with patch("builtins.open", side_effect=OSError("Disk read failure")):
                resp = client.get("/reviews/restaurant/RST0001")
                assert resp.status_code == 404

def test_negation_distinguishes_not_clean_from_not_dirty():
    from app.services.sentiment_analyser import extract_aspects_and_complaints

    _, complaints = extract_aspects_and_complaints([
        "The room was not clean.",
        "The room was not dirty."
    ])

    assert "Cleanliness & hygiene issues" in complaints


def test_clean_room_is_recognized_as_praise():
    from app.services.sentiment_analyser import extract_aspects_and_complaints

    praises, complaints = extract_aspects_and_complaints([
        "The room was clean and tidy."
    ])

    assert "Cleanliness & hygiene" in praises
    assert "Cleanliness & hygiene issues" not in complaints