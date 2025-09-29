from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from .db import Base


class Visitor(Base):
    __tablename__ = "visitors"

    id = Column(Integer, primary_key=True, index=True)
    global_id = Column(String(64), unique=True, index=True, nullable=False)
    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    visits = relationship("VisitEvent", back_populates="visitor", cascade="all, delete-orphan")
    activities = relationship("ActivityEvent", back_populates="visitor", cascade="all, delete-orphan")


class VisitEvent(Base):
    __tablename__ = "visit_events"

    id = Column(Integer, primary_key=True, index=True)
    visitor_id = Column(Integer, ForeignKey("visitors.id"), nullable=False)
    camera_id = Column(String(64), index=True, nullable=False)
    in_time = Column(DateTime, nullable=False)
    out_time = Column(DateTime, nullable=True)

    visitor = relationship("Visitor", back_populates="visits")

    __table_args__ = (
        Index("idx_visit_visitor_camera", "visitor_id", "camera_id"),
    )


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id = Column(Integer, primary_key=True, index=True)
    visitor_id = Column(Integer, ForeignKey("visitors.id"), nullable=False)
    zone = Column(String(64), index=True, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    dwell_seconds = Column(Float, default=0.0)

    visitor = relationship("Visitor", back_populates="activities")


