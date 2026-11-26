"""Live Dashboard view: summary KPIs, solar array power flow, and microinverter cards."""

from __future__ import annotations

import html
from typing import Optional

import streamlit as st

from app.schemas import InverterLiveOut, LiveDashboardResponse, PVChannelReading


def _fmt(value: Optional[float], suffix: str, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f} {suffix}"


def _status_badge_html(status: str) -> str:
    colors = {
        "online": ("#10b981", "rgba(16, 185, 129, 0.15)"),
        "offline": ("#f43f5e", "rgba(244, 63, 94, 0.15)"),
        "alert": ("#f59e0b", "rgba(245, 158, 11, 0.15)"),
    }
    fg, bg = colors.get(status, ("#94a3b8", "rgba(148, 163, 184, 0.15)"))
    safe_status = html.escape(status.capitalize())
    return (
        f'<span style="display:inline-flex;align-items:center;gap:6px;padding:2px 10px;'
        f'border-radius:999px;font-size:12px;font-weight:600;color:{fg};background:{bg};'
        f'border:1px solid {fg}44;">● {safe_status}</span>'
    )


def _pv_tile_html(pv: PVChannelReading) -> str:
    is_available = pv.power is not None or pv.voltage is not None or pv.current is not None
    watts = pv.power
    is_generating = watts is not None and watts > 0

    border = "#f59e0b" if is_generating else ("#334155" if is_available else "#475569")
    opacity = "1" if is_available else "0.5"
    watts_color = "#fbbf24" if is_generating else ("#e2e8f0" if is_available else "#94a3b8")
    watts_text = f"{watts:.0f} W" if watts is not None else "N/A"
    volt_text = f"{pv.voltage:.1f}V" if pv.voltage is not None else "—"
    curr_text = f"{pv.current:.1f} A" if pv.current is not None else "Unavailable"

    return (
        f'<div style="border:1px {"solid" if is_available else "dashed"} {border};'
        f'border-radius:10px;padding:10px;text-align:center;opacity:{opacity};'
        f'background:linear-gradient(180deg,#0c1e35 0%,#0f172a 100%);color:#f8fafc;">'
        f'<div style="display:flex;justify-content:space-between;font-size:11px;color:#94a3b8;">'
        f'<span><b>PV{pv.channel}</b></span><span>{volt_text}</span></div>'
        f'<div style="font-size:18px;font-weight:700;font-family:monospace;color:{watts_color};margin:4px 0;">'
        f'{watts_text}</div>'
        f'<div style="font-size:11px;font-family:monospace;color:#94a3b8;">{curr_text}</div>'
        f'</div>'
    )


