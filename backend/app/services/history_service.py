"""Historical telemetry fetching from DeyeCloud and SQLite querying."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.deye_client import DeyeAPIError, DeyeCloudClient
from app.models import Device, HistoricalReading, SyncLog
from app.schemas import HistoricalPointOut, HistoryFetchResponse, HistoryQueryResponse
from app.services.collector_service import ensure_configured_devices
from app.services.mapping_service import get_mapping_dict

logger = logging.getLogger(__name__)

# DeyeCloud OpenAPI v1.0 granularity integers:
# 1 = 5-minute / intraday points, 2 = daily buckets, 3 = monthly buckets, 4 = yearly buckets
_GRANULARITY_TO_DEYE = {
    "intraday": 1,
    "daily": 2,
    "monthly": 3,
    "yearly": 4,
}


def _extract_period_key(item: Dict[str, Any], granularity: str) -> Optional[str]:
    raw_time = (
        item.get("time")
        or item.get("date")
        or item.get("collectionTime")
        or item.get("period")
    )
    if raw_time is None:
        return None
    text = str(raw_time).strip()
    if granularity == "intraday":
        # Support Unix epoch seconds/ms or ISO/space-separated datetime strings
        if text.isdigit():
            ts = int(text)
            if ts > 1_000_000_000_000:
                ts = ts // 1000
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        return text[:16].replace("T", " ")
    if granularity == "daily":
        return text[:10]
    if granularity == "monthly":
        return text[:7]
    if granularity == "yearly":
        return text[:4]
    return text


def _extract_energy_and_power(
    item: Dict[str, Any], mapping: Dict[str, str]
) -> tuple[Optional[float], Optional[float]]:
    energy_kwh: Optional[float] = None
    power_w: Optional[float] = None

    # Format A: item has nested itemList / dataList of {key, value}
    nested = item.get("itemList") or item.get("dataList")
    if isinstance(nested, list):
        by_key = {str(pt.get("key") or ""): pt.get("value") for pt in nested if isinstance(pt, dict)}
        for field in ("daily_energy", "monthly_energy", "total_energy"):
            mapped_key = mapping.get(field)
            if mapped_key and mapped_key in by_key and by_key[mapped_key] is not None:
                try:
                    energy_kwh = float(by_key[mapped_key])
                    break
                except (TypeError, ValueError):
                    pass
        power_key = mapping.get("current_power")
        if power_key and power_key in by_key and by_key[power_key] is not None:
            try:
                power_w = float(by_key[power_key])
            except (TypeError, ValueError):
                pass
        return energy_kwh, power_w

    # Format B: flat fields on bucket item
    for key in ("energy", "generationValue", "dailyActiveProduction", "value"):
        if item.get(key) is not None:
            try:
                energy_kwh = float(item[key])
                break
            except (TypeError, ValueError):
                pass
    for key in ("power", "generationPower"):
        if item.get(key) is not None:
            try:
                power_w = float(item[key])
                break
            except (TypeError, ValueError):
                pass
    return energy_kwh, power_w


def fetch_and_store_history(
    db: Session,
    client: DeyeCloudClient,
    configured_sns: List[str],
    start_date: str,
    end_date: str,
    granularity: str = "daily",
    target_sns: Optional[List[str]] = None,
    force: bool = False,
) -> HistoryFetchResponse:
    """Fetch historical readings from DeyeCloud and upsert into SQLite.

    Past date ranges (end_date < today) are immutable; if already cached in SQLite,
    skip redundant DeyeCloud API calls unless force=True.
    """
    ensure_configured_devices(db, configured_sns)
    mapping = get_mapping_dict(db)
    sns = target_sns or configured_sns
    today_str = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")

    if not force and end_date < today_str:
        cached = query_history(
            db=db,
            granularity=granularity,
            start_date=start_date,
            end_date=end_date,
            device_sns=sns,
        )
        if cached.records:
            return HistoryFetchResponse(
                status="success",
                message=f"Served {len(cached.records)} immutable {granularity} record(s) from SQLite cache.",
                records_saved=0,
                errors=[],
            )

    deye_gran = _GRANULARITY_TO_DEYE.get(granularity, 2)
    measure_points = [
        k for k in (mapping.get("daily_energy"), mapping.get("current_power")) if k
    ]

    records_saved = 0
    errors: List[str] = []
    now = datetime.now(timezone.utc)

    for sn in sns:
        dev = db.get(Device, sn)
        device_type = dev.device_type if dev else "MICRO_INVERTER"
        try:
            buckets = client.get_device_history(
                device_sn=sn,
                start_at=start_date,
                end_at=end_date,
                granularity=deye_gran,
                measure_points=measure_points or None,
                device_type=device_type,
            )
        except DeyeAPIError as exc:
            msg = f"History fetch failed for {sn}: {exc}"
            logger.warning(msg)
            errors.append(msg)
            continue

        for item in buckets:
            if not isinstance(item, dict):
                continue
            period_key = _extract_period_key(item, granularity)
            if not period_key:
                continue
            energy_kwh, power_w = _extract_energy_and_power(item, mapping)
            existing = db.scalar(
                select(HistoricalReading).where(
                    HistoricalReading.device_sn == sn,
                    HistoricalReading.granularity == granularity,
                    HistoricalReading.period_key == period_key,
                )
            )
            if existing:
                existing.energy_kwh = energy_kwh
                existing.power_w = power_w
                existing.raw_json = json.dumps(item)
                existing.updated_at = now
            else:
                db.add(
                    HistoricalReading(
                        device_sn=sn,
                        granularity=granularity,
                        period_key=period_key,
                        energy_kwh=energy_kwh,
                        power_w=power_w,
                        raw_json=json.dumps(item),
                    )
                )
            records_saved += 1

    status = "success" if not errors else ("partial" if records_saved > 0 else "error")
    message = (
        f"Saved {records_saved} {granularity} historical record(s) for {start_date} to {end_date}."
        if not errors
        else "; ".join(errors)
    )
    db.add(
        SyncLog(
            sync_type="history",
            status=status,
            message=message,
            devices_updated=records_saved,
        )
    )
    db.commit()

    return HistoryFetchResponse(
        status=status,
        message=message,
        records_saved=records_saved,
        errors=errors,
    )


def query_history(
    db: Session,
    granularity: str = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    device_sns: Optional[List[str]] = None,
) -> HistoryQueryResponse:
    """Query stored historical readings from SQLite with optional date range & device filter."""
    stmt = select(HistoricalReading).where(HistoricalReading.granularity == granularity)

    if device_sns:
        stmt = stmt.where(HistoricalReading.device_sn.in_(device_sns))

    if start_date:
        if granularity == "intraday":
            stmt = stmt.where(HistoricalReading.period_key >= f"{start_date[:10]} 00:00")
        else:
            start_key = start_date[:10] if granularity == "daily" else (start_date[:7] if granularity == "monthly" else start_date[:4])
            stmt = stmt.where(HistoricalReading.period_key >= start_key)
    if end_date:
        if granularity == "intraday":
            stmt = stmt.where(HistoricalReading.period_key <= f"{end_date[:10]} 23:59")
        else:
            end_key = end_date[:10] if granularity == "daily" else (end_date[:7] if granularity == "monthly" else end_date[:4])
            stmt = stmt.where(HistoricalReading.period_key <= end_key)

    stmt = stmt.order_by(HistoricalReading.period_key.asc(), HistoricalReading.device_sn.asc())
    rows = db.scalars(stmt).all()

    return HistoryQueryResponse(
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        records=[
            HistoricalPointOut(
                device_sn=r.device_sn,
                granularity=r.granularity,
                period_key=r.period_key,
                energy_kwh=r.energy_kwh,
                power_w=r.power_w,
            )
            for r in rows
        ],
    )
