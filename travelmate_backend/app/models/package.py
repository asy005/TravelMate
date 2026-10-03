# app/models/package.py
"""
Listings offered by non-accommodation partner types (travel agencies, tour
operators, local guides). Deliberately a separate table from Hotel -- a
per-night stay and a multi-day fixed-price package have genuinely different
shapes (price-per-night + rooms vs. price-per-package + duration), and
forcing both into one polymorphic table would mean a pile of nullable
columns that only make sense for one type or the other.

The two tables are made to *behave* the same from the Partner Portal's
perspective through the shared listing_service.py abstraction, so routes and
the frontend don't need to know or care which table backs a given listing.
"""
from sqlalchemy import Column, Integer, String, Float, Text, JSON, ForeignKey
from app.database import Base


class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, index=True)
    destination_id = Column(Integer, ForeignKey("destinations.id"), nullable=False, index=True)
    partner_id = Column(Integer, ForeignKey("partners.id"), nullable=False, index=True)

    title = Column(String(256), nullable=False)
    category = Column(String(32), nullable=True)  # travel_agency | tour_operator | local_guide
    price_tier = Column(String(32), nullable=False, default="medium")
    price_per_package = Column(Float, nullable=True)
    duration_days = Column(Integer, nullable=True)
    capacity = Column(Integer, nullable=True)  # max travelers per booking
    rating = Column(Float, nullable=True)
    amenities = Column(String(512), nullable=True)  # comma-separated inclusions
    thumbnail_url = Column(String(512), nullable=True)

    description = Column(Text, nullable=True)
    photos = Column(JSON, nullable=True)
