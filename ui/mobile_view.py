"""Focused, app-style Mobile UI with essential solar telemetry and streamlined navigation."""

from __future__ import annotations

import html
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import altair as alt
import pandas as pd
import streamlit as st

from app.schemas import InverterLiveOut, LiveDashboardResponse
from ui.services import (
    CO2_KG_PER_KWH,
    CONNECTED_CHANNELS,
    IST,
    RATED_CAPACITY_W,
    fetch_history,
    format_local_time,
    trigger_fetch_history,
)

DEFAULT_TARIFF_INR = 7.5


def _render_mobile_hero(live: LiveDashboardResponse) -> None:
    s = live.summary
    power_str = f"{s.total_current_power_w:.0f} W" if s.total_current_power_w is not None else "N/A"
    daily_kwh = s.total_daily_energy_kwh
    daily_str = f"{daily_kwh:.2f} kWh" if daily_kwh is not None else "N/A"
    savings_str = f"₹{daily_kwh * DEFAULT_TARIFF_INR:.0f}" if daily_kwh is not None else "—"
    co2_str = f"{daily_kwh * CO2_KG_PER_KWH:.1f} kg" if daily_kwh is not None else "—"
    monthly_str = (
        f"{s.total_monthly_energy_kwh:.1f} kWh"
        if s.total_monthly_energy_kwh is not None
        else "N/A"
    )
    lifetime_str = (
        f"{s.total_lifetime_energy_kwh:.0f} kWh"
        if s.total_lifetime_energy_kwh is not None
        else "N/A"
    )

    all_online = s.offline_count == 0 and s.total_devices > 0
    badge_bg = "rgba(16,185,129,0.18)" if all_online else "rgba(245,158,11,0.18)"
    badge_fg = "#34d399" if all_online else "#fbbf24"
    badge_text = (
        f"● {s.online_count}/{s.total_devices} Online"
        if all_online
        else f"● {s.online_count}/{s.total_devices} Online ({s.offline_count} Alert)"
    )

    st.markdown(
        f"""
        <div style="border-radius:18px;padding:18px;margin-bottom:14px;
                    background:linear-gradient(145deg,#0f172a 0%,#1e293b 100%);
                    border:1px solid rgba(245,158,11,0.35);color:#f8fafc;
                    box-shadow:0 8px 24px rgba(0,0,0,0.25);">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <span style="font-size:12px;color:#94a3b8;font-weight:600;letter-spacing:0.4px;">
              LIVE SOLAR OUTPUT
            </span>
            <span style="font-size:11px;font-weight:600;padding:3px 10px;border-radius:999px;
                         background:{badge_bg};color:{badge_fg};">
              {badge_text}
            </span>
          </div>
          <div style="font-size:36px;font-weight:800;font-family:monospace;color:#fbbf24;line-height:1.1;">
            {power_str}
          </div>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:16px;
                      padding-top:12px;border-top:1px solid rgba(148,163,184,0.2);">
            <div>
              <div style="font-size:11px;color:#94a3b8;">Today</div>
              <div style="font-size:15px;font-weight:700;font-family:monospace;color:#34d399;">{daily_str}</div>
            </div>
            <div>
              <div style="font-size:11px;color:#94a3b8;">Est. Saved</div>
              <div style="font-size:15px;font-weight:700;font-family:monospace;color:#f8fafc;">{savings_str}</div>
            </div>
            <div>
              <div style="font-size:11px;color:#94a3b8;">CO₂ Offset</div>
              <div style="font-size:15px;font-weight:700;font-family:monospace;color:#38bdf8;">{co2_str}</div>
            </div>
          </div>
          <div style="display:flex;justify-content:space-between;margin-top:10px;font-size:11px;color:#94a3b8;">
            <span>Month: <b style="color:#e2e8f0;">{monthly_str}</b></span>
            <span>Lifetime: <b style="color:#e2e8f0;">{lifetime_str}</b></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_mobile_today_curve() -> None:
    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    hist = fetch_history(granularity="intraday", start_date=today_str, end_date=today_str)
    st.markdown("**Today's Power Curve**")
    if not hist.records:
        st.caption("Intraday curve will appear as today's 5-minute samples arrive.")
        return

    by_time: Dict[str, float] = {}
    for r in hist.records:
        by_time[r.period_key] = by_time.get(r.period_key, 0.0) + (r.power_w or 0.0)
    df = pd.DataFrame(
        [
            {"Time": k[11:16] if len(k) >= 16 else k, "Watts": round(v, 0)}
            for k, v in sorted(by_time.items())
        ]
    )
    chart = (
        alt.Chart(df)
        .mark_area(
            line={"color": "#f59e0b", "strokeWidth": 2},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="rgba(245,158,11,0.35)", offset=0),
                    alt.GradientStop(color="rgba(245,158,11,0.02)", offset=1),
                ],
                x1=1,
                x2=1,
                y1=0,
                y2=1,
            ),
        )
        .encode(
            x=alt.X("Time:N", title=None),
            y=alt.Y("Watts:Q", title="W"),
            tooltip=["Time", "Watts"],
        )
        .properties(height=180)
    )
    st.altair_chart(chart, width="stretch")


def _render_mobile_inverters(inverters: List[InverterLiveOut]) -> None:
    st.markdown("**Microinverters**")
    for inv in inverters:
        pwr = f"{inv.current_power_w:.0f} W" if inv.current_power_w is not None else "N/A"
        daily = f"{inv.daily_energy_kwh:.2f} kWh" if inv.daily_energy_kwh is not None else "—"
        dot = "🟢" if inv.status == "online" else ("🟡" if inv.status == "alert" else "🔴")
        short_name = inv.name.split(" (")[0]
        with st.expander(f"{dot} {short_name} · {pwr} · {daily}", expanded=False):
            c1, c2, c3 = st.columns(3)
            c1.caption(f"**AC**\n{inv.ac_voltage_v:.0f} V" if inv.ac_voltage_v else "**AC**\n—")
            c2.caption(f"**Temp**\n{inv.temperature_c:.1f} °C" if inv.temperature_c else "**Temp**\n—")
            c3.caption(f"**SN**\n`{inv.device_sn}`")

            pv_cols = st.columns(2)
            for idx, pv in enumerate(inv.pv_inputs):
                with pv_cols[idx % 2]:
                    p_txt = f"{pv.power:.0f} W" if pv.power is not None else "—"
                    v_txt = f"{pv.voltage:.1f} V" if pv.voltage is not None else "—"
                    st.caption(f"**PV{pv.channel}:** {p_txt} ({v_txt})")


def _get_pv_energy_kwh(inverter: InverterLiveOut, channel: int) -> Optional[float]:
    key = f"TotalProduction{channel}"
    for pt in inverter.raw_points:
        if pt.key == key and pt.value not in (None, ""):
            try:
                return float(pt.value)
            except (TypeError, ValueError):
                return None
    return None


def _render_mobile_panels(live: LiveDashboardResponse) -> None:
    panel_num = 1
    for inv in live.inverters:
        connected = CONNECTED_CHANNELS.get(inv.device_sn, [1, 2, 3, 4])
        pwr = f"{inv.current_power_w:.0f} W" if inv.current_power_w is not None else "N/A"
        dot = "🟢" if inv.status == "online" else "🔴"
        st.markdown(f"**{dot} {inv.name.split(' (')[0]}** · `{pwr}`")

        cards_html = []
        for ch in connected:
            pv = next((p for p in inv.pv_inputs if p.channel == ch), None)
            if pv is None:
                continue
            w = pv.power
            w_str = f"{w:.0f} W" if w is not None else "N/A"
            w_col = "#fbbf24" if (w is not None and w > 0) else "#e2e8f0"
            v_str = f"{pv.voltage:.1f}V" if pv.voltage is not None else "—"
            a_str = f"{pv.current:.1f}A" if pv.current is not None else "—"
            kwh = _get_pv_energy_kwh(inv, ch)
            e_str = f"⚡ {kwh:.1f} kWh" if kwh is not None else ""
            cards_html.append(
                f'<div style="border:1px solid #334155;border-radius:12px;padding:10px;'
                f'background:linear-gradient(180deg,#0f172a,#020617);color:#f8fafc;">'
                f'<div style="display:flex;justify-content:space-between;font-size:11px;color:#94a3b8;">'
                f'<span><b>Panel {panel_num}</b></span><span>PV{ch}</span></div>'
                f'<div style="font-size:20px;font-weight:700;font-family:monospace;color:{w_col};margin:4px 0;">{w_str}</div>'
                f'<div style="font-size:11px;font-family:monospace;color:#cbd5e1;">{v_str} • {a_str}</div>'
                f'<div style="font-size:10px;font-family:monospace;color:#34d399;margin-top:2px;">{html.escape(e_str)}</div>'
                f'</div>'
            )
            panel_num += 1

        if cards_html:
            st.markdown(
                f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px;">'
                f'{"".join(cards_html)}</div>',
                unsafe_allow_html=True,
            )


def _render_mobile_trends() -> None:
    preset = st.radio(
        "Range",
        options=["Today", "7 Days", "30 Days", "Monthly"],
        horizontal=True,
        label_visibility="collapsed",
    )

    today = datetime.now(IST).date()
    if preset == "Today":
        granularity = "intraday"
        start_d = today.isoformat()
        end_d = today.isoformat()
    elif preset == "7 Days":
        granularity = "daily"
        start_d = (today - timedelta(days=6)).isoformat()
        end_d = today.isoformat()
    elif preset == "30 Days":
        granularity = "daily"
        start_d = (today - timedelta(days=29)).isoformat()
        end_d = today.isoformat()
    else:
        granularity = "monthly"
        start_d = (today - timedelta(days=365)).isoformat()
        end_d = today.isoformat()

    if st.button("☁️ Sync from DeyeCloud", width="stretch"):
        with st.spinner("Syncing..."):
            res = trigger_fetch_history(start_date=start_d, end_date=end_d, granularity=granularity)
        if res.errors:
            st.error(" | ".join(res.errors))
        else:
            st.success(res.message)

    hist = fetch_history(granularity=granularity, start_date=start_d, end_date=end_d)
    if not hist.records:
        st.info("No readings stored for this range yet. Tap **Sync from DeyeCloud** above.")
        return

    by_period: Dict[str, float] = {}
    for r in hist.records:
        key = r.period_key[11:16] if (granularity == "intraday" and len(r.period_key) >= 16) else r.period_key
        val = (r.power_w or 0.0) if granularity == "intraday" else (r.energy_kwh or 0.0)
        by_period[key] = by_period.get(key, 0.0) + val

    df = pd.DataFrame([{"Period": k, "Value": round(v, 2)} for k, v in sorted(by_period.items())])

    if granularity == "intraday":
        latest_by_sn: Dict[str, float] = {}
        for r in hist.records:
            if r.energy_kwh is not None:
                latest_by_sn[r.device_sn] = max(latest_by_sn.get(r.device_sn, 0.0), r.energy_kwh)
        total_kwh = sum(latest_by_sn.values())
        peak_str = f"{df['Value'].max():.0f} W" if not df.empty else "—"
    else:
        total_kwh = df["Value"].sum()
        peak_str = f"{df['Value'].max():.2f} kWh" if not df.empty else "—"

    k1, k2, k3 = st.columns(3)
    k1.metric("Energy", f"{total_kwh:.1f} kWh")
    k2.metric("Saved", f"₹{total_kwh * DEFAULT_TARIFF_INR:.0f}")
    k3.metric("Peak", peak_str)

    if granularity == "intraday":
        chart = (
            alt.Chart(df)
            .mark_area(color="#f59e0b", opacity=0.25, line={"color": "#f59e0b"})
            .encode(
                x=alt.X("Period:N", title=None, sort=None),
                y=alt.Y("Value:Q", title="Watts"),
                tooltip=["Period", "Value"],
            )
            .properties(height=220)
        )
    else:
        chart = (
            alt.Chart(df)
            .mark_bar(color="#f59e0b", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("Period:N", title=None, sort=None),
                y=alt.Y("Value:Q", title="kWh"),
                tooltip=["Period", "Value"],
            )
            .properties(height=220)
        )
    st.altair_chart(chart, width="stretch")


def render_mobile_app(live: LiveDashboardResponse) -> None:
    """Render the streamlined 3-tab Mobile UI."""
    tab_overview, tab_panels, tab_trends = st.tabs(
        ["⚡ Overview", "☀️ Panels", "📈 Trends"]
    )

    with tab_overview:
        _render_mobile_hero(live)
        _render_mobile_today_curve()
        st.divider()
        _render_mobile_inverters(live.inverters)
        st.caption(f"Last synced: {format_local_time(live.last_sync_at)}")

    with tab_panels:
        _render_mobile_panels(live)

    with tab_trends:
        _render_mobile_trends()