def _render_solar_flow(live: LiveDashboardResponse, mobile: bool = False) -> None:
    st.subheader("☀️ Solar Array & Power Flow")
    st.caption("Measured DeyeCloud PV telemetry flowing into each microinverter and combined AC output")

    if mobile:
        cols = [st.container() for _ in live.inverters]
    else:
        cols = st.columns(max(1, len(live.inverters)))
    for col, inv in zip(cols, live.inverters):
        with col:
            tiles = "".join(_pv_tile_html(pv) for pv in inv.pv_inputs)
            is_online = inv.status == "online"
            node_border = "#10b98166" if is_online else "#334155"
            node_bg = "rgba(16, 185, 129, 0.08)" if is_online else "rgba(30, 41, 59, 0.4)"
            arrow_color = "#10b981" if (inv.current_power_w or 0) > 0 else "#475569"
            pwr = f"{inv.current_power_w:.0f} W" if inv.current_power_w is not None else "N/A"
            daily = f"{inv.daily_energy_kwh:.2f} kWh" if inv.daily_energy_kwh is not None else "—"
            short_name = html.escape(inv.name.split(" (")[0])

            st.markdown(
                f"""
                <div style="border:1px solid #33415566;border-radius:14px;padding:12px;background:rgba(15,23,42,0.35);">
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                    {tiles}
                  </div>
                  <div style="text-align:center;color:{arrow_color};font-size:18px;line-height:1.2;margin:6px 0;">▼</div>
                  <div style="border:1px solid {node_border};background:{node_bg};border-radius:10px;padding:10px 12px;display:flex;justify-content:space-between;align-items:center;">
                    <div>
                      <div style="font-size:13px;font-weight:600;">{short_name}</div>
                      <div style="font-size:11px;font-family:monospace;color:#94a3b8;">{html.escape(inv.device_sn)}</div>
                    </div>
                    <div style="text-align:right;">
                      <div style="font-size:15px;font-weight:700;font-family:monospace;color:#f59e0b;">{pwr}</div>
                      <div style="font-size:11px;color:#94a3b8;">{daily}</div>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    total_pwr = (
        f"{live.summary.total_current_power_w:.0f} W"
        if live.summary.total_current_power_w is not None
        else "N/A"
    )
    total_daily = (
        f"{live.summary.total_daily_energy_kwh:.2f} kWh today"
        if live.summary.total_daily_energy_kwh is not None
        else "—"
    )
    st.markdown(
        f"""
        <div style="display:flex;justify-content:center;margin-top:12px;">
          <div style="border:1px solid rgba(245,158,11,0.45);background:rgba(245,158,11,0.10);
                      border-radius:14px;padding:12px 24px;text-align:center;">
            <div style="font-size:12px;color:#cbd5e1;">🏠 Combined AC Solar Output</div>
            <div style="font-size:22px;font-weight:700;font-family:monospace;color:#f59e0b;">
              {total_pwr} <span style="font-size:13px;font-weight:400;color:#94a3b8;">({total_daily})</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_inverter_card(inv: InverterLiveOut) -> None:
    with st.container(border=True):
        top_l, top_r = st.columns([3, 1])
        with top_l:
            rated = f" • Rated {inv.rated_power_w:.0f} W" if inv.rated_power_w else ""
            st.markdown(f"**{inv.name}**")
            st.caption(f"SN: `{inv.device_sn}`{rated}")
        with top_r:
            st.markdown(_status_badge_html(inv.status), unsafe_allow_html=True)

        m1, m2 = st.columns(2)
        m1.metric("Current Power", _fmt(inv.current_power_w, "W", 0))
        m2.metric("Daily Energy", _fmt(inv.daily_energy_kwh, "kWh"))

        m3, m4 = st.columns(2)
        m3.metric("Total Energy", _fmt(inv.total_energy_kwh, "kWh", 1))
        m4.metric("Temperature", _fmt(inv.temperature_c, "°C", 1))

        ac1, ac2, ac3 = st.columns(3)
        ac1.caption(f"**AC Voltage**\n\n{_fmt(inv.ac_voltage_v, 'V', 1)}")
        ac2.caption(f"**AC Current**\n\n{_fmt(inv.ac_current_a, 'A', 2)}")
        ac3.caption(f"**Frequency**\n\n{_fmt(inv.ac_frequency_hz, 'Hz', 2)}")

        st.markdown("**Individual PV Inputs (PV1–PV4)**")
        pv_cols = st.columns(2)
        for idx, pv in enumerate(inv.pv_inputs):
            with pv_cols[idx % 2]:
                has_any = pv.voltage is not None or pv.current is not None or pv.power is not None
                badge = "Reported" if has_any else "Unavailable"
                v_str = f"{pv.voltage:.1f} {pv.voltage_unit or 'V'}" if pv.voltage is not None else "—"
                c_str = f"{pv.current:.1f} {pv.current_unit or 'A'}" if pv.current is not None else "—"
                p_str = f"{pv.power:.1f} {pv.power_unit or 'W'}" if pv.power is not None else "—"
                e_str = f"{pv.energy:.2f} {pv.energy_unit or 'kWh'}" if pv.energy is not None else "—"
                with st.container(border=True):
                    st.caption(f"**PV{pv.channel}** · `{badge}`")
                    st.markdown(
                        f"<div style='font-size:12px;font-family:monospace;'>"
                        f"V: <b>{v_str}</b><br/>"
                        f"I: <b>{c_str}</b><br/>"
                        f"P: <b style='color:#f59e0b;'>{p_str}</b><br/>"
                        f"E: <b style='color:#10b981;'>{e_str}</b>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )


def render_live_dashboard(live: LiveDashboardResponse, mobile: bool = False) -> None:
    """Render the Live Dashboard tab."""
    s = live.summary
    power_val = f"{s.total_current_power_w:.0f} W" if s.total_current_power_w is not None else "N/A"
    fleet_delta = f"{s.offline_count} offline/alert" if s.offline_count > 0 else "All online"
    fleet_delta_color = "inverse" if s.offline_count > 0 else "normal"

    if mobile:
        r1a, r1b = st.columns(2)
        r1a.metric("Current Power", power_val)
        r1b.metric("Daily Gen.", _fmt(s.total_daily_energy_kwh, "kWh"))
        r2a, r2b = st.columns(2)
        r2a.metric("Monthly Gen.", _fmt(s.total_monthly_energy_kwh, "kWh"))
        r2b.metric("Lifetime Gen.", _fmt(s.total_lifetime_energy_kwh, "kWh", 1))
        st.metric(
            "Fleet Status",
            f"{s.online_count} / {s.total_devices}",
            delta=fleet_delta,
            delta_color=fleet_delta_color,
        )
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Current Power", power_val)
        c2.metric("Daily Generation", _fmt(s.total_daily_energy_kwh, "kWh"))
        c3.metric("Monthly Generation", _fmt(s.total_monthly_energy_kwh, "kWh"))
        c4.metric("Lifetime Generation", _fmt(s.total_lifetime_energy_kwh, "kWh", 1))
        c5.metric(
            "Fleet Status",
            f"{s.online_count} / {s.total_devices}",
            delta=fleet_delta,
            delta_color=fleet_delta_color,
        )

    st.divider()
    _render_solar_flow(live, mobile=mobile)
    st.divider()

    st.subheader("Microinverter Details")
    if mobile:
        for inv in live.inverters:
            _render_inverter_card(inv)
    else:
        inv_cols = st.columns(max(1, len(live.inverters)))
        for col, inv in zip(inv_cols, live.inverters):
            with col:
                _render_inverter_card(inv)
