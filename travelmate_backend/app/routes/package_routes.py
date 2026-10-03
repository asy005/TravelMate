# app/routes/package_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.package import Package
from app.models.partner import Partner
from app.models.destination import Destination
from app.models.conversation import ConversationSession
from app.services.budget_optimizer import allocate_budget
from app.services.plan_orchestrator import itinerary_with_package

router = APIRouter(prefix="/packages", tags=["packages"])


class SelectPackageIn(BaseModel):
    session_id: str
    destination_id: int
    package_id: int


def _serialize_package(pkg: Package, db: Session):
    partner = db.query(Partner).filter(Partner.id == pkg.partner_id).first()
    return {
        "id": pkg.id,
        "title": pkg.title,
        "description": pkg.description,
        "category": pkg.category,
        "duration_days": pkg.duration_days,
        "capacity": pkg.capacity,
        "price_tier": pkg.price_tier,
        "price_per_package": pkg.price_per_package,
        "rating": pkg.rating,
        "amenities": (pkg.amenities or "").split(",") if pkg.amenities else [],
        "thumbnail_url": pkg.thumbnail_url,
        "photos": pkg.photos or [],
        "partner_name": partner.business_name if partner else None,
    }


@router.get("/{package_id}")
def get_package_details(package_id: int, db: Session = Depends(get_db)):
    pkg = db.query(Package).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    return _serialize_package(pkg, db)


@router.post("/select")
def select_package(payload: SelectPackageIn, db: Session = Depends(get_db)):
    """
    Mirrors /hotels/select -- updates the AI-generated plan with the chosen
    package, then recomputes budget AND itinerary (packages change trip
    length/structure in a way hotel selection doesn't). No package booking
    yet, per scope.
    """
    session = db.query(ConversationSession).filter(
        ConversationSession.session_id == payload.session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pkg = db.query(Package).filter(Package.id == payload.package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    plan = session.generated_plan
    if not plan:
        raise HTTPException(status_code=400, detail="This session has no generated plan yet")

    dest = db.query(Destination).filter(Destination.id == payload.destination_id).first()
    package_dict = _serialize_package(pkg, db)

    updated = False
    for dest_block in plan.get("destinations", []):
        if dest_block.get("id") == payload.destination_id:
            dest_block["selected_package"] = package_dict
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Destination not found in this plan")

    slots = session.slots or {}
    duration_days = slots.get("duration_days") or 3
    travelers = slots.get("travelers") or 1

    # Budget: same single source of truth used everywhere else.
    plan["budget"] = allocate_budget(
        db, slots, duration_days, travelers,
        destination_id=payload.destination_id,
        selected_hotel=next(
            (d.get("selected_hotel") for d in plan.get("destinations", []) if d.get("id") == payload.destination_id),
            None,
        ),
        selected_package=package_dict,
    )

    # Itinerary: regenerated to reflect the package now driving the trip.
    plan["day_wise_itinerary"] = itinerary_with_package(
        dest.name if dest else "your destination", duration_days, package_dict
    )

    session.generated_plan = plan
    db.add(session)
    db.commit()
    db.refresh(session)

    return {"msg": "Package selected", "plan": session.generated_plan}
