# app/models/conversation.py
from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    messages = Column(JSON, default=list)         # [{"role": "...", "content": "...", "ts": "..."}]
    slots = Column(JSON, default=dict)             # {"origin": ..., "budget": ..., ...}
    status = Column(String(32), default="collecting")  # collecting | ready | completed
    generated_plan = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
