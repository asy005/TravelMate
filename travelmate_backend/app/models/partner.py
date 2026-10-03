# app/models/partner.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

# Generic across all current and future partner types. Kept as a single
# table with a `partner_type` discriminator rather than a table-per-type --
# the fields a *business* needs (name, contact, status) don't vary by type;
# only their *listings* do (handled separately, see listing_service.py).
PARTNER_TYPES = ["hotel", "homestay", "resort", "travel_agency", "tour_operator", "local_guide"]


class Partner(Base):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    business_name = Column(String(256), nullable=False)
    partner_type = Column(String(32), nullable=False)  # one of PARTNER_TYPES
    contact_email = Column(String(256), nullable=True)
    contact_phone = Column(String(64), nullable=True)
    description = Column(String(1024), nullable=True)

    # No admin-approval workflow yet (that's part of the Admin Dashboard
    # module) -- partners are auto-approved so they aren't blocked with no
    # way to unblock themselves. Field exists so approval can be added later
    # without a schema change.
    status = Column(String(32), nullable=False, default="approved")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
