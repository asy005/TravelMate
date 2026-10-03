from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship   # ← THIS WAS MISSING
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String, nullable=False)

    # Profile fields (M2)
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    home_city = Column(String, nullable=True)
    preferred_language = Column(String, nullable=True, default="en")
    preferred_currency = Column(String, nullable=True, default="INR")

    # RBAC (M2) -- simple string role for now; a full roles/permissions
    # table is deferred until the Partner Portal module needs finer scoping.
    role = Column(String, nullable=False, default="customer")

    # relation to favorites
    favorites = relationship("Favorite", back_populates="user")
