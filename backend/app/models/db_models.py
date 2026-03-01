from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    runs = relationship("Run", back_populates="owner", cascade="all, delete-orphan")


class Run(Base):
    __tablename__ = "runs"

    run_id = Column(String(64), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    method_id = Column(String(64), nullable=True)
    dataset_id = Column(String(64), nullable=True)
    metrics = Column(JSON, nullable=True, default=list)
    results = Column(JSON, nullable=True)
    duration = Column(Float, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    # Backward-compatible fields
    method_key = Column(String(64), nullable=False)
    dataset_key = Column(String(64), nullable=False)
    metric_keys = Column(JSON, nullable=False, default=list)
    seed = Column(Integer, nullable=False, default=42)
    params = Column(JSON, nullable=False, default=dict)
    status = Column(String(16), nullable=False, default="pending")
    logs = Column(JSON, nullable=False, default=list)
    duration_sec = Column(Float, nullable=True)
    metrics_result = Column(JSON, nullable=True)
    error = Column(String(500), nullable=True)
    version_info = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="runs")
