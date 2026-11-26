"""FastAPI REST API endpoints for Deye Solar Monitoring."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.clients.deye_client import DeyeCloudClient
from app.config import Settings, get_settings
from app.database import get_db
from app.models import ApiCallLog, SyncLog
from app.schemas import (
    ApiCallLogOut,
    ApiEndpointCount,
    ApiUsageResponse,
    CollectResponse,
    DeviceOut,
    DiscoverResponse,
    HealthResponse,
    HistoryFetchRequest,
    HistoryFetchResponse,
    HistoryQueryResponse,
    LiveDashboardResponse,
    MappingsListResponse,
    MappingsUpdateRequest,
    SchedulerConfigOut,
    SchedulerConfigUpdate,
)
from app.services.collector_service import (
    collect_live_data,
    discover_devices,
    get_live_dashboard,
    list_devices,
)
from app.services.history_service import fetch_and_store_history, query_history
from app.services.mapping_service import get_mappings_response, update_mappings

router = APIRouter(prefix="/api", tags=["solar-monitoring"])


def get_deye_client(request: Request) -> DeyeCloudClient:
    """Dependency returning the shared DeyeCloudClient stored on app.state."""
    return request.app.state.deye_client


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Return backend health, DB connectivity, and latest synchronization state."""
    db_status = "ok"
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


@router.get("/devices", response_model=List[DeviceOut])
def get_devices(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> List[DeviceOut]:
    """Return all configured and discovered microinverters."""
    return list_devices(db, settings.configured_device_sns)


@router.get("/live", response_model=LiveDashboardResponse)
def get_live(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LiveDashboardResponse:
    """Return latest live telemetry, PV1-PV4 readings, and summary metrics."""
    return get_live_dashboard(db, settings.configured_device_sns)


@router.post("/collect", response_model=CollectResponse)
def trigger_collect(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: DeyeCloudClient = Depends(get_deye_client),
) -> CollectResponse:
    """Manually trigger live telemetry collection from DeyeCloud."""
    return collect_live_data(db, client, settings.configured_device_sns)


@router.post("/discover", response_model=DiscoverResponse)
def trigger_discover(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: DeyeCloudClient = Depends(get_deye_client),
) -> DiscoverResponse:
    """Discover stations, devices, and supported DeyeCloud measurePoints."""
    return discover_devices(db, client, settings.configured_device_sns)


@router.get("/history", response_model=HistoryQueryResponse)
def get_history(
    granularity: str = Query(default="daily", pattern=r"^(intraday|daily|monthly|yearly)$"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    device_sn: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> HistoryQueryResponse:
    """Query historical generation readings stored in SQLite."""
    sns = [s.strip() for s in device_sn.split(",") if s.strip()] if device_sn else None
    return query_history(
        db=db,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        device_sns=sns,
    )


@router.post("/history/fetch", response_model=HistoryFetchResponse)
def fetch_history(
    payload: HistoryFetchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: DeyeCloudClient = Depends(get_deye_client),
) -> HistoryFetchResponse:
    """Fetch historical telemetry from DeyeCloud and store it in SQLite."""
    return fetch_and_store_history(
        db=db,
        client=client,
        configured_sns=settings.configured_device_sns,
        start_date=payload.start_date,
        end_date=payload.end_date,
        granularity=payload.granularity,
        target_sns=payload.device_sns,
    )


@router.get("/mappings", response_model=MappingsListResponse)
def get_mappings(db: Session = Depends(get_db)) -> MappingsListResponse:
    """Return measurement field mappings, discovered points, and unmapped points."""
    return get_mappings_response(db)


@router.post("/mappings", response_model=MappingsListResponse)
def save_mappings(
    payload: MappingsUpdateRequest,
    db: Session = Depends(get_db),
) -> MappingsListResponse:
    """Update measurement field mappings."""
    return update_mappings(db, payload.mappings)


@router.get("/scheduler", response_model=SchedulerConfigOut)
def get_scheduler_config(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> SchedulerConfigOut:
    """Return current auto-refresh enabled state and polling interval in minutes."""
    enabled = getattr(request.app.state, "auto_refresh_enabled", False)
    interval = getattr(request.app.state, "poll_interval_minutes", settings.poll_interval_minutes)
    return SchedulerConfigOut(enabled=enabled, interval_minutes=interval)


@router.post("/scheduler", response_model=SchedulerConfigOut)
def update_scheduler_config(
    payload: SchedulerConfigUpdate,
    request: Request,
) -> SchedulerConfigOut:
    """Enable/disable background auto-refresh and update polling interval in minutes."""
    scheduler = getattr(request.app.state, "scheduler", None)
    collect_fn = getattr(request.app.state, "scheduled_collect_fn", None)

    request.app.state.auto_refresh_enabled = payload.enabled
    request.app.state.poll_interval_minutes = payload.interval_minutes

    if scheduler is not None and collect_fn is not None:
        if payload.enabled:
            scheduler.add_job(
                collect_fn,
                trigger="interval",
                minutes=payload.interval_minutes,
                args=[request.app],
                id="deye_live_collector",
                replace_existing=True,
            )
        else:
            if scheduler.get_job("deye_live_collector") is not None:
                scheduler.remove_job("deye_live_collector")

    return SchedulerConfigOut(
        enabled=payload.enabled,
        interval_minutes=payload.interval_minutes,
    )


@router.get("/usage", response_model=ApiUsageResponse)
def get_api_usage(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ApiUsageResponse:
    """Return DeyeCloud API call counts, quota usage, endpoint stats, and recent call logs."""
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    one_minute_ago = now - timedelta(minutes=1)

    total_calls = db.scalar(select(func.count(ApiCallLog.id))) or 0
    calls_today = (
        db.scalar(select(func.count(ApiCallLog.id)).where(ApiCallLog.created_at >= start_of_day))
        or 0
    )
    calls_this_month = (
        db.scalar(select(func.count(ApiCallLog.id)).where(ApiCallLog.created_at >= start_of_month))
        or 0
    )
    calls_last_minute = (
        db.scalar(select(func.count(ApiCallLog.id)).where(ApiCallLog.created_at >= one_minute_ago))
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
