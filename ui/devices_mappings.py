"""Devices & Mappings view: station discovery and measurement point mapping editor."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.schemas import MappingUpdateItem
from ui.services import (
    fetch_devices,
    fetch_mappings,
    save_mappings,
    trigger_discover_devices,
)


def render_devices_mappings(mobile: bool = False) -> None:
    """Render the Devices & Mappings tab."""
    if mobile:
        top_l, top_r = st.container(), st.container()
    else:
        top_l, top_r = st.columns([3, 1])
    with top_l:
        st.subheader("🔧 Configured Microinverters")
        st.caption("Discover station bindings and supported DeyeCloud measurement points.")
    with top_r:
        if st.button("📡 Discover Devices & Points", type="primary", width="stretch"):
            with st.spinner("Discovering devices and measurePoints from DeyeCloud..."):
                res = trigger_discover_devices()
            if res.errors:
                st.error(" | ".join(res.errors))
            else:
                st.success(res.message)

    devices = fetch_devices()
    if devices:
        if mobile:
            for dev in devices:
                with st.container(border=True):
                    st.markdown(f"**{dev.name}**")
                    st.caption(f"Status: `{dev.status}`")
                    st.write(f"- **SN:** `{dev.device_sn}`")
                    st.write(f"- **Type:** `{dev.device_type}`")
                    st.write(f"- **Station ID:** `{dev.station_id or 'Not bound'}`")
                    st.write(f"- **Discovered Points:** `{len(dev.available_points)}`")
        else:
            dev_cols = st.columns(min(3, len(devices)))
            for idx, dev in enumerate(devices):
                with dev_cols[idx % len(dev_cols)]:
                    with st.container(border=True):
                        st.markdown(f"**{dev.name}**")
                        st.caption(f"Status: `{dev.status}`")
                        st.write(f"- **SN:** `{dev.device_sn}`")
                        st.write(f"- **Type:** `{dev.device_type}`")
                        st.write(f"- **Station ID:** `{dev.station_id or 'Not bound'}`")
                        st.write(f"- **Discovered Points:** `{len(dev.available_points)}`")

    st.divider()
    map_res = fetch_mappings()

    if mobile:
        left, right = st.container(), st.container()
    else:
        left, right = st.columns([2, 1])
    with left:
        st.subheader("Measurement Field Mappings")
        st.caption("Edit DeyeCloud keys mapped to dashboard fields and click Save Mappings.")

        df_map = pd.DataFrame(
            [
                {
                    "dashboard_field": m.dashboard_field,
                    "Label": m.label,
                    "Category": m.category,
                    "Unit": m.unit or "",
                    "DeyeCloud Key": m.deye_key or "",
                }
                for m in map_res.mappings
            ]
        )

        available_keys = sorted({pt.key for pt in map_res.available_points if pt.key})
        edited_df = st.data_editor(
            df_map,
            width="stretch",
            hide_index=True,
            disabled=["dashboard_field", "Label", "Category", "Unit"],
            column_config={
                "dashboard_field": st.column_config.TextColumn("Field ID"),
                "DeyeCloud Key": st.column_config.TextColumn(
                    "DeyeCloud Key",
                    help=(
                        f"Available keys: {', '.join(available_keys[:10])}..."
                        if available_keys
                        else "Enter DeyeCloud key"
                    ),
                ),
            },
            key="mappings_editor",
        )

        if st.button("💾 Save Mappings", type="primary"):
            payload = [
                MappingUpdateItem(
                    dashboard_field=str(row["dashboard_field"]),
                    deye_key=str(row["DeyeCloud Key"]).strip() or None,
                )
                for _, row in edited_df.iterrows()
            ]
            save_mappings(payload)
            st.success("Measurement mappings saved. Live dashboard values will reflect updated keys.")
            st.rerun()

    with right:
        st.subheader(f"Unmapped Points ({len(map_res.unmapped_points)})")
        st.caption(
            "Measurement keys returned by DeyeCloud that are not currently assigned to any dashboard field."
        )
        if not map_res.unmapped_points:
            st.info(
                "No unmapped measurement points discovered yet. "
                "Run **Discover Devices & Points** or refresh live data."
            )
        else:
            df_unmapped = pd.DataFrame(
                [
                    {
                        "Key": pt.key,
                        "Name": pt.name or "Unnamed",
                        "Unit": pt.unit or "",
                    }
                    for pt in map_res.unmapped_points
                ]
            )
            st.dataframe(df_unmapped, width="stretch", hide_index=True, height=520)
