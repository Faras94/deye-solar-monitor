"""SQLAlchemy ORM models for Deye Solar Monitoring."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Device(Base):
    """Configured or discovered Deye microinverter."""

    __tablename__ = "devices"

    device_sn: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_type: Mapped[str] = mapped_column(String(64), default="MICRO_INVERTER")
    station_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    collection_time: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    available_points_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MeasurementSnapshot(Base):
    """Latest and historical live telemetry snapshots per inverter."""

    __tablename__ = "measurement_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_sn: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    collection_time: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    normalized_json: Mapped[str] = mapped_column(Text, nullable=False)
    raw_points_json: Mapped[str] = mapped_column(Text, nullable=False)


class HistoricalReading(Base):
    """Bucketed historical energy readings (daily, monthly, yearly) stored in SQLite."""

    __tablename__ = "historical_readings"
    __table_args__ = (
        UniqueConstraint("device_sn", "granularity", "period_key", name="uq_history_device_gran_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_sn: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    granularity: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # daily | monthly | yearly
    period_key: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    energy_kwh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    power_w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MeasurementMapping(Base):
    """Configurable mapping from DeyeCloud measurement keys to dashboard fields."""

    __tablename__ = "measurement_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dashboard_field: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    deye_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    category: Mapped[str] = mapped_column(String(32), default="inverter")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SyncLog(Base):
    """Audit log of API synchronization attempts, successes, and sanitized errors."""

    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sync_type: Mapped[str] = mapped_column(String(32), nullable=False)  # live | discover | history
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # success | partial | error
    message: Mapped[str] = mapped_column(Text, nullable=False)
    devices_updated: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class TokenCache(Base):
    """Persists 60-day DeyeCloud access tokens across server restarts."""

    __tablename__ = "token_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at_epoch: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ApiCallLog(Base):
    """Audit log of every outbound DeyeCloud API request."""

    __tablename__ = "api_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="POST")
    endpoint: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    success: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 1=ok, 0=error
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
