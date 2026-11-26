"""API Usage view: DeyeCloud API call counts, quota monitor, endpoint stats, and call logs."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.services import fetch_api_usage, format_local_time


def render_api_usage(mobile: bool = False) -> None:
    """Render the API Usage tab."""
    if mobile:
        top_l, top_r = st.container(), st.container()
    else:
        top_l, top_r = st.columns([4, 1])
    with top_l:
        st.subheader("🖥️ DeyeCloud API Call Log & Quota Monitor (IST)")
        st.caption("Every outbound request sent to DeyeCloud with call counts, latency, and Indian Standard Time (IST) timestamps")
    with top_r:
        if st.button("🔄 Reload Log", width="stretch"):
            st.rerun()

    usage = fetch_api_usage(limit=150)
    success_rate = (
        f"{(usage.success_calls / usage.total_calls) * 100:.1f}%"
        if usage.total_calls > 0
        else "100.0%"
    )
    quota_pct = (usage.calls_this_month / usage.monthly_quota) * 100.0

    if mobile:
        r1a, r1b = st.columns(2)
        r1a.metric(
            "Total Calls", usage.total_calls, f"{usage.success_calls} OK • {usage.error_calls} Err"
        )
        r1b.metric("Calls Today", usage.calls_today, "Since 00:00 IST")
        r2a, r2b = st.columns(2)
        r2a.metric(
            "Monthly Quota",
            usage.calls_this_month,
            f"{quota_pct:.3f}% of {usage.monthly_quota:,}",
        )
        r2b.metric("QPM", f"{usage.calls_last_minute} / {usage.qpm_limit}", "Rate headroom")
        st.metric("Success Rate", success_rate, "HTTP & API responses")
    else:
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric(
            "Total Calls Logged",
            usage.total_calls,
            f"{usage.success_calls} OK • {usage.error_calls} Err",
        )
        k2.metric("Calls Today", usage.calls_today, "Since 00:00 IST")
        k3.metric(
            "Monthly Quota",
            usage.calls_this_month,
            f"{quota_pct:.3f}% of {usage.monthly_quota:,}",
        )
        k4.metric("Last Minute (QPM)", f"{usage.calls_last_minute} / {usage.qpm_limit}", "Rate headroom")
        k5.metric("Success Rate", success_rate, "HTTP & API responses")

    st.divider()
    st.markdown("**API Calls by Endpoint**")
    if not usage.endpoints:
        st.info("No DeyeCloud API calls recorded yet. Click Refresh or Discover to make a call.")
    else:
        df_ep = pd.DataFrame(
            [
                {
                    "Endpoint": ep.endpoint,
                    "Total Calls": ep.total_calls,
                    "Success": ep.success_calls,
                    "Errors": ep.error_calls,
                    "Avg Latency (ms)": round(ep.avg_duration_ms, 0),
                    "Last Called": format_local_time(ep.last_called_at),
                }
                for ep in usage.endpoints
            ]
        )
        st.dataframe(df_ep, width="stretch", hide_index=True)

    st.divider()
    st.markdown(f"**Recent API Calls ({len(usage.recent_calls)})**")
    if not usage.recent_calls:
        st.info("No API calls logged yet.")
    else:
        df_recent = pd.DataFrame(
            [
                {
                    "Time": format_local_time(c.created_at),
                    "Method": c.method,
                    "Endpoint": c.endpoint,
                    "HTTP": str(c.status_code) if c.status_code is not None else "—",
                    "Duration (ms)": round(c.duration_ms, 0),
                    "Status": "✅ OK" if c.success else "❌ Error",
                    "Error": c.error_message or "—",
                }
                for c in usage.recent_calls
            ]
        )
        st.dataframe(df_recent, width="stretch", hide_index=True, height=420)
