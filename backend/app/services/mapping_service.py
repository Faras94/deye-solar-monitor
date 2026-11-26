"""Service for managing DeyeCloud-to-dashboard measurement point mappings."""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Device, MeasurementMapping, MeasurementSnapshot
from app.schemas import AvailablePoint, MappingOut, MappingsListResponse, MappingUpdateItem

DEFAULT_MAPPINGS: List[Dict[str, Optional[str]]] = [
    {"dashboard_field": "rated_power", "deye_key": "RatedPower", "label": "Rated Power", "unit": "W", "category": "inverter"},
    {"dashboard_field": "current_power", "deye_key": "TotalActiveACOutputPower", "label": "Current AC Power", "unit": "W", "category": "inverter"},
    {"dashboard_field": "daily_energy", "deye_key": "DailyActiveProduction", "label": "Daily Energy", "unit": "kWh", "category": "inverter"},
    {"dashboard_field": "monthly_energy", "deye_key": "MonthlyActiveProduction", "label": "Monthly Energy", "unit": "kWh", "category": "inverter"},
    {"dashboard_field": "total_energy", "deye_key": "TotalActiveProduction", "label": "Total Lifetime Energy", "unit": "kWh", "category": "inverter"},
    {"dashboard_field": "ac_voltage", "deye_key": "ACVoltage1", "label": "AC Voltage", "unit": "V", "category": "inverter"},
    {"dashboard_field": "ac_current", "deye_key": "ACCurrent1", "label": "AC Current", "unit": "A", "category": "inverter"},
    {"dashboard_field": "ac_frequency", "deye_key": "ACOutputFrequencyR", "label": "Grid Frequency", "unit": "Hz", "category": "inverter"},
    {"dashboard_field": "temperature", "deye_key": "InverterTemperature", "label": "Inverter Temperature", "unit": "°C", "category": "inverter"},
    {"dashboard_field": "pv1_voltage", "deye_key": "DCVoltagePV1", "label": "PV1 Voltage", "unit": "V", "category": "pv1"},
    {"dashboard_field": "pv1_current", "deye_key": "DCCurrentPV1", "label": "PV1 Current", "unit": "A", "category": "pv1"},
    {"dashboard_field": "pv1_power", "deye_key": "DCPowerPV1", "label": "PV1 Power", "unit": "W", "category": "pv1"},
    {"dashboard_field": "pv1_energy", "deye_key": "TotalProduction1", "label": "PV1 Total Energy", "unit": "kWh", "category": "pv1"},
    {"dashboard_field": "pv2_voltage", "deye_key": "DCVoltagePV2", "label": "PV2 Voltage", "unit": "V", "category": "pv2"},
    {"dashboard_field": "pv2_current", "deye_key": "DCCurrentPV2", "label": "PV2 Current", "unit": "A", "category": "pv2"},
    {"dashboard_field": "pv2_power", "deye_key": "DCPowerPV2", "label": "PV2 Power", "unit": "W", "category": "pv2"},
    {"dashboard_field": "pv2_energy", "deye_key": "TotalProduction2", "label": "PV2 Total Energy", "unit": "kWh", "category": "pv2"},
    {"dashboard_field": "pv3_voltage", "deye_key": "DCVoltagePV3", "label": "PV3 Voltage", "unit": "V", "category": "pv3"},
    {"dashboard_field": "pv3_current", "deye_key": "DCCurrentPV3", "label": "PV3 Current", "unit": "A", "category": "pv3"},
    {"dashboard_field": "pv3_power", "deye_key": "DCPowerPV3", "label": "PV3 Power", "unit": "W", "category": "pv3"},
    {"dashboard_field": "pv3_energy", "deye_key": "TotalProduction3", "label": "PV3 Total Energy", "unit": "kWh", "category": "pv3"},
    {"dashboard_field": "pv4_voltage", "deye_key": "DCVoltagePV4", "label": "PV4 Voltage", "unit": "V", "category": "pv4"},
    {"dashboard_field": "pv4_current", "deye_key": "DCCurrentPV4", "label": "PV4 Current", "unit": "A", "category": "pv4"},
    {"dashboard_field": "pv4_power", "deye_key": "DCPowerPV4", "label": "PV4 Power", "unit": "W", "category": "pv4"},
    {"dashboard_field": "pv4_energy", "deye_key": "TotalProduction4", "label": "PV4 Total Energy", "unit": "kWh", "category": "pv4"},
]


