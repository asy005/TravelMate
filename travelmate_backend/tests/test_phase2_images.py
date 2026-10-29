"""
test_phase2_images.py
----------------------
Tests for Phase 2: real image serving and visual discovery.

Covers:
  - image_resolver utility functions
  - /dataset-images static mount (via TestClient)
  - /destinations/ API returning thumbnail_url
  - /photo/landmark endpoint existence and response contract
"""

import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

# ── App & DB fixtures ────────────────────────────────────────────────────────
from app.database import Base, get_db
from app.main import app
from app.models.destination import Destination

# Import all models so Base.metadata is fully populated
from app.models import (  # noqa: F401
    user, favorites, destination as _dest_mod, conversation,
    refresh_token, password_reset_token, partner, hotel, package, booking,
)


# ── SQLite in-memory engine shared across tests in this module ───────────────
_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)


def _override_get_db():
    db = _TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """Create tables and seed test data once for the whole module."""
    Base.metadata.create_all(bind=_TEST_ENGINE)
    app.dependency_overrides[get_db] = _override_get_db

    # Seed one destination that has a known dataset image (D0001_Goa.jpg)
    db = _TestingSession()
    db.add(
        Destination(
            id=1,
            name="Goa",
            country="India",
            description="Sun, sand and sea.",
            lat=15.2993,
            lon=74.124,
            tags="beach,party,relaxing",
            thumbnail_url=None,           # intentionally empty so resolver is exercised
            avg_rating=4.5,
            csv_destination_id="D0001",
        )
    )
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=_TEST_ENGINE)
    app.dependency_overrides.pop(get_db, None)


# ── image_resolver unit tests ────────────────────────────────────────────────

class TestImageResolver:
    def test_destination_found(self):
        """resolve_destination_image returns a URL for a known csv_id that has an image."""
        from app.utils.image_resolver import resolve_destination_image
        url = resolve_destination_image(1, "D0001")
        assert url != "", "Expected a non-empty URL for D0001"
        assert url.startswith("/dataset-images/destinations/"), f"Unexpected URL: {url}"
        assert "D0001" in url

    def test_destination_missing(self):
        """resolve_destination_image returns '' for a csv_id with no image."""
        from app.utils.image_resolver import resolve_destination_image
        url = resolve_destination_image(999999, "D9999")
        assert url == "", f"Expected empty string, got: {url!r}"

    def test_attraction_found(self):
        """resolve_attraction_image returns a URL for a known attraction id."""
        from app.utils.image_resolver import resolve_attraction_image
        # ATT0003_Akshardham_Temple.jpg is present in the dataset
        url = resolve_attraction_image("ATT0003")
        assert url != "", "Expected a non-empty URL for ATT0003"
        assert url.startswith("/dataset-images/attractions/"), f"Unexpected URL: {url}"
        assert "ATT0003" in url

    def test_attraction_missing(self):
        """resolve_attraction_image returns '' for a non-existent attraction."""
        from app.utils.image_resolver import resolve_attraction_image
        url = resolve_attraction_image("ATT999999")
        assert url == "", f"Expected empty string, got: {url!r}"

    def test_hotel_found(self):
        """resolve_hotel_image returns a URL for a known accommodation type."""
        from app.utils.image_resolver import resolve_hotel_image
        url = resolve_hotel_image("Hotel")
        assert url != "", "Expected a non-empty URL for 'Hotel' type"
        assert url.startswith("/dataset-images/hotels/"), f"Unexpected URL: {url}"

    def test_hotel_missing(self):
        """resolve_hotel_image returns '' for an unknown accommodation type."""
        from app.utils.image_resolver import resolve_hotel_image
        url = resolve_hotel_image("UnknownTypeThatDoesNotExist")
        assert url == "", f"Expected empty string, got: {url!r}"


# ── Static mount tests (serve real files from disk) ─────────────────────────

class TestStaticMount:
    @pytest.fixture(scope="class")
    def client(self):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

    def test_destination_image_served(self, client):
        """GET a real destination image and verify HTTP 200."""
        from app.utils.image_resolver import resolve_destination_image
        url = resolve_destination_image(1, "D0001")
        assert url, "Resolver must return a URL for D0001 to run this test"
        response = client.get(url)
        assert response.status_code == 200, (
            f"Expected 200 for {url}, got {response.status_code}"
        )

    def test_missing_image_returns_404(self, client):
        """GET a non-existent image path returns 404."""
        response = client.get("/dataset-images/destinations/D_DOES_NOT_EXIST_9999.jpg")
        assert response.status_code == 404, (
            f"Expected 404 for missing image, got {response.status_code}"
        )


# ── Destinations API test ────────────────────────────────────────────────────

class TestDestinationsApi:
    @pytest.fixture(scope="class")
    def client(self):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

    def test_destination_api_includes_thumbnail(self, client):
        """GET /destinations/ must return at least one result with a non-empty thumbnail_url."""
        response = client.get("/destinations/")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        results = response.json()
        assert len(results) > 0, "Expected at least one destination in response"

        urls = [r.get("thumbnail_url") for r in results if r.get("thumbnail_url")]
        assert len(urls) > 0, (
            "Expected at least one destination with a non-empty thumbnail_url. "
            f"Got: {[r.get('thumbnail_url') for r in results]}"
        )
        # All returned URLs should look like dataset-images paths
        for url in urls:
            assert url.startswith("/dataset-images/"), f"Unexpected URL format: {url}"


# ── Landmark endpoint test ───────────────────────────────────────────────────

class TestLandmarkEndpoint:
    @pytest.fixture(scope="class")
    def client(self):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

    def _minimal_jpeg_bytes(self) -> bytes:
        """Return a minimal valid JPEG image as bytes."""
        from PIL import Image
        img = Image.new("RGB", (10, 10), color=(128, 64, 32))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    def test_landmark_endpoint_responds(self, client):
        """POST /photo/landmark must respond 200 or 503, never 500."""
        jpeg_bytes = self._minimal_jpeg_bytes()
        response = client.post(
            "/photo/landmark",
            files={"file": ("test.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
        )
        assert response.status_code in (200, 503), (
            f"Expected 200 or 503, got {response.status_code}: {response.text}"
        )
        body = response.json()
        if response.status_code == 503:
            assert body.get("available") is False
            assert "message" in body
        else:
            # 200: should have landmark and confidence
            assert "landmark" in body or "error" in body
