"""FastAPI application entrypoint with background 5-minute DeyeCloud polling."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.clients.deye_client import DeyeCloudClient
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.logging_utils import configure_logging
from app.models import ApiCallLog, TokenCache
from app.routers.api import router as api_router
from app.services.collector_service import collect_live_data, ensure_configured_devices
from app.services.mapping_service import ensure_default_mappings

logger = logging.getLogger(__name__)


def _scheduled_collect(app: FastAPI) -> None:
    """Background job executed every POLL_INTERVAL_MINUTES."""
    settings = get_settings()
    if not settings.has_credentials:
        logger.debug("Skipping scheduled collection: DeyeCloud credentials not configured.")
        return

    db = SessionLocal()
    try:
        result = collect_live_data(db, app.state.deye_client, settings.configured_device_sns)
        logger.info("Scheduled collection finished: status=%s updated=%d", result.status, result.devices_updated)
    except Exception as exc:
        logger.exception("Unexpected error during scheduled collection: %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(
        level=settings.log_level,
        extra_secrets=[settings.deye_app_secret, settings.deye_password],
    )

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_configured_devices(db, settings.configured_device_sns)
        ensure_default_mappings(db)
    finally:
        db.close()

    cache_key = f"{settings.deye_base_url}|{settings.deye_app_id}"

    def _load_token():
        s = SessionLocal()
        try:
            row = s.query(TokenCache).filter(TokenCache.cache_key == cache_key).first()
            return (row.access_token, row.expires_at_epoch) if row else None
        finally:
            s.close()

    def _save_token(token: str, expires_at_epoch: float) -> None:
        s = SessionLocal()
        try:
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
        finally:
            s.close()

    def _log_api_call(
        method: str,
        endpoint: str,
        status_code: int | None,
        success: bool,
        duration_ms: float,
        error_message: str | None,
    ) -> None:
        s = SessionLocal()
        try:
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
        finally:
            s.close()

    client = DeyeCloudClient(
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
    app.state.deye_client = client

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.start()
    app.state.scheduler = scheduler
    app.state.auto_refresh_enabled = False
    app.state.poll_interval_minutes = settings.poll_interval_minutes
    app.state.scheduled_collect_fn = _scheduled_collect
    logger.info(
        "Deye Solar Monitor started (base_url=%s, poll_interval=%dm, auto_refresh=OFF, devices=%s).",
        settings.deye_base_url,
        settings.poll_interval_minutes,
        settings.configured_device_sns,
    )

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        client.close()


app = FastAPI(
    title="Deye Solar Monitoring API",
    version="1.0.0",
    description="Backend API for monitoring Deye microinverters via DeyeCloud OpenAPI v1.0.",
    lifespan=lifespan,
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
