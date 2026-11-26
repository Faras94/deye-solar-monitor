"""Pydantic schemas for FastAPI request and response payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, Field, PlainSerializer


def _serialize_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


UTCDatetime = Annotated[datetime, PlainSerializer(_serialize_utc, return_type=str)]


class HealthResponse(BaseModel):
    status: str
    database: str
    credentials_configured: bool
    base_url: str
    configured_devices: List[str]
    poll_interval_minutes: int
    last_sync_at: Optional[UTCDatetime] = None
    last_sync_status: Optional[str] = None
    last_error: Optional[str] = None


class AvailablePoint(BaseModel):
    key: str
    name: Optional[str] = None
    unit: Optional[str] = None


class DeviceOut(BaseModel):
    device_sn: str
    name: str
    device_type: str
    station_id: Optional[int] = None
    status: str
    collection_time: Optional[str] = None
    last_seen_at: Optional[UTCDatetime] = None
    available_points: List[AvailablePoint] = Field(default_factory=list)


class PVChannelReading(BaseModel):
    channel: int
    voltage: Optional[float] = None
    current: Optional[float] = None
    power: Optional[float] = None
    energy: Optional[float] = None
    voltage_unit: Optional[str] = None
    current_unit: Optional[str] = None
    power_unit: Optional[str] = None
    energy_unit: Optional[str] = None


class RawMeasurementPoint(BaseModel):
    key: str
    value: Optional[Any] = None
    unit: Optional[str] = None
    name: Optional[str] = None


class InverterLiveOut(BaseModel):
    device_sn: str
    name: str
    status: str
    collection_time: Optional[str] = None
    last_seen_at: Optional[UTCDatetime] = None
    rated_power_w: Optional[float] = None
    current_power_w: Optional[float] = None
    daily_energy_kwh: Optional[float] = None
    monthly_energy_kwh: Optional[float] = None
    total_energy_kwh: Optional[float] = None
    ac_voltage_v: Optional[float] = None
    ac_current_a: Optional[float] = None
    ac_frequency_hz: Optional[float] = None
    temperature_c: Optional[float] = None
    pv_inputs: List[PVChannelReading] = Field(default_factory=list)
    raw_points: List[RawMeasurementPoint] = Field(default_factory=list)


class LiveSummary(BaseModel):
    total_current_power_w: Optional[float] = None
    total_daily_energy_kwh: Optional[float] = None
    total_monthly_energy_kwh: Optional[float] = None
    total_lifetime_energy_kwh: Optional[float] = None
    online_count: int = 0
    offline_count: int = 0
    total_devices: int = 0


class LiveDashboardResponse(BaseModel):
    summary: LiveSummary
    inverters: List[InverterLiveOut]
    last_sync_at: Optional[UTCDatetime] = None
    last_sync_status: Optional[str] = None
    last_error: Optional[str] = None


class CollectResponse(BaseModel):
    status: str
    message: str
    devices_updated: int
    synced_at: UTCDatetime
    errors: List[str] = Field(default_factory=list)


class DiscoverResponse(BaseModel):
    status: str
    message: str
    discovered_devices: List[DeviceOut]
    errors: List[str] = Field(default_factory=list)


class HistoricalPointOut(BaseModel):
    device_sn: str
    granularity: str
    period_key: str
    energy_kwh: Optional[float] = None
    power_w: Optional[float] = None


class HistoryQueryResponse(BaseModel):
    granularity: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    records: List[HistoricalPointOut]


class HistoryFetchRequest(BaseModel):
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    granularity: str = Field(default="daily", pattern=r"^(intraday|daily|monthly|yearly)$")
    device_sns: Optional[List[str]] = None


class HistoryFetchResponse(BaseModel):
    status: str
    message: str
    records_saved: int
    errors: List[str] = Field(default_factory=list)


class MappingOut(BaseModel):
    dashboard_field: str
    deye_key: Optional[str] = None
    label: str
    unit: Optional[str] = None
    category: str


class MappingsListResponse(BaseModel):
    mappings: List[MappingOut]
    unmapped_points: List[AvailablePoint]
    available_points: List[AvailablePoint]


class MappingUpdateItem(BaseModel):
    dashboard_field: str
    deye_key: Optional[str] = None


class MappingsUpdateRequest(BaseModel):
    mappings: List[MappingUpdateItem]


class SchedulerConfigOut(BaseModel):
    enabled: bool
    interval_minutes: int


class SchedulerConfigUpdate(BaseModel):
    enabled: bool
    interval_minutes: int = Field(default=5, ge=1, le=120)


class ApiCallLogOut(BaseModel):
    id: int
    method: str
    endpoint: str
    status_code: Optional[int] = None
    success: bool
    duration_ms: float
    error_message: Optional[str] = None
    created_at: UTCDatetime


class ApiEndpointCount(BaseModel):
    endpoint: str
    total_calls: int
    success_calls: int
    error_calls: int
    avg_duration_ms: float
    last_called_at: Optional[UTCDatetime] = None


class ApiUsageResponse(BaseModel):
    total_calls: int
    calls_today: int
    calls_this_month: int
    calls_last_minute: int
    monthly_quota: int = 100000
    qpm_limit: int = 60
    success_calls: int
    error_calls: int
    endpoints: List[ApiEndpointCount]
    recent_calls: List[ApiCallLogOut]
