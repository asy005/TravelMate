from sqlalchemy import Column, Integer, String, Text, Float
from ..database import Base

class Destination(Base):
    __tablename__ = "destinations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False)
    country = Column(String(128), nullable=True)
    description = Column(Text, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    tags = Column(String(512), nullable=True)
    thumbnail_url = Column(String(512), nullable=True)
    avg_rating = Column(Float, default=5.0)

    # Extended dataset columns
    csv_destination_id = Column(String(32), nullable=True, index=True)
    state = Column(String(128), nullable=True)
    city = Column(String(128), nullable=True)
    category = Column(String(64), nullable=True)
    best_season = Column(String(64), nullable=True)
    average_budget = Column(Float, nullable=True)
    ideal_duration = Column(Integer, nullable=True)
