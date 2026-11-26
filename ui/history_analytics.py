"""History & Analytics view: intraday/daily/monthly/yearly charts, yield KPIs, and CSV export."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from ui.services import (
    CO2_KG_PER_KWH,
    INVERTER_COLORS,
    IST,
    RATED_CAPACITY_W,
    fetch_history,
    trigger_fetch_history,
)


def render_history_analytics(configured_devices: List[str], mobile: bool = False) -> None:
    """Render the History & Analytics tab."""
    st.subheader("📈 History & Analytics")

    # Controls bar
    if mobile:
        c1, c2, c3, c4 = st.container(), st.container(), st.container(), st.container()
    else:
        c1, c2, c3, c4 = st.columns([1.4, 2.2, 1.4, 1.0])
    with c1:
        granularity_label = st.selectbox(
            "View Mode",
            options=["Day (Time)", "Daily", "Monthly", "Yearly"],
            index=0,
        )
        granularity_map = {
            "Day (Time)": "intraday",
            "Daily": "daily",
            "Monthly": "monthly",
            "Yearly": "yearly",
        }
        granularity = granularity_map[granularity_label]

    today = datetime.now(IST).date()
    if granularity == "intraday":
        with c2:
            selected_day = st.date_input("Select Day", value=today)
            effective_start = selected_day.isoformat()
            effective_end = selected_day.isoformat()
        h1, h2, h3 = st.columns([1, 1, 1.2])
        with h1:
            start_hour = st.selectbox("From Hour", [f"{h:02d}" for h in range(24)], index=6)
        with h2:
            end_hour = st.selectbox("To Hour", [f"{h:02d}" for h in range(24)], index=19)
        with h3:
            day_bucket_mode = st.radio(
                "Resolution",
                options=["Hourly", "5-Min"],
                horizontal=True,
                index=0,
            )
    else:
        with c2:
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                start_d = st.date_input("Start Date", value=today - timedelta(days=14))
            with d_col2:
                end_d = st.date_input("End Date", value=today)
            effective_start = start_d.isoformat()
            effective_end = end_d.isoformat()
        start_hour = "00"
        end_hour = "23"
        day_bucket_mode = "5-Min"

    with c3:
        inverter_options = ["ALL"] + configured_devices
        selected_inverter = st.selectbox("Inverter", options=inverter_options, index=0)

    with c4:
        tariff_inr = st.number_input("Tariff (₹/kWh)", min_value=0.0, value=7.5, step=0.5)

    # Action buttons
    b1, b2, _ = st.columns([1.4, 1.4, 4])
    with b1:
        if st.button("☁️ Fetch from DeyeCloud", type="primary", width="stretch"):
            with st.spinner("Fetching history from DeyeCloud..."):
                res = trigger_fetch_history(
                    start_date=effective_start,
                    end_date=effective_end,
                    granularity=granularity,
                )
            if res.errors:
                st.error(" | ".join(res.errors))
            else:
                st.success(res.message)

    # Query SQLite
    target_sns = None if selected_inverter == "ALL" else [selected_inverter]
    hist = fetch_history(
        granularity=granularity,
        start_date=effective_start,
        end_date=effective_end,
        device_sns=target_sns,
    )
    records = hist.records

    if granularity == "intraday":
        records = [
            r
            for r in records
            if len(r.period_key) < 13 or (start_hour <= r.period_key[11:13] <= end_hour)
        ]

    serial_numbers = (
        [selected_inverter]
        if selected_inverter != "ALL"
        else list(dict.fromkeys([*configured_devices, *[r.device_sn for r in records]]))
    )
    total_rated_kw = sum(RATED_CAPACITY_W.get(sn, 2000) for sn in serial_numbers) / 1000.0

    with b2:
        if records:
            csv_df = pd.DataFrame(
                [
                    {
                        "device_sn": r.device_sn,
                        "granularity": r.granularity,
                        "period_key": r.period_key,
                        "power_w": r.power_w,
                        "energy_kwh": r.energy_kwh,
                    }
                    for r in records
                ]
            )
            st.download_button(
                label="⬇️ Export CSV",
                data=csv_df.to_csv(index=False).encode("utf-8"),
                file_name=f"deye-solar-{granularity}-{effective_start}-to-{effective_end}.csv",
                mime="text/csv",
                width="stretch",
            )
        else:
            st.button("⬇️ Export CSV", disabled=True, width="stretch")

    if not records:
        st.info(
            f"No {granularity} readings stored for this selection. "
            "Click **Fetch from DeyeCloud** to pull data, or wait for 5-minute live collections."
        )
        return

    # Build chart DataFrame
    rows: List[Dict[str, object]] = []
    if granularity == "intraday" and day_bucket_mode == "Hourly":
        by_hour: Dict[str, Dict[str, object]] = {}
        for r in records:
            hk = r.period_key[:13] if len(r.period_key) >= 13 else r.period_key
            bucket = by_hour.setdefault(hk, {"sums": {}, "counts": {}})
            sums: Dict[str, float] = bucket["sums"]  # type: ignore[assignment]
            counts: Dict[str, int] = bucket["counts"]  # type: ignore[assignment]
            sums[r.device_sn] = sums.get(r.device_sn, 0.0) + (r.power_w or 0.0)
            counts[r.device_sn] = counts.get(r.device_sn, 0) + 1

        for hk in sorted(by_hour.keys()):
            sums = by_hour[hk]["sums"]  # type: ignore[assignment]
            counts = by_hour[hk]["counts"]  # type: ignore[assignment]
            hh = hk[11:13] if len(hk) >= 13 else hk
            row: Dict[str, object] = {"sort_key": hk, "period": f"{hh}:00", "total": 0.0}
            for sn, total_p in sums.items():
                avg_p = total_p / max(1, counts.get(sn, 1))
                row[sn] = round(avg_p, 2)
                row["total"] = round(float(row["total"]) + avg_p, 2)
            rows.append(row)
    else:
        by_period: Dict[str, Dict[str, object]] = {}
        for r in records:
            disp = (
                r.period_key[11:16]
                if granularity == "intraday" and len(r.period_key) >= 16
                else r.period_key
            )
            if r.period_key not in by_period:
                by_period[r.period_key] = {
                    "sort_key": r.period_key,
                    "period": disp,
                    "total": 0.0,
                }
            val = (r.power_w or 0.0) if granularity == "intraday" else (r.energy_kwh or 0.0)
            by_period[r.period_key][r.device_sn] = round(val, 2)
            by_period[r.period_key]["total"] = round(
                float(by_period[r.period_key]["total"]) + val, 2
            )
        rows = [by_period[k] for k in sorted(by_period.keys())]

    df_chart = pd.DataFrame(rows)
    df_chart["moving_avg"] = df_chart["total"].rolling(window=3, min_periods=1).mean().round(2)

    # KPI Calculations
    totals = df_chart["total"].tolist()
    peak_val = max(totals) if totals else 0.0
    peak_idx = totals.index(peak_val) if totals else 0
    peak_time = str(df_chart.iloc[peak_idx]["period"]) if not df_chart.empty else "—"
    avg_val = sum(totals) / len(totals) if totals else 0.0

    if granularity == "intraday":
        latest_by_sn: Dict[str, float] = {}
        for r in records:
            if r.energy_kwh is not None:
                latest_by_sn[r.device_sn] = max(latest_by_sn.get(r.device_sn, 0.0), r.energy_kwh)
        total_energy_kwh = sum(latest_by_sn.values())
        cf_pct = (avg_val / (total_rated_kw * 1000.0)) * 100.0 if total_rated_kw > 0 else 0.0
    else:
        total_energy_kwh = sum(totals)
        cf_pct = (
            (total_energy_kwh / (total_rated_kw * 24.0 * len(df_chart))) * 100.0
            if total_rated_kw > 0 and len(df_chart) > 0
            else 0.0
        )

    specific_yield = total_energy_kwh / total_rated_kw if total_rated_kw > 0 else 0.0
    savings_inr = total_energy_kwh * tariff_inr
    co2_kg = total_energy_kwh * CO2_KG_PER_KWH
    unit_label = "W" if granularity == "intraday" else "kWh"

    # 6-KPI Grid
    peak_label = f"Peak {'Power' if granularity == 'intraday' else 'Period'}"
    peak_val_str = (
        f"{peak_val:.0f} {unit_label}" if granularity == "intraday" else f"{peak_val:.2f} {unit_label}"
    )
    if mobile:
        r1a, r1b = st.columns(2)
        r1a.metric("Total Energy", f"{total_energy_kwh:.2f} kWh", f"{len(df_chart)} sample(s)")
        r1b.metric("Specific Yield", f"{specific_yield:.2f}", f"kWh/kWp ({total_rated_kw:.1f} kWp)")
        r2a, r2b = st.columns(2)
        r2a.metric(peak_label, peak_val_str, f"At {peak_time}")
        r2b.metric("Capacity Factor", f"{cf_pct:.1f}%", f"Avg {avg_val:.1f} {unit_label}")
        r3a, r3b = st.columns(2)
        r3a.metric("Est. Savings", f"₹{savings_inr:.1f}", f"@ ₹{tariff_inr:.2f}/kWh")
        r3b.metric("CO₂ Offset", f"{co2_kg:.1f} kg", "Grid emissions avoided")
    else:
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Total Energy", f"{total_energy_kwh:.2f} kWh", f"{len(df_chart)} sample(s)")
        k2.metric("Specific Yield", f"{specific_yield:.2f}", f"kWh/kWp ({total_rated_kw:.1f} kWp)")
        k3.metric(peak_label, peak_val_str, f"At {peak_time}")
        k4.metric("Capacity Factor", f"{cf_pct:.1f}%", f"Avg {avg_val:.1f} {unit_label}")
        k5.metric("Est. Savings", f"₹{savings_inr:.1f}", f"@ ₹{tariff_inr:.2f}/kWh")
        k6.metric("CO₂ Offset", f"{co2_kg:.1f} kg", "Grid emissions avoided")

    st.divider()

    # Row 1 Charts
    if mobile:
        ch1, ch2 = st.container(), st.container()
    else:
        ch1, ch2 = st.columns(2)
    with ch1:
        if granularity == "intraday":
            st.markdown(f"**Intraday Power Curve & 3-Point Trend ({effective_start})**")
            base = alt.Chart(df_chart).encode(x=alt.X("period:N", title="Time", sort=None))
            area = base.mark_area(color="#f59e0b", opacity=0.25, line={"color": "#f59e0b"}).encode(
                y=alt.Y("total:Q", title="Power (W)"),
                tooltip=["period", "total", "moving_avg"],
            )
            ma_line = base.mark_line(color="#0ea5e9", strokeDash=[4, 4], strokeWidth=2).encode(
                y="moving_avg:Q"
            )
            st.altair_chart((area + ma_line).properties(height=280), width="stretch")
        else:
            st.markdown(f"**Total {granularity.capitalize()} Generation (kWh)**")
            bar = (
                alt.Chart(df_chart)
                .mark_bar(color="#f59e0b", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("period:N", title="Period", sort=None),
                    y=alt.Y("total:Q", title="Energy (kWh)"),
                    tooltip=["period", "total"],
                )
                .properties(height=280)
            )
            st.altair_chart(bar, width="stretch")

    with ch2:
        st.markdown(f"**Individual Microinverter Comparison ({unit_label})**")
        present_sns = [sn for sn in serial_numbers if sn in df_chart.columns]
        if present_sns:
            df_melt = df_chart.melt(
                id_vars=["period"],
                value_vars=present_sns,
                var_name="Inverter",
                value_name="Value",
            )
            line_chart = (
                alt.Chart(df_melt)
                .mark_line(point=True, strokeWidth=2)
                .encode(
                    x=alt.X("period:N", title="Period", sort=None),
                    y=alt.Y("Value:Q", title=unit_label),
                    color=alt.Color(
                        "Inverter:N",
                        scale=alt.Scale(range=INVERTER_COLORS[: len(present_sns)]),
                    ),
                    tooltip=["period", "Inverter", "Value"],
                )
                .properties(height=280)
            )
            st.altair_chart(line_chart, width="stretch")

    # Per-inverter stats
    per_inv_rows = []
    for sn in serial_numbers:
        sn_rows = [r for r in records if r.device_sn == sn]
        rated_w = RATED_CAPACITY_W.get(sn, 2000)
        powers = [r.power_w for r in sn_rows if r.power_w is not None]
        energies = [r.energy_kwh for r in sn_rows if r.energy_kwh is not None]
        peak_w = max(powers) if powers else None
        avg_w = (sum(powers) / len(powers)) if powers else None
        energy_kwh = (
            (max(energies) if energies else None)
            if granularity == "intraday"
            else (sum(energies) if energies else None)
        )
        yield_kwp = (energy_kwh / (rated_w / 1000.0)) if energy_kwh is not None else None
        cf_sn = (
            (avg_w / rated_w) * 100.0
            if (granularity == "intraday" and avg_w is not None)
            else (
                (energy_kwh / ((rated_w / 1000.0) * 24.0 * len(sn_rows))) * 100.0
                if (energy_kwh is not None and sn_rows)
                else None
            )
        )
        per_inv_rows.append(
            {
                "Serial Number": sn,
                "Rated (W)": rated_w,
                "Peak Power (W)": round(peak_w, 0) if peak_w is not None else None,
                "Avg Power (W)": round(avg_w, 0) if avg_w is not None else None,
                "Energy (kWh)": round(energy_kwh, 2) if energy_kwh is not None else None,
                "Yield (kWh/kWp)": round(yield_kwp, 2) if yield_kwp is not None else None,
                "Cap. Factor (%)": round(cf_sn, 1) if cf_sn is not None else None,
                "Savings (₹)": round(energy_kwh * tariff_inr, 1) if energy_kwh is not None else None,
            }
        )

    # Row 2 Charts
    if mobile:
        ch3, ch4 = st.container(), st.container()
    else:
        ch3, ch4 = st.columns(2)
    with ch3:
        st.markdown("**Inverter Energy Contribution Share (kWh)**")
        share_rows = [
            {"Inverter": r["Serial Number"], "Energy (kWh)": r["Energy (kWh)"]}
            for r in per_inv_rows
            if (r["Energy (kWh)"] or 0) > 0
        ]
        if not share_rows:
            st.info("No positive energy share recorded in this window.")
        else:
            df_share = pd.DataFrame(share_rows)
            donut = (
                alt.Chart(df_share)
                .mark_arc(innerRadius=55, outerRadius=95)
                .encode(
                    theta=alt.Theta("Energy (kWh):Q"),
                    color=alt.Color(
                        "Inverter:N",
                        scale=alt.Scale(range=INVERTER_COLORS[: len(share_rows)]),
                    ),
                    tooltip=["Inverter", "Energy (kWh)"],
                )
                .properties(height=250)
            )
            st.altair_chart(donut, width="stretch")

    with ch4:
        if granularity == "intraday":
            st.markdown("**Hourly Average Power Profile (W)**")
            df_chart["hour"] = df_chart["period"].astype(str).str.slice(0, 2) + ":00"
            df_hourly = df_chart.groupby("hour", as_index=False)["total"].mean().round(1)
            hbar = (
                alt.Chart(df_hourly)
                .mark_bar(color="#10b981", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("hour:N", title="Hour", sort=None),
                    y=alt.Y("total:Q", title="Avg Power (W)"),
                    tooltip=["hour", "total"],
                )
                .properties(height=250)
            )
            st.altair_chart(hbar, width="stretch")
        else:
            st.markdown("**3-Period Moving Average Trend (kWh)**")
            ma_area = (
                alt.Chart(df_chart)
                .mark_area(color="#8b5cf6", opacity=0.2, line={"color": "#8b5cf6"})
                .encode(
                    x=alt.X("period:N", title="Period", sort=None),
                    y=alt.Y("moving_avg:Q", title="Moving Avg (kWh)"),
                    tooltip=["period", "moving_avg"],
                )
                .properties(height=250)
            )
            st.altair_chart(ma_area, width="stretch")

    st.divider()
    st.markdown("**Per-Inverter Performance & Yield Analytics**")
    df_perf = pd.DataFrame(per_inv_rows)
    total_e_sum = df_perf["Energy (kWh)"].fillna(0).sum()
    df_perf["Share (%)"] = (
        (df_perf["Energy (kWh)"].fillna(0) / total_e_sum * 100.0).round(1)
        if total_e_sum > 0
        else 0.0
    )
    st.dataframe(df_perf, width="stretch", hide_index=True)