def ensure_default_mappings(db: Session) -> None:
    """Seed default measurement mappings if they do not exist yet."""
    existing = {
        row.dashboard_field
        for row in db.scalars(select(MeasurementMapping)).all()
    }
    added = False
    for item in DEFAULT_MAPPINGS:
        if item["dashboard_field"] not in existing:
            db.add(
                MeasurementMapping(
                    dashboard_field=item["dashboard_field"],
                    deye_key=item["deye_key"],
                    label=item["label"] or item["dashboard_field"],
                    unit=item["unit"],
                    category=item["category"] or "inverter",
                )
            )
            added = True
    if added:
        db.commit()


def get_mapping_dict(db: Session) -> Dict[str, str]:
    """Return {dashboard_field: deye_key} for all configured non-empty mappings."""
    ensure_default_mappings(db)
    rows = db.scalars(select(MeasurementMapping)).all()
    return {r.dashboard_field: r.deye_key for r in rows if r.deye_key}


def collect_available_points(db: Session) -> List[AvailablePoint]:
    """Aggregate unique measurement points discovered from devices and live snapshots."""
    points_by_key: Dict[str, AvailablePoint] = {}

    for device in db.scalars(select(Device)).all():
        if not device.available_points_json:
            continue
        try:
            items = json.loads(device.available_points_json)
        except ValueError:
            continue
        for item in items:
            key = item.get("key")
            if key and key not in points_by_key:
                points_by_key[key] = AvailablePoint(
                    key=key,
                    name=item.get("name"),
                    unit=item.get("unit"),
                )

    for snap in db.scalars(select(MeasurementSnapshot).order_by(MeasurementSnapshot.id.desc()).limit(30)).all():
        try:
            raw_items = json.loads(snap.raw_points_json)
        except ValueError:
            continue
        for item in raw_items:
            key = item.get("key")
            if key and key not in points_by_key:
                points_by_key[key] = AvailablePoint(
                    key=key,
                    name=item.get("name"),
                    unit=item.get("unit"),
                )

    return sorted(points_by_key.values(), key=lambda p: p.key.lower())


def get_mappings_response(db: Session) -> MappingsListResponse:
    """Return configured mappings, all discovered points, and unmapped points."""
    ensure_default_mappings(db)
    rows = db.scalars(select(MeasurementMapping).order_by(MeasurementMapping.id)).all()
    mappings = [
        MappingOut(
            dashboard_field=r.dashboard_field,
            deye_key=r.deye_key,
            label=r.label,
            unit=r.unit,
            category=r.category,
        )
        for r in rows
    ]
    mapped_keys: Set[str] = {r.deye_key for r in rows if r.deye_key}
    available = collect_available_points(db)
    unmapped = [pt for pt in available if pt.key not in mapped_keys]
    return MappingsListResponse(
        mappings=mappings,
        unmapped_points=unmapped,
        available_points=available,
    )


def update_mappings(db: Session, updates: List[MappingUpdateItem]) -> MappingsListResponse:
    """Persist user-configured DeyeCloud key mappings."""
    ensure_default_mappings(db)
    by_field = {
        r.dashboard_field: r
        for r in db.scalars(select(MeasurementMapping)).all()
    }
    for item in updates:
        row = by_field.get(item.dashboard_field)
        if row is not None:
            cleaned = item.deye_key.strip() if item.deye_key else None
            row.deye_key = cleaned or None
    db.commit()
    return get_mappings_response(db)
