"""
Regression tests for Priority 1: Budget Calculation and Consistency.

Verifies:
1. Initial trip plan generation populates reasonable non-zero estimates for all
   expense categories (hotel, transportation, food, activities, misc, reserve).
2. Package selection recalculates the budget using the unified allocate_budget service,
   accounts for package amenities without double-charging, and never sets categories to 0.
3. Hotel selection recalculates budget consistently, scales flexible costs appropriately,
   and persists the updated budget in the conversation session.
4. Over-budget scenario (fixed costs > total budget) never collapses flexible
   categories (food, transportation, activities, misc) to 0 and correctly reports
   Over Budget status with alternative hotel recommendations.
5. All calculations (estimated_total, cost_per_traveler, cost_per_day, remaining_budget,
   health status) are strictly consistent and sum exactly.
"""
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
from app.services.auth_utils import hash_password
from app.services.budget_optimizer import allocate_budget, parse_total_budget


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
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


def _seed_shimla_environment(db):
    """Seed Shimla destination with expensive and budget hotels, and a tour package."""
    dest = Destination(
        name="Shimla",
        country="India",
        description="Hill station in Himachal Pradesh",
        lat=31.1048,
        lon=77.1734,
        tags="Hill Station,Himachal Pradesh,Shimla,Relaxing",
        avg_rating=4.5,
    )
    db.add(dest)
    db.flush()

    user = User(
        username="shimla_partner",
        email="partner@shimla.local",
        password=hash_password("Pass123!"),
        role="partner",
    )
    db.add(user)
    db.flush()

    partner = Partner(
        owner_user_id=user.id,
        business_name="TravelMate Adventures",
        partner_type="tour_operator",
        status="approved",
    )
    db.add(partner)
    db.flush()

    # Expensive hotel (Homestay: 3800/night * 5 = 19,000)
    expensive_hotel = Hotel(
        destination_id=dest.id,
        partner_id=partner.id,
        name="Shimla Homestay Retreat",
        price_per_night=3800.0,
        star_rating=4.5,
        accommodation_type="homestay",
        price_tier="medium",
        amenities="WiFi,Breakfast",
    )
    # Budget hotel (Budget Inn: 1800/night * 5 = 9,000)
    cheap_hotel = Hotel(
        destination_id=dest.id,
        partner_id=partner.id,
        name="Shimla Budget Inn",
        price_per_night=1800.0,
        star_rating=3.8,
        accommodation_type="hotel",
        price_tier="low",
        amenities="WiFi",
    )
    db.add(expensive_hotel)
    db.add(cheap_hotel)

    # Explorer tour package (8500 total, 3 days, breakfast + guided tours + local transport)
    pkg = Package(
        destination_id=dest.id,
        partner_id=partner.id,
        title="Shimla Explorer Tour",
        price_per_package=8500.0,
        duration_days=3,
        capacity=8,
        price_tier="medium",
        amenities="Guided tours,Local transport,Sightseeing pass,Breakfast",
        category="tour_operator",
    )
    db.add(pkg)
    db.flush()

    plan = {
        "trip_overview": {
            "origin": "Delhi",
            "destination": "Shimla",
            "duration_days": 5,
            "travelers": 2,
            "budget": "30000",
            "primary_destination": "Shimla",
        },
        "destinations": [
            {
                "id": dest.id,
                "name": "Shimla",
                "recommended_hotels": [
                    {
                        "id": expensive_hotel.id,
                        "name": expensive_hotel.name,
                        "price_per_night": expensive_hotel.price_per_night,
                    },
                    {
                        "id": cheap_hotel.id,
                        "name": cheap_hotel.name,
                        "price_per_night": cheap_hotel.price_per_night,
                    },
                ],
                "recommended_packages": [
                    {
                        "id": pkg.id,
                        "title": pkg.title,
                        "price_per_package": pkg.price_per_package,
                    }
                ],
            }
        ],
        "budget": {},
        "day_wise_itinerary": [],
    }

    session = ConversationSession(
        session_id="shimla-test-session",
        messages=[],
        slots={"duration_days": 5, "travelers": 2, "budget": "30000", "travel_style": "relaxing"},
        status="ready",
        generated_plan=plan,
    )
    db.add(session)
    db.commit()
    return dest, expensive_hotel, cheap_hotel, pkg, session


