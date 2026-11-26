"""Integration tests for all FastAPI endpoints backed by SQLite."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app
from app.routers.api import get_deye_client
from app.services.collector_service import ensure_configured_devices
from app.services.mapping_service import ensure_default_mappings


class FakeDeyeClient:
    """In-memory mock of DeyeCloudClient for integration testing."""

    def get_station_list(self, page: int = 1, size: int = 50):
        return [{"id": 9001, "name": "Home Rooftop"}]

    def get_station_devices(self, station_ids, page: int = 1, size: int = 50):
        return [
            {"deviceSn": "260605A076", "deviceType": "MICRO_INVERTER", "stationId": 9001, "deviceState": 1},
            {"deviceSn": "260603A1D5", "deviceType": "MICRO_INVERTER", "stationId": 9001, "deviceState": 1},
            {"deviceSn": "260505A373", "deviceType": "MICRO_INVERTER", "stationId": 9001, "deviceState": 3},
        ]

    def get_device_measure_points(self, device_sn: str, device_type=None):
        return [
            {"key": "TotalActiveACOutputPower", "name": "Current AC Power", "unit": "W"},
            {"key": "DailyActiveProduction", "name": "Daily Energy", "unit": "kWh"},
            {"key": "DCVoltagePV1", "name": "PV1 Voltage", "unit": "V"},
            {"key": "ExtraDiagnosticCode", "name": "Diag", "unit": None},
        ]

    def get_device_latest(self, device_sns):
        return [
            {
                "deviceSn": "260605A076",
                "deviceState": 1,
                "collectionTime": "1732620000",
                "dataList": [
                    {"key": "TotalActiveACOutputPower", "value": "820", "unit": "W"},
                    {"key": "DailyActiveProduction", "value": "4.2", "unit": "kWh"},
                    {"key": "TotalActiveProduction", "value": "412.5", "unit": "kWh"},
                    {"key": "ACVoltage1", "value": "231.4", "unit": "V"},
                    {"key": "ACCurrent1", "value": "3.54", "unit": "A"},
                    {"key": "ACOutputFrequencyR", "value": "50.01", "unit": "Hz"},
                    {"key": "InverterTemperature", "value": "41.2", "unit": "°C"},
                    {"key": "DCVoltagePV1", "value": "37.8", "unit": "V"},
                    {"key": "DCCurrentPV1", "value": "10.9", "unit": "A"},
                    {"key": "DCPowerPV1", "value": "412.0", "unit": "W"},
                    {"key": "ExtraDiagnosticCode", "value": "0", "unit": None},
                ],
            },
            {
                "deviceSn": "260603A1D5",
                "deviceState": 1,
                "collectionTime": "1732620000",
                "dataList": [
                    {"key": "TotalActiveACOutputPower", "value": "780", "unit": "W"},
                    {"key": "DailyActiveProduction", "value": "3.9", "unit": "kWh"},
                ],
            },
            # 260505A373 omitted to simulate offline/unavailable inverter
        ]

    def get_device_history(self, device_sn, start_at, end_at, granularity=2, measure_points=None, device_type=None):
        return [
            {
                "time": start_at,
                "itemList": [
                    {"key": "DailyActiveProduction", "value": "5.1"},
                    {"key": "TotalActiveACOutputPower", "value": "900"},
                ],
            }
        ]


def _build_test_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    seed_db = TestingSessionLocal()
    ensure_configured_devices(seed_db, ["260605A076", "260603A1D5", "260505A373"])
    ensure_default_mappings(seed_db)
    seed_db.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_settings():
        return Settings(
            deye_base_url="https://india-developer.deyecloud.com",
            deye_app_id="test-app",
            deye_app_secret="test-secret",
            deye_email="test@example.com",
            deye_password="test-password",
            deye_device_sns="260605A076,260603A1D5,260505A373",
            database_url="sqlite:///:memory:",
        )

    fake_client = FakeDeyeClient()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_deye_client] = lambda: fake_client
    return TestClient(app)


def test_all_api_endpoints_end_to_end():
    client = _build_test_client()
    try:
        # 1. Health
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["configured_devices"] == ["260605A076", "260603A1D5", "260505A373"]

        # 2. Devices
        r = client.get("/api/devices")
        assert r.status_code == 200
        assert [d["device_sn"] for d in r.json()] == ["260605A076", "260603A1D5", "260505A373"]

        # 3. Discover
        r = client.post("/api/discover")
        assert r.status_code == 200
        assert r.json()["status"] == "success"

        # 4. Collect
        r = client.post("/api/collect")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "partial"  # 2 online, 1 missing
        assert body["devices_updated"] == 2

        # 5. Live
        r = client.get("/api/live")
        assert r.status_code == 200
        live = r.json()
        assert live["summary"]["total_current_power_w"] == 1600.0
        assert live["summary"]["total_daily_energy_kwh"] == 8.1
        assert live["summary"]["online_count"] == 2
        assert live["summary"]["offline_count"] == 1
        inv1 = next(i for i in live["inverters"] if i["device_sn"] == "260605A076")
        assert inv1["pv_inputs"][0]["power"] == 412.0
        assert inv1["pv_inputs"][1]["power"] is None  # Never invented

        # 6. History fetch & query
        r = client.post(
            "/api/history/fetch",
            json={"start_date": "2026-11-20", "end_date": "2026-11-26", "granularity": "daily"},
        )
        assert r.status_code == 200
        assert r.json()["records_saved"] == 3

        r = client.get("/api/history?granularity=daily&start_date=2026-11-01&end_date=2026-11-30")
        assert r.status_code == 200
        assert len(r.json()["records"]) >= 3

        # 7. Mappings GET & POST
        r = client.get("/api/mappings")
        assert r.status_code == 200
        unmapped_keys = {p["key"] for p in r.json()["unmapped_points"]}
        assert "ExtraDiagnosticCode" in unmapped_keys

        r = client.post(
            "/api/mappings",
            json={"mappings": [{"dashboard_field": "pv2_voltage", "deye_key": "ExtraDiagnosticCode"}]},
        )
        assert r.status_code == 200
        unmapped_after = {p["key"] for p in r.json()["unmapped_points"]}
        assert "ExtraDiagnosticCode" not in unmapped_after
    finally:
        app.dependency_overrides.clear()
