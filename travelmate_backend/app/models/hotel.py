# app/models/hotel.py
from sqlalchemy import Column, Integer, String, Float, Text, JSON, ForeignKey
from app.database import Base


class Hotel(Base):
    __tablename__ = "hotels"

    id = Column(Integer, primary_key=True, index=True)
    destination_id = Column(Integer, ForeignKey("destinations.id"), nullable=False, index=True)
    partner_id = Column(Integer, ForeignKey("partners.id"), nullable=True, index=True)  # null = platform-seeded, no owner yet

    name = Column(String(256), nullable=False)
    partner_name = Column(String(256), nullable=True)  # legacy display label, kept for backward compatibility
    accommodation_type = Column(String(64), nullable=True)  # hotel | homestay | resort | boutique
    price_tier = Column(String(32), nullable=False, default="medium")  # low | medium | luxury
    price_per_night = Column(Float, nullable=True)
    star_rating = Column(Float, nullable=True)
    amenities = Column(String(512), nullable=True)  # comma-separated
    thumbnail_url = Column(String(512), nullable=True)

    description = Column(Text, nullable=True)
    photos = Column(JSON, nullable=True)  # list of photo URLs
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
