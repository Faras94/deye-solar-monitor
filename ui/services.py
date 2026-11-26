"""Shared backend bridge, database session helpers, and DeyeCloud client wiring for Streamlit."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, List, Optional

import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

# Load .env before importing backend settings so relative SQLite paths resolve to backend/deye_solar.db
load_dotenv(ROOT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")

# If deployed on Streamlit Community Cloud, load from st.secrets into os.environ
try:
    for _k, _v in getattr(st, "secrets", {}).items():
        if isinstance(_v, (str, int, float, bool)):
            os.environ.setdefault(_k, str(_v))
            os.environ.setdefault(_k.upper(), str(_v))
except Exception:
    pass

_raw_db_url = os.environ.get("DATABASE_URL", "sqlite:///./deye_solar.db")
if _raw_db_url.startswith("sqlite:///./"):
    _rel_path = _raw_db_url.removeprefix("sqlite:///./")
    _abs_db = (BACKEND_DIR / _rel_path).resolve()
    os.environ["DATABASE_URL"] = f"sqlite:///{_abs_db}"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.clients.deye_client import DeyeCloudClient  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.logging_utils import configure_logging  # noqa: E402
from app.models import ApiCallLog, SyncLog, TokenCache  # noqa: E402
from app.schemas import (  # noqa: E402
    ApiCallLogOut,
    ApiEndpointCount,
    ApiUsageResponse,
    CollectResponse,
    DeviceOut,
    DiscoverResponse,
    HealthResponse,
    HistoryFetchResponse,
    HistoryQueryResponse,
    LiveDashboardResponse,
    MappingsListResponse,
    MappingUpdateItem,
)
from app.services.collector_service import (  # noqa: E402
    collect_live_data,
    discover_devices,
    ensure_configured_devices,
    get_live_dashboard,
    list_devices,
)
from app.services.history_service import fetch_and_store_history, query_history  # noqa: E402
from app.services.mapping_service import (  # noqa: E402
    ensure_default_mappings,
    get_mappings_response,
    update_mappings,
)

# Shared domain constants matching the solar array setup
IST = timezone(timedelta(hours=5, minutes=30), name="IST")
INVERTER_COLORS = ["#f59e0b", "#10b981", "#0ea5e9", "#8b5cf6"]

CONNECTED_CHANNELS: dict[str, list[int]] = {
    "260605A076": [2, 3, 4],  # PV1 has no panel connected
    "260603A1D5": [1, 2, 3, 4],  # All 4 panels connected
    "260505A373": [2],  # PV1 has no panel connected (1 panel on PV2)
}

RATED_CAPACITY_W: dict[str, int] = {
    "260605A076": 2200,
    "260603A1D5": 2200,
    "260505A373": 1000,
}

CO2_KG_PER_KWH = 0.82  # India CEA grid emission factor


@contextmanager
def get_db_session() -> Iterator[Session]:
    """Yield a SQLAlchemy session and ensure it closes cleanly."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@st.cache_resource
def init_app_resources() -> DeyeCloudClient:
    """Initialize SQLite tables, default mappings, logging, and a shared DeyeCloudClient."""
    settings: Settings = get_settings()
    configure_logging(
        level=settings.log_level,
        extra_secrets=[settings.deye_app_secret, settings.deye_password],
    )

    Base.metadata.create_all(bind=engine)
    with get_db_session() as db:
        ensure_configured_devices(db, settings.configured_device_sns)
        ensure_default_mappings(db)

    cache_key = f"{settings.deye_base_url}|{settings.deye_app_id}"

    def _load_token():
        with get_db_session() as s:
            row = s.query(TokenCache).filter(TokenCache.cache_key == cache_key).first()
            return (row.access_token, row.expires_at_epoch) if row else None

    def _save_token(token: str, expires_at_epoch: float) -> None:
        with get_db_session() as s:
            row = s.query(TokenCache).filter(TokenCache.cache_key == cache_key).first()
            if row:
                row.access_token = token
                row.expires_at_epoch = expires_at_epoch
            else:
                s.add(
                    TokenCache(
                        cache_key=cache_key,
                        access_token=token,
                        expires_at_epoch=expires_at_epoch,
                    )
                )
            s.commit()

    def _log_api_call(
        method: str,
        endpoint: str,
        status_code: int | None,
        success: bool,
        duration_ms: float,
        error_message: str | None,
    ) -> None:
        with get_db_session() as s:
            s.add(
                ApiCallLog(
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code,
                    success=1 if success else 0,
                    duration_ms=duration_ms,
                    error_message=error_message,
                )
            )
            s.commit()

    return DeyeCloudClient(
        base_url=settings.deye_base_url,
        app_id=settings.deye_app_id,
        app_secret=settings.deye_app_secret,
        email=settings.deye_email,
        password=settings.deye_password,
        company_id=settings.deye_company_id,
        timeout_seconds=settings.api_timeout_seconds,
        token_loader=_load_token,
        token_saver=_save_token,
        call_logger=_log_api_call,
    )


def format_local_time(dt: Optional[datetime | str]) -> str:
    """Format a UTC datetime or ISO string into Indian Standard Time (IST)."""
    if dt is None:
        return "Never"
    if isinstance(dt, str):
        raw = dt.strip()
        if not raw:
            return "Never"
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw
    else:
        parsed = dt
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    ist_dt = parsed.astimezone(IST)
    return ist_dt.strftime("%b %d, %Y %I:%M:%S %p")


