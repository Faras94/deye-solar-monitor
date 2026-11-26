"""Unit tests for strict PV mapping (never inventing PV values) and unmapped point tracking."""

from __future__ import annotations

from app.services.collector_service import normalize_telemetry
from app.services.mapping_service import (
    DEFAULT_MAPPINGS,
    ensure_default_mappings,
    get_mappings_response,
    update_mappings,
)
from app.schemas import MappingUpdateItem


def test_normalize_telemetry_never_invents_missing_pv_values():
    mapping = {item["dashboard_field"]: item["deye_key"] for item in DEFAULT_MAPPINGS if item["deye_key"]}
    raw_data_list = [
        {"key": "TotalActiveACOutputPower", "value": "1250", "unit": "W"},
        {"key": "DailyActiveProduction", "value": "6.4", "unit": "kWh"},
        {"key": "DCVoltagePV1", "value": "38.5", "unit": "V"},
        {"key": "DCCurrentPV1", "value": "8.2", "unit": "A"},
        # Note: DCPowerPV1 is intentionally omitted, and PV2..PV4 are omitted
    ]

    normalized = normalize_telemetry(raw_data_list, mapping)
    assert normalized["current_power_w"] == 1250.0
    assert normalized["daily_energy_kwh"] == 6.4

    pv1 = normalized["pv_inputs"][0]
    assert pv1["channel"] == 1
    assert pv1["voltage"] == 38.5
    assert pv1["current"] == 8.2
    # Must NOT calculate 38.5 * 8.2 or divide 1250W
    assert pv1["power"] is None

    for ch_idx in (1, 2, 3):
        pv = normalized["pv_inputs"][ch_idx]
        assert pv["voltage"] is None
        assert pv["current"] is None
        assert pv["power"] is None


def test_mapping_update_and_unmapped_points(db_session):
    ensure_default_mappings(db_session)
    from app.models import Device
    import json

    db_session.add(
        Device(
            device_sn="260605A076",
            name="Microinverter 1",
            available_points_json=json.dumps([
                {"key": "TotalActiveACOutputPower", "name": "AC Power", "unit": "W"},
                {"key": "CustomPV1Volt", "name": "Custom PV1 V", "unit": "V"},
                {"key": "InternalFanSpeed", "name": "Fan RPM", "unit": "rpm"},
            ]),
        )
    )
    db_session.commit()

    res_before = get_mappings_response(db_session)
    unmapped_keys_before = {p.key for p in res_before.unmapped_points}
    assert "CustomPV1Volt" in unmapped_keys_before
    assert "InternalFanSpeed" in unmapped_keys_before
    assert "TotalActiveACOutputPower" not in unmapped_keys_before

    res_after = update_mappings(
        db_session,
        [MappingUpdateItem(dashboard_field="pv1_voltage", deye_key="CustomPV1Volt")],
    )
    unmapped_keys_after = {p.key for p in res_after.unmapped_points}
    assert "CustomPV1Volt" not in unmapped_keys_after
    assert "InternalFanSpeed" in unmapped_keys_after
