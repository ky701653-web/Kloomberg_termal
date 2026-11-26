"""Module 8: FII / DII Cash Market Institutional Flows."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data.nse_data import fetch_fii_dii_flows
from utils.formatting import format_inr
from utils.ui import render_csv_download, render_metric_card, render_section_header, style_change_dataframe


def render_fii_dii() -> None:
    """Render FII/DII net buying & selling flows table and chart."""
    render_section_header("FII / DII Cash Market Flows (₹ Crores)")

    with st.spinner("Fetching FII/DII institutional activity..."):
        rows, is_stale, ts_ist = fetch_fii_dii_flows(ttl_seconds=900)

    if is_stale:
        st.warning(f"Showing cached FII/DII flows from {ts_ist}.")

    if not rows:
        st.warning(
            "FII/DII data from NSE is currently blocked or unavailable. "
            "Check **Data Source Status** for error details and retry in a few minutes."
        )
        return

    df = pd.DataFrame(rows)
    st.caption(f"Source: NSE India / nselib | Updated: {ts_ist}")

    # Latest metrics per category
    latest_cards = df.groupby("category", as_index=False).first()
    cols = st.columns(max(1, len(latest_cards)))
    for col, (_, item) in zip(cols, latest_cards.iterrows()):
        with col:
            net_cr = float(item.get("net_value_cr", 0.0))
            render_metric_card(
                label=f"{item['category']} ({item['date']})",
                value_str=f"₹{net_cr:+,.2f} Cr",
                change=net_cr,
                subtext=f"Buy ₹{item['buy_value_cr']:,.0f} Cr | Sell ₹{item['sell_value_cr']:,.0f} Cr",
            )

    fig = go.Figure()
    for cat, color in [("FII/FPI", "#FF8C00"), ("DII", "#00C805")]:
        sub = df[df["category"].str.contains(cat.split("/")[0], case=False, na=False)]
        if not sub.empty:
            fig.add_trace(go.Bar(x=sub["date"], y=sub["net_value_cr"], name=cat, marker_color=color))
    if not fig.data:
        fig.add_trace(go.Bar(x=df["category"] + " " + df["date"], y=df["net_value_cr"], name="Net (₹ Cr)", marker_color="#FF8C00"))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#0D0F12",
        barmode="group",
        height=380,
        yaxis_title="Net Flow (₹ Crores)",
    )
    st.plotly_chart(fig, width="stretch")

    disp = pd.DataFrame(
        {
            "Category": df["category"],
            "Date": df["date"],
            "Buy (₹ Cr)": df["buy_value_cr"].apply(lambda v: format_inr(v * 1e7, compact=True)),
            "Sell (₹ Cr)": df["sell_value_cr"].apply(lambda v: format_inr(v * 1e7, compact=True)),
            "Net (₹ Cr)": df["net_value_cr"].apply(lambda v: f"{v:+,.2f}"),
        }
    )
    st.dataframe(style_change_dataframe(disp, ["Net (₹ Cr)"]), width="stretch", hide_index=True)
    render_csv_download(df, "fii_dii_flows.csv", label="Download FII/DII CSV")
