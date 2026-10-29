"""
Tests for hotel and package selection persistence (Task 1).

Verifies that:
- Selecting a hotel correctly mutates and persists the JSON plan column.
- Selecting a package correctly mutates and persists the JSON plan column.
- Re-selecting a different hotel replaces (not duplicates) the selection.
- The /hotels/select and /packages/select endpoints return the updated plan.
- No booking is created merely by selecting a hotel or package.
- Missing/invalid session and resource IDs are handled with correct HTTP codes.
"""
import copy
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.conversation import ConversationSession
from app.models.destination import Destination
from app.models.partner import Partner
from app.models.hotel import Hotel
from app.models.package import Package
from app.models.booking import Booking
from app.services.auth_utils import create_token, hash_password


# ---------------------------------------------------------------------------
# In-memory DB fixture (isolated per test)
# ---------------------------------------------------------------------------
@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db(db_engine):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    """TestClient that overrides get_db with the in-memory session."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------
def _seed_world(db):
    """Create a destination, hotel, package, and a session with a plan."""
    dest = Destination(
        name="Goa",
        country="India",
        description="Beach paradise",
        lat=15.2993,
        lon=74.1240,
    )
    db.add(dest)
    db.flush()

    user = User(
        username="partner_seed",
        email="partner_seed@test.com",
        password=hash_password("password123"),
        role="partner",
    )
    db.add(user)
    db.flush()

    partner = Partner(
        owner_user_id=user.id,
        business_name="Goa Adventures",
        partner_type="tour_operator",
    )
    db.add(partner)
    db.flush()

    hotel = Hotel(
        destination_id=dest.id,
        partner_id=partner.id,
        name="Blue Lagoon Resort",
        price_per_night=4500.0,
        star_rating=4.0,
        accommodation_type="resort",
        price_tier="luxury",
    )
    db.add(hotel)

    pkg = Package(
        destination_id=dest.id,
        partner_id=partner.id,
        title="Goa Beach Tour",
        price_per_package=12000.0,
        duration_days=3,
        price_tier="medium",
    )
    db.add(pkg)
    db.flush()

    plan = {
        "trip_overview": {"primary_destination": "Goa", "duration_days": 3, "travelers": 2},
        "destinations": [{"id": dest.id, "name": "Goa"}],
        "budget": {},
        "day_wise_itinerary": [],
    }
    session = ConversationSession(
        session_id="test-session-abc",
        messages=[],
        slots={"duration_days": 3, "travelers": 2},
        status="ready",
        generated_plan=plan,
    )
    db.add(session)
    db.commit()
    db.refresh(dest)
    db.refresh(hotel)
    db.refresh(pkg)
    db.refresh(session)
    return dest, hotel, pkg, session


# ---------------------------------------------------------------------------
# Hotel selection tests
# ---------------------------------------------------------------------------
class TestHotelSelection:
    def test_select_hotel_persists_in_plan(self, client, db):
        dest, hotel, pkg, sess = _seed_world(db)
        res = client.post("/hotels/select", json={
            "session_id": sess.session_id,
            "destination_id": dest.id,
            "hotel_id": hotel.id,
        })
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["msg"] == "Hotel selected"

        # The returned plan must carry the selection
        selected = data["plan"]["destinations"][0].get("selected_hotel")
        assert selected is not None
        assert selected["id"] == hotel.id
        assert selected["name"] == "Blue Lagoon Resort"

    def test_select_hotel_survives_db_reload(self, client, db):
        """Verify the mutation is actually written to the DB (not just in memory)."""
        dest, hotel, pkg, sess = _seed_world(db)
        client.post("/hotels/select", json={
            "session_id": sess.session_id,
            "destination_id": dest.id,
            "hotel_id": hotel.id,
        })
        # Expire the ORM cache and reload from DB
        db.expire_all()
        reloaded = db.query(ConversationSession).filter(
            ConversationSession.session_id == sess.session_id
        ).first()
        sel = reloaded.generated_plan["destinations"][0].get("selected_hotel")
        assert sel is not None, "Hotel selection was NOT persisted to the DB (flag_modified bug)"
        assert sel["name"] == "Blue Lagoon Resort"

    def test_select_different_hotel_replaces_not_duplicates(self, client, db):
        dest, hotel, pkg, sess = _seed_world(db)
        hotel2 = Hotel(
            destination_id=dest.id,
            name="Sea Breeze Inn",
            price_per_night=2000.0,
            star_rating=3.0,
            accommodation_type="hotel",
            price_tier="medium",
        )
        db.add(hotel2)
        db.commit()
        db.refresh(hotel2)

        client.post("/hotels/select", json={
            "session_id": sess.session_id,
            "destination_id": dest.id,
            "hotel_id": hotel.id,
        })
        client.post("/hotels/select", json={
            "session_id": sess.session_id,
            "destination_id": dest.id,
            "hotel_id": hotel2.id,
        })
        db.expire_all()
        reloaded = db.query(ConversationSession).filter(
            ConversationSession.session_id == sess.session_id
        ).first()
        sel = reloaded.generated_plan["destinations"][0].get("selected_hotel")
        assert sel["name"] == "Sea Breeze Inn", "Second selection should replace first"
        # Must be a single dict, not a list
        assert isinstance(sel, dict)

    def test_select_hotel_does_not_create_booking(self, client, db):
        dest, hotel, pkg, sess = _seed_world(db)
        client.post("/hotels/select", json={
            "session_id": sess.session_id,
            "destination_id": dest.id,
            "hotel_id": hotel.id,
        })
        booking_count = db.query(Booking).count()
        assert booking_count == 0, "Selecting a hotel must NOT create a booking"

    def test_select_hotel_unknown_session_returns_404(self, client, db):
        dest, hotel, pkg, sess = _seed_world(db)
        res = client.post("/hotels/select", json={
            "session_id": "nonexistent-session",
            "destination_id": dest.id,
            "hotel_id": hotel.id,
        })
        assert res.status_code == 404

    def test_select_unknown_hotel_returns_404(self, client, db):
        dest, hotel, pkg, sess = _seed_world(db)
        res = client.post("/hotels/select", json={
            "session_id": sess.session_id,
            "destination_id": dest.id,
            "hotel_id": 99999,
        })
        assert res.status_code == 404

    def test_select_hotel_wrong_destination_returns_404(self, client, db):
        dest, hotel, pkg, sess = _seed_world(db)
        res = client.post("/hotels/select", json={
            "session_id": sess.session_id,
            "destination_id": 99999,
            "hotel_id": hotel.id,
        })
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Package selection tests
# ---------------------------------------------------------------------------
class TestPackageSelection:
    def test_select_package_persists_in_plan(self, client, db):
        dest, hotel, pkg, sess = _seed_world(db)
        res = client.post("/packages/select", json={
            "session_id": sess.session_id,
            "destination_id": dest.id,
            "package_id": pkg.id,
        })
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["msg"] == "Package selected"
        selected = data["plan"]["destinations"][0].get("selected_package")
        assert selected is not None
        assert selected["id"] == pkg.id
        assert selected["title"] == "Goa Beach Tour"

    def test_select_package_survives_db_reload(self, client, db):
        dest, hotel, pkg, sess = _seed_world(db)
        client.post("/packages/select", json={
            "session_id": sess.session_id,
            "destination_id": dest.id,
            "package_id": pkg.id,
        })
        db.expire_all()
        reloaded = db.query(ConversationSession).filter(
            ConversationSession.session_id == sess.session_id
        ).first()
        sel = reloaded.generated_plan["destinations"][0].get("selected_package")
        assert sel is not None, "Package selection was NOT persisted to the DB (flag_modified bug)"
        assert sel["title"] == "Goa Beach Tour"

    def test_select_package_does_not_create_booking(self, client, db):
        dest, hotel, pkg, sess = _seed_world(db)
        client.post("/packages/select", json={
            "session_id": sess.session_id,
            "destination_id": dest.id,
            "package_id": pkg.id,
        })
        assert db.query(Booking).count() == 0

    def test_select_package_unknown_session_returns_404(self, client, db):
        dest, hotel, pkg, sess = _seed_world(db)
        res = client.post("/packages/select", json={
            "session_id": "bad-session",
            "destination_id": dest.id,
            "package_id": pkg.id,
        })
        assert res.status_code == 404

    def test_select_package_session_without_plan_returns_400(self, client, db):
        dest, hotel, pkg, sess = _seed_world(db)
        sess.generated_plan = None
        db.add(sess)
        db.commit()
        res = client.post("/packages/select", json={
            "session_id": sess.session_id,
            "destination_id": dest.id,
            "package_id": pkg.id,
        })
        assert res.status_code == 400
