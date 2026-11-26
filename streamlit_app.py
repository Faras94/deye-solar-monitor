"""Deye Solar Monitor — Streamlit Application Entrypoint."""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from ui.api_usage import render_api_usage
from ui.devices_mappings import render_devices_mappings
from ui.history_analytics import render_history_analytics
from ui.live_dashboard import render_live_dashboard
from ui.real_view import render_real_view
from ui.services import (
    fetch_live_dashboard,
    format_local_time,
    get_health_summary,
    init_app_resources,
    trigger_collect_live,
)

st.set_page_config(
    page_title="Deye Solar Monitor",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize SQLite, default mappings, and shared DeyeCloudClient
init_app_resources()

if "auto_refresh_enabled" not in st.session_state:
    st.session_state.auto_refresh_enabled = False
if "poll_interval_minutes" not in st.session_state:
    st.session_state.poll_interval_minutes = 5
if "sync_notice" not in st.session_state:
    st.session_state.sync_notice = None
if "sync_error" not in st.session_state:
    st.session_state.sync_error = None
if "mobile_mode" not in st.session_state:
    st.session_state.mobile_mode = False

health = get_health_summary()


def _run_manual_refresh() -> None:
    with st.spinner("Collecting live telemetry from DeyeCloud..."):
        col_res = trigger_collect_live()
    if col_res.errors:
        st.session_state.sync_error = " | ".join(col_res.errors)
        st.session_state.sync_notice = None
    else:
        st.session_state.sync_notice = col_res.message
        st.session_state.sync_error = None


# Apply mobile-optimized CSS when Mobile View is active
if st.session_state.mobile_mode:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.2rem !important;
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            padding-bottom: 2rem !important;
        }
        [data-testid="stMetric"] {
            padding: 10px 12px !important;
            border-radius: 12px !important;
            background: rgba(148, 163, 184, 0.08) !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.35rem !important;
        }
        button[kind="primary"], button[kind="secondary"] {
            min-height: 44px !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px !important;
            flex-wrap: wrap !important;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 6px 10px !important;
            font-size: 0.85rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# Sidebar controls
with st.sidebar:
    st.title("☀️ Deye Solar Monitor")
    st.caption(
        f"India Cloud • {len(health.configured_devices)} Microinverters\n\n"
        f"Auto-refresh: {'ON' if st.session_state.auto_refresh_enabled else 'OFF'}"
    )

    if st.button("🔄 Refresh Live Telemetry", type="primary", width="stretch"):
        _run_manual_refresh()

    st.session_state.mobile_mode = st.toggle(
        "📱 Mobile UI Optimization",
        value=st.session_state.mobile_mode,
        help="Stacks cards, KPIs, and charts into a touch-friendly phone layout.",
    )

    st.divider()
    st.markdown("**Auto-Refresh Settings**")
    st.session_state.auto_refresh_enabled = st.toggle(
        "Enable Auto-Refresh",
        value=st.session_state.auto_refresh_enabled,
    )
    st.session_state.poll_interval_minutes = st.number_input(
        "Interval (minutes)",
        min_value=1,
        max_value=120,
        value=int(st.session_state.poll_interval_minutes),
        step=1,
    )

    st.divider()
    st.markdown("**System Status**")
    st.write(f"- **Last Sync:** {format_local_time(health.last_sync_at)}")
    st.write(f"- **Sync Status:** `{health.last_sync_status or 'never'}`")
    st.write(f"- **Database:** `{health.database}`")
    st.write(
        f"- **Credentials:** `{'configured' if health.credentials_configured else 'missing'}`"
    )


def _render_main_content() -> None:
    mobile = st.session_state.mobile_mode

    # Top quick-action bar (always visible on mobile even when sidebar is collapsed)
    bar_l, bar_m, bar_r = st.columns([2.4, 1.2, 1.4])
    with bar_l:
        st.caption(
            f"☀️ **Deye Solar** • Last sync: `{format_local_time(health.last_sync_at)}`"
        )
    with bar_m:
        if st.button("🔄 Refresh", key="top_refresh_btn", width="stretch"):
            _run_manual_refresh()
            st.rerun()
    with bar_r:
        btn_label = "🖥️ Desktop View" if mobile else "📱 Mobile View"
        btn_type = "primary" if mobile else "secondary"
        if st.button(btn_label, key="toggle_mobile_btn", type=btn_type, width="stretch"):
            st.session_state.mobile_mode = not mobile
            st.rerun()

    if st.session_state.auto_refresh_enabled:
        col_res = trigger_collect_live()
        if col_res.errors:
            st.session_state.sync_error = " | ".join(col_res.errors)

    live = fetch_live_dashboard()

    if st.session_state.sync_notice:
        st.success(st.session_state.sync_notice)
    if st.session_state.sync_error:
        st.error(st.session_state.sync_error)
    elif live.last_error:
        st.error(live.last_error)

    offline_devices = [
        inv.device_sn for inv in live.inverters if inv.status in ("offline", "alert")
    ]
    if offline_devices:
        st.warning(f"Offline / Alert device(s): **{', '.join(offline_devices)}**")

    configured_devices = [inv.device_sn for inv in live.inverters] or health.configured_devices

    tab_live, tab_real, tab_history, tab_devices, tab_usage = st.tabs(
        [
            "⚡ Live" if mobile else "⚡ Live Dashboard",
            "☀️ Panels" if mobile else "☀️ Real View",
            "📈 History" if mobile else "📈 History & Analytics",
            "🔧 Devices" if mobile else "🔧 Devices & Mappings",
            "🖥️ API" if mobile else "🖥️ API Usage",
        ]
    )

    with tab_live:
        render_live_dashboard(live, mobile=mobile)

    with tab_real:
        render_real_view(live, mobile=mobile)

    with tab_history:
        render_history_analytics(configured_devices, mobile=mobile)

    with tab_devices:
        render_devices_mappings(mobile=mobile)

    with tab_usage:
        render_api_usage(mobile=mobile)


if st.session_state.auto_refresh_enabled:
    interval = timedelta(minutes=int(st.session_state.poll_interval_minutes))

    @st.fragment(run_every=interval)
    def _auto_refresh_fragment() -> None:
        _render_main_content()

    _auto_refresh_fragment()
else:
    _render_main_content()
