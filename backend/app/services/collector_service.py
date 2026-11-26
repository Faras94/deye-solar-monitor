"""Device discovery, live telemetry collection, and strict measurement normalization."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.deye_client import DeyeAPIError, DeyeCloudClient
from app.models import Device, HistoricalReading, MeasurementSnapshot, SyncLog
from app.schemas import (
    AvailablePoint,
    CollectResponse,
    DeviceOut,
    DiscoverResponse,
    InverterLiveOut,
    LiveDashboardResponse,
    LiveSummary,
    PVChannelReading,
    RawMeasurementPoint,
)
from app.services.mapping_service import ensure_default_mappings, get_mapping_dict

logger = logging.getLogger(__name__)

_STATE_MAP = {
    1: "online",
    "1": "online",
    "NORMAL": "online",
    "ONLINE": "online",
    2: "alert",
    "2": "alert",
    "ALERT": "alert",
    3: "offline",
    "3": "offline",
    "OFFLINE": "offline",
}


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_status(raw_state: Any) -> str:
    if raw_state is None:
        return "unknown"
    if raw_state in _STATE_MAP:
        return _STATE_MAP[raw_state]
    upper = str(raw_state).strip().upper()
    return _STATE_MAP.get(upper, "unknown")


def ensure_configured_devices(db: Session, device_sns: List[str]) -> None:
    """Ensure all configured microinverter serial numbers exist in the devices table."""
    existing = {d.device_sn for d in db.scalars(select(Device)).all()}
    added = False
    for idx, sn in enumerate(device_sns, start=1):
        if sn not in existing:
            db.add(
                Device(
                    device_sn=sn,
                    name=f"Microinverter {idx} ({sn})",
                    device_type="MICRO_INVERTER",
                    status="unknown",
                )
            )
            added = True
    if added:
        db.commit()


def _parse_available_points(device: Device) -> List[AvailablePoint]:
    if not device.available_points_json:
        return []
    try:
        raw = json.loads(device.available_points_json)
        return [
            AvailablePoint(key=item["key"], name=item.get("name"), unit=item.get("unit"))
            for item in raw
            if isinstance(item, dict) and item.get("key")
        ]
    except ValueError:
        return []


def list_devices(db: Session, configured_sns: List[str]) -> List[DeviceOut]:
    """Return all configured/discovered devices ordered by configuration order."""
    ensure_configured_devices(db, configured_sns)
    rows = db.scalars(select(Device)).all()
    order_index = {sn: i for i, sn in enumerate(configured_sns)}
    rows.sort(key=lambda d: (order_index.get(d.device_sn, 999), d.device_sn))
    return [
        DeviceOut(
            device_sn=d.device_sn,
            name=d.name,
            device_type=d.device_type,
            station_id=d.station_id,
            status=d.status,
            collection_time=d.collection_time,
            last_seen_at=d.last_seen_at,
            available_points=_parse_available_points(d),
        )
        for d in rows
    ]


def discover_devices(
    db: Session, client: DeyeCloudClient, configured_sns: List[str]
) -> DiscoverResponse:
    """Discover station bindings, device metadata, and supported measurePoints from DeyeCloud."""
    ensure_configured_devices(db, configured_sns)
    ensure_default_mappings(db)
    errors: List[str] = []

    station_devices_by_sn: Dict[str, Dict[str, Any]] = {}
    try:
        stations = client.get_station_list()
        station_ids = [int(s["id"]) for s in stations if s.get("id") is not None]
        if station_ids:
            remote_devices = client.get_station_devices(station_ids)
            for item in remote_devices:
                sn = str(item.get("deviceSn") or "").strip()
                if sn:
                    station_devices_by_sn[sn] = item
    except DeyeAPIError as exc:
        msg = f"Station/device discovery failed: {exc}"
        logger.warning(msg)
        errors.append(msg)

    devices = db.scalars(select(Device)).all()
    for dev in devices:
        remote = station_devices_by_sn.get(dev.device_sn)
        if remote:
            dev.device_type = str(remote.get("deviceType") or dev.device_type or "MICRO_INVERTER")
            if remote.get("stationId") is not None:
                dev.station_id = int(remote["stationId"])
            if remote.get("deviceState") is not None or remote.get("connectStatus") is not None:
                dev.status = _normalize_status(remote.get("deviceState") or remote.get("connectStatus"))
            dev.raw_metadata_json = json.dumps(remote)

        try:
            points = client.get_device_measure_points(dev.device_sn, device_type=dev.device_type)
            if points:
                dev.available_points_json = json.dumps(points)
        except DeyeAPIError as exc:
            err_msg = f"MeasurePoints fetch failed for {dev.device_sn}: {exc}"
            logger.warning(err_msg)
            errors.append(err_msg)

    status = "success" if not errors else ("partial" if station_devices_by_sn else "error")
    summary_msg = (
        f"Discovered {len(station_devices_by_sn)} station device(s)."
        if not errors
        else "; ".join(errors)
    )
    db.add(
        SyncLog(
            sync_type="discover",
            status=status,
            message=summary_msg,
            devices_updated=len(station_devices_by_sn),
        )
    )
    db.commit()

    return DiscoverResponse(
        status=status,
        message=summary_msg,
        discovered_devices=list_devices(db, configured_sns),
        errors=errors,
    )


def normalize_telemetry(
    data_list: List[Dict[str, Any]], mapping: Dict[str, str]
) -> Dict[str, Any]:
    """Map raw DeyeCloud dataList points to dashboard fields without inventing missing values."""
    points_by_key: Dict[str, Dict[str, Any]] = {}
    for item in data_list:
        key = str(item.get("key") or "").strip()
        if key:
            points_by_key[key] = item

    def pick_float(field_name: str) -> Optional[float]:
        deye_key = mapping.get(field_name)
        if not deye_key:
            return None
        point = points_by_key.get(deye_key)
        if point is None:
            return None
        return _to_float(point.get("value"))

    def pick_unit(field_name: str) -> Optional[str]:
        deye_key = mapping.get(field_name)
        if not deye_key:
            return None
        point = points_by_key.get(deye_key)
        return point.get("unit") if point else None

    pv_inputs: List[Dict[str, Any]] = []
    for ch in range(1, 5):
        v = pick_float(f"pv{ch}_voltage")
        c = pick_float(f"pv{ch}_current")
        p = pick_float(f"pv{ch}_power")
        e = pick_float(f"pv{ch}_energy")
        # Strictly do NOT compute p = v * c or divide total power across PV inputs.
        # Only report what DeyeCloud explicitly returned for this PV channel.
        pv_inputs.append(
            {
                "channel": ch,
                "voltage": v,
                "current": c,
                "power": p,
                "energy": e,
                "voltage_unit": pick_unit(f"pv{ch}_voltage"),
                "current_unit": pick_unit(f"pv{ch}_current"),
                "power_unit": pick_unit(f"pv{ch}_power"),
                "energy_unit": pick_unit(f"pv{ch}_energy"),
            }
        )

    return {
        "rated_power_w": pick_float("rated_power"),
        "current_power_w": pick_float("current_power"),
        "daily_energy_kwh": pick_float("daily_energy"),
        "monthly_energy_kwh": pick_float("monthly_energy"),
        "total_energy_kwh": pick_float("total_energy"),
        "ac_voltage_v": pick_float("ac_voltage"),
        "ac_current_a": pick_float("ac_current"),
        "ac_frequency_hz": pick_float("ac_frequency"),
        "temperature_c": pick_float("temperature"),
        "pv_inputs": pv_inputs,
    }


def _upsert_today_history_from_live(
    db: Session, device_sn: str, normalized: Dict[str, Any], now: datetime
) -> None:
    daily_kwh = normalized.get("daily_energy_kwh")
    power_w = normalized.get("current_power_w")

    if power_w is not None or daily_kwh is not None:
        intraday_key = now.astimezone().strftime("%Y-%m-%d %H:%M")
        existing_intraday = db.scalar(
            select(HistoricalReading).where(
                HistoricalReading.device_sn == device_sn,
                HistoricalReading.granularity == "intraday",
                HistoricalReading.period_key == intraday_key,
            )
        )
        if existing_intraday:
            existing_intraday.energy_kwh = daily_kwh
            existing_intraday.power_w = power_w
            existing_intraday.updated_at = now
        else:
            db.add(
                HistoricalReading(
                    device_sn=device_sn,
                    granularity="intraday",
                    period_key=intraday_key,
                    energy_kwh=daily_kwh,
                    power_w=power_w,
                )
            )

    if daily_kwh is None:
        return

    period_key = now.strftime("%Y-%m-%d")
    existing = db.scalar(
        select(HistoricalReading).where(
            HistoricalReading.device_sn == device_sn,
            HistoricalReading.granularity == "daily",
            HistoricalReading.period_key == period_key,
        )
    )
    if existing:
        existing.energy_kwh = daily_kwh
        existing.power_w = power_w
        existing.updated_at = now
    else:
        db.add(
            HistoricalReading(
                device_sn=device_sn,
                granularity="daily",
                period_key=period_key,
                energy_kwh=daily_kwh,
                power_w=power_w,
            )
        )


def collect_live_data(
    db: Session, client: DeyeCloudClient, configured_sns: List[str], force: bool = False
) -> CollectResponse:
    """Fetch latest telemetry for configured microinverters and persist snapshots.

    Respects DeyeCloud best-practices by serving cached SQLite data if a successful
    live sync completed within the last 60 seconds (unless force=True).
    """
    ensure_configured_devices(db, configured_sns)
    mapping = get_mapping_dict(db)
    now = datetime.now(timezone.utc)

    if not force:
        recent_sync = db.scalar(
            select(SyncLog)
            .where(SyncLog.sync_type == "live", SyncLog.status.in_(["success", "partial"]))
            .order_by(SyncLog.id.desc())
            .limit(1)
        )
        if recent_sync and recent_sync.created_at:
            sync_ts = recent_sync.created_at
            if sync_ts.tzinfo is None:
                sync_ts = sync_ts.replace(tzinfo=timezone.utc)
            age_seconds = (now - sync_ts).total_seconds()
            if age_seconds < 60.0:
                return CollectResponse(
                    status=recent_sync.status,
                    message=f"Served from cache (last synced {int(age_seconds)}s ago; 60s cooldown).",
                    devices_updated=recent_sync.devices_updated,
                    synced_at=sync_ts,
                    errors=[],
                )

    errors: List[str] = []
    devices_updated = 0

    try:
        latest_items = client.get_device_latest(configured_sns)
    except DeyeAPIError as exc:
        err_msg = str(exc)
        logger.error("Live collection failed: %s", err_msg)
        db.add(
            SyncLog(
                sync_type="live",
                status="error",
                message=err_msg,
                devices_updated=0,
            )
        )
        db.commit()
        return CollectResponse(
            status="error",
            message=err_msg,
            devices_updated=0,
            synced_at=now,
            errors=[err_msg],
        )

    by_sn: Dict[str, Dict[str, Any]] = {
        str(item.get("deviceSn") or "").strip(): item
        for item in latest_items
        if item.get("deviceSn")
    }

    for sn in configured_sns:
        dev = db.get(Device, sn)
        if not dev:
            continue
        item = by_sn.get(sn)
        if not item:
            dev.status = "offline"
            errors.append(f"Device {sn} was not returned by DeyeCloud.")
            continue

        data_list = item.get("dataList") or []
        raw_points = [
            {
                "key": pt.get("key"),
                "value": pt.get("value"),
                "unit": pt.get("unit"),
                "name": pt.get("name"),
            }
            for pt in data_list
            if isinstance(pt, dict) and pt.get("key")
        ]
        normalized = normalize_telemetry(raw_points, mapping)

        raw_state = item.get("deviceState") or item.get("connectStatus")
        dev.status = _normalize_status(raw_state) if raw_state is not None else "online"
        if item.get("deviceType"):
            dev.device_type = str(item["deviceType"])
        collection_time = item.get("collectionTime")
        dev.collection_time = str(collection_time) if collection_time is not None else None
        dev.last_seen_at = now

        db.add(
            MeasurementSnapshot(
                device_sn=sn,
                recorded_at=now,
                collection_time=dev.collection_time,
                normalized_json=json.dumps(normalized),
                raw_points_json=json.dumps(raw_points),
            )
        )
        _upsert_today_history_from_live(db, sn, normalized, now)
        devices_updated += 1

    status = "success" if not errors else ("partial" if devices_updated > 0 else "error")
    message = (
        f"Collected live telemetry for {devices_updated}/{len(configured_sns)} device(s)."
        if not errors
        else "; ".join(errors)
    )
    db.add(
        SyncLog(
            sync_type="live",
            status=status,
            message=message,
            devices_updated=devices_updated,
        )
    )
    db.commit()

    return CollectResponse(
        status=status,
        message=message,
        devices_updated=devices_updated,
        synced_at=now,
        errors=errors,
    )


def _sum_optional(values: List[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    return round(sum(present), 3) if present else None


def get_live_dashboard(db: Session, configured_sns: List[str]) -> LiveDashboardResponse:
    """Build live dashboard payload from latest SQLite snapshots and sync logs."""
    ensure_configured_devices(db, configured_sns)
    mapping = get_mapping_dict(db)
    devices = list_devices(db, configured_sns)

    inverters: List[InverterLiveOut] = []
    online_count = 0
    offline_count = 0

    for dev in devices:
        snap = db.scalar(
            select(MeasurementSnapshot)
            .where(MeasurementSnapshot.device_sn == dev.device_sn)
            .order_by(MeasurementSnapshot.id.desc())
            .limit(1)
        )

        raw_points: List[RawMeasurementPoint] = []
        if snap:
            try:
                raw_dicts = json.loads(snap.raw_points_json)
            except ValueError:
                raw_dicts = []
            # Re-normalize against current mappings so mapping edits reflect immediately
            normalized = normalize_telemetry(raw_dicts, mapping)
            raw_points = [RawMeasurementPoint(**pt) for pt in raw_dicts if pt.get("key")]
        else:
            normalized = normalize_telemetry([], mapping)

        if dev.status == "online":
            online_count += 1
        elif dev.status in {"offline", "alert"}:
            offline_count += 1

        pv_inputs = [PVChannelReading(**pv) for pv in normalized["pv_inputs"]]
        inverters.append(
            InverterLiveOut(
                device_sn=dev.device_sn,
                name=dev.name,
                status=dev.status,
                collection_time=dev.collection_time,
                last_seen_at=dev.last_seen_at,
                rated_power_w=normalized["rated_power_w"],
                current_power_w=normalized["current_power_w"],
                daily_energy_kwh=normalized["daily_energy_kwh"],
                monthly_energy_kwh=normalized["monthly_energy_kwh"],
                total_energy_kwh=normalized["total_energy_kwh"],
                ac_voltage_v=normalized["ac_voltage_v"],
                ac_current_a=normalized["ac_current_a"],
                ac_frequency_hz=normalized["ac_frequency_hz"],
                temperature_c=normalized["temperature_c"],
                pv_inputs=pv_inputs,
                raw_points=raw_points,
            )
        )

    last_sync = db.scalar(
        select(SyncLog)
        .where(SyncLog.sync_type == "live")
        .order_by(SyncLog.id.desc())
        .limit(1)
    )
    last_success = db.scalar(
        select(SyncLog)
        .where(SyncLog.sync_type == "live", SyncLog.status.in_(["success", "partial"]))
        .order_by(SyncLog.id.desc())
        .limit(1)
    )

    summary = LiveSummary(
        total_current_power_w=_sum_optional([inv.current_power_w for inv in inverters]),
        total_daily_energy_kwh=_sum_optional([inv.daily_energy_kwh for inv in inverters]),
        total_monthly_energy_kwh=_sum_optional([inv.monthly_energy_kwh for inv in inverters]),
        total_lifetime_energy_kwh=_sum_optional([inv.total_energy_kwh for inv in inverters]),
        online_count=online_count,
        offline_count=offline_count,
        total_devices=len(inverters),
    )

    return LiveDashboardResponse(
        summary=summary,
        inverters=inverters,
        last_sync_at=last_success.created_at if last_success else None,
        last_sync_status=last_sync.status if last_sync else None,
        last_error=last_sync.message if last_sync and last_sync.status == "error" else None,
    )
