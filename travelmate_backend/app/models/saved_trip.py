from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class SavedTrip(Base):
    __tablename__ = "saved_trips"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    destination_id = Column(Integer, ForeignKey("destinations.id", ondelete="SET NULL"), nullable=True, index=True)
    destination_name = Column(String(255), nullable=False)
    trip_title = Column(String(255), nullable=True)
    trip_duration_days = Column(Integer, default=3)
    travel_dates = Column(String(255), nullable=True)
    destination_data = Column(JSON, nullable=True)
    itinerary = Column(JSON, nullable=True)
    selected_attractions = Column(JSON, nullable=True)
    selected_activities = Column(JSON, nullable=True)
    route_stops = Column(JSON, nullable=True)
    route_details = Column(JSON, nullable=True)
    packing_checklist = Column(JSON, nullable=True)
    custom_packing_items = Column(JSON, nullable=True)
    trip_preferences = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="saved_trips")