def get_health_summary() -> HealthResponse:
    settings = get_settings()
    db_status = "ok"
    with get_db_session() as db:
        try:
            db.execute(text("SELECT 1"))
        except Exception:
            db_status = "error"

        last_sync = db.scalar(select(SyncLog).order_by(SyncLog.id.desc()).limit(1))
        last_success = db.scalar(
            select(SyncLog)
            .where(SyncLog.status.in_(["success", "partial"]))
            .order_by(SyncLog.id.desc())
            .limit(1)
        )

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        credentials_configured=settings.has_credentials,
        base_url=settings.deye_base_url,
        configured_devices=settings.configured_device_sns,
        poll_interval_minutes=settings.poll_interval_minutes,
        last_sync_at=last_success.created_at if last_success else None,
        last_sync_status=last_sync.status if last_sync else None,
        last_error=last_sync.message if last_sync and last_sync.status == "error" else None,
    )


def fetch_live_dashboard() -> LiveDashboardResponse:
    settings = get_settings()
    with get_db_session() as db:
        return get_live_dashboard(db, settings.configured_device_sns)


def trigger_collect_live() -> CollectResponse:
    settings = get_settings()
    client = init_app_resources()
    with get_db_session() as db:
        return collect_live_data(db, client, settings.configured_device_sns)


def trigger_discover_devices() -> DiscoverResponse:
    settings = get_settings()
    client = init_app_resources()
    with get_db_session() as db:
        return discover_devices(db, client, settings.configured_device_sns)


def fetch_devices() -> List[DeviceOut]:
    settings = get_settings()
    with get_db_session() as db:
        return list_devices(db, settings.configured_device_sns)


def fetch_history(
    granularity: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    device_sns: Optional[List[str]] = None,
) -> HistoryQueryResponse:
    with get_db_session() as db:
        return query_history(
            db=db,
            granularity=granularity,
            start_date=start_date,
            end_date=end_date,
            device_sns=device_sns,
        )


def trigger_fetch_history(
    start_date: str,
    end_date: str,
    granularity: str,
    target_sns: Optional[List[str]] = None,
) -> HistoryFetchResponse:
    settings = get_settings()
    client = init_app_resources()
    with get_db_session() as db:
        return fetch_and_store_history(
            db=db,
            client=client,
            configured_sns=settings.configured_device_sns,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            target_sns=target_sns,
        )


def fetch_mappings() -> MappingsListResponse:
    with get_db_session() as db:
        return get_mappings_response(db)


def save_mappings(items: List[MappingUpdateItem]) -> MappingsListResponse:
    with get_db_session() as db:
        return update_mappings(db, items)


def fetch_api_usage(limit: int = 150) -> ApiUsageResponse:
    with get_db_session() as db:
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc.astimezone(IST)
        start_of_day_utc = now_ist.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(
            timezone.utc
        )
        start_of_month_utc = now_ist.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).astimezone(timezone.utc)
        one_minute_ago = now_utc - timedelta(minutes=1)

        total_calls = db.scalar(select(func.count(ApiCallLog.id))) or 0
        calls_today = (
            db.scalar(
                select(func.count(ApiCallLog.id)).where(ApiCallLog.created_at >= start_of_day_utc)
            )
            or 0
        )
        calls_this_month = (
            db.scalar(
                select(func.count(ApiCallLog.id)).where(
                    ApiCallLog.created_at >= start_of_month_utc
                )
            )
            or 0
        )
        calls_last_minute = (
            db.scalar(
                select(func.count(ApiCallLog.id)).where(ApiCallLog.created_at >= one_minute_ago)
            )
            or 0
        )
        success_calls = (
            db.scalar(select(func.count(ApiCallLog.id)).where(ApiCallLog.success == 1)) or 0
        )
        error_calls = total_calls - success_calls

        endpoint_rows = db.execute(
            select(
                ApiCallLog.endpoint,
                func.count(ApiCallLog.id).label("total"),
                func.sum(ApiCallLog.success).label("ok"),
                func.avg(ApiCallLog.duration_ms).label("avg_ms"),
                func.max(ApiCallLog.created_at).label("last_at"),
            )
            .group_by(ApiCallLog.endpoint)
            .order_by(func.count(ApiCallLog.id).desc())
        ).all()

        endpoints = [
            ApiEndpointCount(
                endpoint=row.endpoint,
                total_calls=int(row.total or 0),
                success_calls=int(row.ok or 0),
                error_calls=int(row.total or 0) - int(row.ok or 0),
                avg_duration_ms=round(float(row.avg_ms or 0.0), 1),
                last_called_at=row.last_at,
            )
            for row in endpoint_rows
        ]

        recent_rows = db.scalars(
            select(ApiCallLog).order_by(ApiCallLog.id.desc()).limit(limit)
        ).all()

        recent_calls = [
            ApiCallLogOut(
                id=r.id,
                method=r.method,
                endpoint=r.endpoint,
                status_code=r.status_code,
                success=bool(r.success),
                duration_ms=r.duration_ms,
                error_message=r.error_message,
                created_at=r.created_at,
            )
            for r in recent_rows
        ]

        return ApiUsageResponse(
            total_calls=total_calls,
            calls_today=calls_today,
            calls_this_month=calls_this_month,
            calls_last_minute=calls_last_minute,
            success_calls=success_calls,
            error_calls=error_calls,
            endpoints=endpoints,
            recent_calls=recent_calls,
        )
