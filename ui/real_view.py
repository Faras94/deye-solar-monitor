"""Real View: 8 physically wired solar panels grouped by microinverter + today's power trend."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Optional

import altair as alt
import pandas as pd
import streamlit as st

from app.schemas import InverterLiveOut, LiveDashboardResponse, PVChannelReading
from ui.services import CO2_KG_PER_KWH, CONNECTED_CHANNELS, IST, RATED_CAPACITY_W, fetch_history


def _get_pv_energy_kwh(inverter: InverterLiveOut, channel: int) -> Optional[float]:
    key = f"TotalProduction{channel}"
    for pt in inverter.raw_points:
        if pt.key == key and pt.value not in (None, ""):
            try:
                return float(pt.value)
            except (TypeError, ValueError):
                return None
    return None


def _panel_card_html(
    panel_number: int,
    pv: PVChannelReading,
    pv_energy_kwh: Optional[float],
    inverter_status: str,
) -> str:
    watts = pv.power
    is_generating = watts is not None and watts > 0
    is_online = inverter_status == "online"

    status_color = "#34d399" if is_online else "#94a3b8"
    watts_color = "#fbbf24" if is_generating else "#f8fafc"
    watts_text = f"{watts:.0f} W" if watts is not None else "N/A"
    volt_text = f"{pv.voltage:.1f} V" if pv.voltage is not None else "— V"
    curr_text = f"{pv.current:.1f} A" if pv.current is not None else "— A"
    energy_text = f"⚡ {pv_energy_kwh:.2f} kWh" if pv_energy_kwh is not None else "⚡ —"
    bar_gradient = (
        "linear-gradient(90deg,#34d399,#fbbf24,#34d399)"
        if is_generating
        else "linear-gradient(90deg,rgba(16,185,129,0.3),rgba(14,165,233,0.3))"
    )
    safe_status = html.escape("Online" if is_online else inverter_status)

    return f"""
    <div style="border:1px solid #334155;border-radius:14px;padding:14px;
                background:linear-gradient(180deg,#0f172a 0%,#020617 100%);color:#f8fafc;">
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;margin-bottom:10px;">
        <div><b>Panel {panel_number}</b> <span style="font-family:monospace;color:#7dd3fc;">(PV{pv.channel})</span></div>
        <div style="color:{status_color};font-weight:600;">● {safe_status}</div>
      </div>
      <div style="display:flex;align-items:center;gap:12px;">
        <div style="width:76px;height:52px;border-radius:8px;border:1px solid rgba(56,189,248,0.45);
                    background:repeating-linear-gradient(0deg,rgba(186,230,253,0.18) 0 1px,transparent 1px 13px),
                               repeating-linear-gradient(90deg,rgba(186,230,253,0.18) 0 1px,transparent 1px 19px),
                               linear-gradient(135deg,#0369a1,#1e3a8a,#0f172a);flex-shrink:0;"></div>
        <div>
          <div style="font-size:22px;font-weight:700;font-family:monospace;color:{watts_color};">{watts_text}</div>
          <div style="font-size:11px;font-family:monospace;color:#cbd5e1;">{volt_text} • {curr_text}</div>
          <div style="font-size:11px;font-family:monospace;color:#34d399;margin-top:2px;">{energy_text}</div>
        </div>
      </div>
      <div style="height:4px;border-radius:999px;background:{bar_gradient};margin-top:12px;"></div>
    </div>
    """


def render_real_view(live: LiveDashboardResponse, mobile: bool = False) -> None:
    """Render the Real View tab showing only physically wired solar panels."""
    panel_counter = 1
    inverter_groups = []
    for inv in live.inverters:
        connected = CONNECTED_CHANNELS.get(inv.device_sn, [1, 2, 3, 4])
        panels = []
        for ch in connected:
            pv = next((p for p in inv.pv_inputs if p.channel == ch), None)
            if pv is None:
                continue
            panels.append(
                {
                    "panel_number": panel_counter,
                    "pv": pv,
                    "pv_energy_kwh": _get_pv_energy_kwh(inv, ch),
                }
            )
            panel_counter += 1
        inverter_groups.append(
            {
                "inverter": inv,
                "rated_kw": RATED_CAPACITY_W.get(inv.device_sn, 2000) / 1000.0,
                "panels": panels,
            }
        )

    total_panels = sum(len(g["panels"]) for g in inverter_groups)
    total_power_w = live.summary.total_current_power_w
    total_daily_kwh = live.summary.total_daily_energy_kwh
    co2_saved_kg = total_daily_kwh * CO2_KG_PER_KWH if total_daily_kwh is not None else None

    st.subheader(f"☀️ Real View — {total_panels} Connected Solar Panels")
    st.caption("Showing only physically wired panels (unconnected PV1 ports hidden)")

    if mobile:
        k1, k2 = st.columns(2)
        k1.metric("Total Generation", f"{total_power_w:.0f} W" if total_power_w is not None else "N/A")
        k2.metric(
            "Today's Energy",
            f"{total_daily_kwh:.2f} kWh" if total_daily_kwh is not None else "N/A",
        )
        st.metric("CO₂ Saved Today", f"{co2_saved_kg:.2f} kg" if co2_saved_kg is not None else "N/A")
    else:
        k1, k2, k3 = st.columns(3)
        k1.metric("Total Generation", f"{total_power_w:.0f} W" if total_power_w is not None else "N/A")
        k2.metric(
            "Today's Energy",
            f"{total_daily_kwh:.2f} kWh" if total_daily_kwh is not None else "N/A",
        )
        k3.metric("CO₂ Saved Today", f"{co2_saved_kg:.2f} kg" if co2_saved_kg is not None else "N/A")

    st.divider()

    for group in inverter_groups:
        inv: InverterLiveOut = group["inverter"]
        panels = group["panels"]
        rated_kw: float = group["rated_kw"]

        with st.container(border=True):
            h_left, h_mid, h_right = st.columns([3, 1, 1])
            with h_left:
                st.markdown(f"**{inv.name}** · `{inv.status}`")
                st.caption(
                    f"{rated_kw:.1f} kW Rated • {len(panels)} Panel{'s' if len(panels) != 1 else ''} Connected"
                )
            with h_mid:
                st.metric(
                    "Current Power",
                    f"{inv.current_power_w:.0f} W" if inv.current_power_w is not None else "N/A",
                )
            with h_right:
                st.metric(
                    "Today's Energy",
                    f"{inv.daily_energy_kwh:.2f} kWh" if inv.daily_energy_kwh is not None else "N/A",
                )

            if panels:
                if mobile:
                    for p in panels:
                        st.markdown(
                            _panel_card_html(
                                panel_number=p["panel_number"],
                                pv=p["pv"],
                                pv_energy_kwh=p["pv_energy_kwh"],
                                inverter_status=inv.status,
                            ),
                            unsafe_allow_html=True,
                        )
                else:
                    p_cols = st.columns(max(1, len(panels)))
                    for col, p in zip(p_cols, panels):
                        with col:
                            st.markdown(
                                _panel_card_html(
                                    panel_number=p["panel_number"],
                                    pv=p["pv"],
                                    pv_energy_kwh=p["pv_energy_kwh"],
                                    inverter_status=inv.status,
                                ),
                                unsafe_allow_html=True,
                            )

    st.divider()
    if mobile:
        left, right = st.container(), st.container()
    else:
        left, right = st.columns([2, 1])

    with left:
        st.markdown("**Total Power Trend (Today)**")
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        hist = fetch_history(granularity="intraday", start_date=today_str, end_date=today_str)
        if not hist.records:
            st.info("Intraday trend will appear as 5-minute samples accumulate today.")
        else:
            by_time: dict[str, float] = {}
            for r in hist.records:
                by_time[r.period_key] = by_time.get(r.period_key, 0.0) + (r.power_w or 0.0)
            df = pd.DataFrame(
                [
                    {
                        "time": k[11:16] if len(k) >= 16 else k,
                        "power_w": round(v, 0),
                    }
                    for k, v in sorted(by_time.items())
                ]
            )
            chart = (
                alt.Chart(df)
                .mark_area(
                    line={"color": "#0ea5e9", "strokeWidth": 2},
                    color=alt.Gradient(
                        gradient="linear",
                        stops=[
                            alt.GradientStop(color="rgba(14,165,233,0.35)", offset=0),
                            alt.GradientStop(color="rgba(14,165,233,0.02)", offset=1),
                        ],
                        x1=1,
                        x2=1,
                        y1=0,
                        y2=1,
                    ),
                )
                .encode(
                    x=alt.X("time:N", title="Time"),
                    y=alt.Y("power_w:Q", title="Total Power (W)"),
                    tooltip=["time", "power_w"],
                )
                .properties(height=230)
            )
            st.altair_chart(chart, width="stretch")

    with right:
        with st.container(border=True):
            st.markdown("**✅ System Summary**")
            st.write(f"- **Total Panels:** `{total_panels}`")
            st.write(f"- **Microinverters:** `{len(live.inverters)}`")
            st.write("- **Inverter Rating:** `5.4 kW`")
            st.write("- **Layout:** `3 + 4 + 1 Panels`")
            st.success(
                f"{live.summary.online_count}/{live.summary.total_devices} microinverters online. "
                "Unconnected PV1 ports are excluded from this view."
            )