class TestBudgetCalculationRegression:
    def test_initial_budget_allocation_populates_all_categories_non_zero(self, db):
        """Initial plan generation budget for 30,000 Shimla trip must have non-zero flexible estimates."""
        dest, expensive_hotel, cheap_hotel, pkg, session = _seed_shimla_environment(db)

        slots = {"budget": "30000", "travel_style": "relaxing", "duration_days": 5, "travelers": 2}
        budget = allocate_budget(
            db,
            slots=slots,
            duration_days=5,
            travelers=2,
            destination_id=dest.id,
            selected_hotel=None,
            selected_package=None,
        )

        breakdown = budget["breakdown"]
        # Ensure every single category is initialized and non-zero
        assert breakdown["hotel"] > 0, "Hotel cost should be initialized from top candidate hotel"
        assert breakdown["transportation"] > 0, "Transportation must never be 0"
        assert breakdown["food"] > 0, "Food must never be 0"
        assert breakdown["activities"] > 0, "Activities must never be 0"
        assert breakdown["miscellaneous"] > 0, "Miscellaneous must never be 0"
        assert breakdown["emergency_reserve"] == 3000, "Emergency reserve should be 10% of 30,000"

        # Math consistency
        assert budget["estimated_total"] == sum(breakdown.values())
        assert budget["remaining_budget"] == 30000 - budget["estimated_total"]
        assert budget["cost_per_traveler"] == round(budget["estimated_total"] / 2)
        assert budget["cost_per_day"] == round(budget["estimated_total"] / 5)
        assert budget["status"] in ("Within Budget", "Near Budget Limit", "Over Budget")

    def test_package_selection_in_shimla_scenario_never_shows_zero_for_flexible_categories(self, db, client):
        """
        In the Shimla scenario (budget ₹30,000, 5 days, 2 travelers):
        Default hotel = ₹19,000 (3,800/night * 5)
        Package = ₹8,500
        Emergency reserve = ₹3,000
        Total fixed = ₹30,500 > 30,000.
        Transportation, food, activities, misc must NEVER collapse to ₹0!
        """
        dest, expensive_hotel, cheap_hotel, pkg, session = _seed_shimla_environment(db)

        res = client.post("/packages/select", json={
            "session_id": session.session_id,
            "destination_id": dest.id,
            "package_id": pkg.id,
        })
        assert res.status_code == 200
        data = res.json()
        budget = data["plan"]["budget"]
        breakdown = budget["breakdown"]

        # Package must be accounted for exactly once
        assert breakdown.get("package") == 8500
        assert breakdown["hotel"] == 19000
        assert breakdown["emergency_reserve"] == 3000

        # CRITICAL REGRESSION: Transportation, food, activities, misc MUST NOT BE ZERO!
        assert breakdown["transportation"] > 0, f"Expected non-zero transportation, got {breakdown['transportation']}"
        assert breakdown["food"] > 0, f"Expected non-zero food, got {breakdown['food']}"
        assert breakdown["activities"] > 0, f"Expected non-zero activities, got {breakdown['activities']}"
        assert breakdown["miscellaneous"] > 0, f"Expected non-zero misc, got {breakdown['miscellaneous']}"

        # Status must correctly indicate Over Budget
        assert budget["status"] == "Over Budget"
        assert budget["remaining_budget"] < 0
        assert budget["estimated_total"] == sum(breakdown.values())
        assert len(budget["alternative_hotels"]) > 0, "Must recommend cheaper alternative hotels when over budget"

    def test_selecting_cheaper_hotel_recalculates_budget_and_updates_status(self, db, client):
        """
        After selecting a cheaper hotel (Shimla Budget Inn: 1800/night * 5 = 9,000),
        budget recalculates, flexible costs absorb the remaining budget, and status transitions.
        """
        dest, expensive_hotel, cheap_hotel, pkg, session = _seed_shimla_environment(db)

        # 1. First select package (putting the plan into over-budget state with expensive hotel)
        client.post("/packages/select", json={
            "session_id": session.session_id,
            "destination_id": dest.id,
            "package_id": pkg.id,
        })

        # 2. Now select cheaper hotel (Shimla Budget Inn: 1800/night * 5 = 9000)
        res = client.post("/hotels/select", json={
            "session_id": session.session_id,
            "destination_id": dest.id,
            "hotel_id": cheap_hotel.id,
        })
        assert res.status_code == 200
        data = res.json()
        budget = data["plan"]["budget"]
        breakdown = budget["breakdown"]

        # Hotel cost should now be 9000
        assert breakdown["hotel"] == 9000
        assert breakdown["package"] == 8500
        assert breakdown["emergency_reserve"] == 3000

        # Flexible costs should be positive and non-zero
        assert breakdown["transportation"] > 0
        assert breakdown["food"] > 0
        assert breakdown["activities"] > 0
        assert breakdown["miscellaneous"] > 0

        # Estimated total must equal total budget (₹30,000)
        assert budget["estimated_total"] == 30000
        assert budget["remaining_budget"] == 0
        assert budget["status"] in ("Within Budget", "Near Budget Limit")
        assert budget["cost_per_traveler"] == 15000
        assert budget["cost_per_day"] == 6000

        # Verify DB persistence
        db.expire_all()
        reloaded = db.query(ConversationSession).filter(
            ConversationSession.session_id == session.session_id
        ).first()
        saved_budget = reloaded.generated_plan["budget"]
        assert saved_budget["breakdown"]["hotel"] == 9000
        assert saved_budget["estimated_total"] == 30000

    def test_over_budget_scenario_with_low_total_budget(self, db):
        """When user has a low budget (₹15,000) for 5 days 2 travelers, estimates remain non-zero and Over Budget is flagged."""
        dest, expensive_hotel, cheap_hotel, pkg, session = _seed_shimla_environment(db)

        slots = {"budget": "15000", "travel_style": "relaxing", "duration_days": 5, "travelers": 2}
        budget = allocate_budget(
            db,
            slots=slots,
            duration_days=5,
            travelers=2,
            destination_id=dest.id,
            selected_hotel={"id": expensive_hotel.id, "name": expensive_hotel.name, "price_per_night": 3800.0},
        )

        breakdown = budget["breakdown"]
        assert breakdown["hotel"] == 19000
        assert breakdown["emergency_reserve"] == 1500
        assert breakdown["transportation"] > 0
        assert breakdown["food"] > 0
        assert breakdown["activities"] > 0
        assert breakdown["miscellaneous"] > 0

        assert budget["status"] == "Over Budget"
        assert budget["remaining_budget"] < 0
        assert budget["estimated_total"] == sum(breakdown.values())
        assert budget["cost_per_traveler"] == round(budget["estimated_total"] / 2)
        assert budget["cost_per_day"] == round(budget["estimated_total"] / 5)

    def test_package_including_hotel_avoids_double_charging_accommodation(self, db):
        """When package explicitly includes hotel accommodation, separate hotel is not charged."""
        dest, expensive_hotel, cheap_hotel, pkg, session = _seed_shimla_environment(db)

        all_in_one_pkg = {
            "id": 999,
            "title": "Shimla Luxury All-Inclusive Stay & Tour",
            "price_per_package": 25000.0,
            "amenities": "Hotel stay included,Breakfast,Guided tours",
            "description": "5-day package including stay at 4-star resort with sightseeing.",
            "includes_hotel": True,
        }

        slots = {"budget": "40000", "travel_style": "luxury", "duration_days": 5, "travelers": 2}
        budget = allocate_budget(
            db,
            slots=slots,
            duration_days=5,
            travelers=2,
            destination_id=dest.id,
            selected_package=all_in_one_pkg,
        )

        breakdown = budget["breakdown"]
        assert breakdown["hotel"] == 0, "Hotel stay already included in package, should not be double-charged"
        assert breakdown["package"] == 25000
        assert breakdown["transportation"] > 0
        assert breakdown["food"] > 0
        assert breakdown["activities"] > 0
        assert breakdown["miscellaneous"] > 0
        assert budget["estimated_total"] == sum(breakdown.values())
