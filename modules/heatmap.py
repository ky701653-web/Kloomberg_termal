"""Module 6: Sector & Nifty 50 Treemap Heatmaps."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from data.market_data import SECTOR_INDICES, fetch_nifty50_heatmap_data, fetch_yfinance_quotes
from utils.formatting import format_number, format_pct
from utils.ui import get_plotly_theme, get_theme_palette, render_csv_download, render_plotly, render_section_header, style_change_dataframe


def render_heatmap() -> None:
    """Render Nifty 50 constituent treemap and NSE Sectoral Indices heatmap."""
    render_section_header("Sector & Nifty 50 Market Heatmap")

    tab_n50, tab_sec = st.tabs(["Nifty 50 Treemap", "NSE Sectoral Indices"])

    with tab_n50:
        with st.spinner("Loading Nifty 50 constituent heatmap..."):
            rows, is_stale, ts_ist = fetch_nifty50_heatmap_data(ttl_seconds=180)
        if is_stale:
            st.warning(f"Showing cached Nifty 50 heatmap from {ts_ist}.")
        else:
            st.caption(f"Sized by traded turnover proxy; colored by daily % change | Updated: {ts_ist}")

        if rows:
            pal = get_theme_palette()
            ptheme = get_plotly_theme()
            df = pd.DataFrame(rows)
            df["label"] = df.apply(
                lambda r: f"{r['name']}<br>{format_pct(r['pct_change'])}", axis=1
            )
            fig = px.treemap(
                df,
                path=[px.Constant("Nifty 50"), "sector", "name"],
                values="weight_proxy",
                color="pct_change",
                color_continuous_scale=[pal["down"], pal["surface_alt"], pal["up"]],
                color_continuous_midpoint=0.0,
                range_color=[-4.0, 4.0],
                hover_data={"price": True, "pct_change": ":.2f", "weight_proxy": False},
            )
            fig.update_traces(texttemplate="%{label}<br>%{customdata[1]:+.2f}%", textposition="middle center")
            fig.update_layout(
                template=ptheme["template"],
                paper_bgcolor=ptheme["paper_bgcolor"],
                font=dict(family="Inter, sans-serif", color=ptheme["font_color"]),
                height=580,
                margin=dict(l=8, r=8, t=24, b=8),
            )
            render_plotly(fig)
            render_csv_download(
                df[["name", "symbol", "sector", "price", "change", "pct_change"]],
                "nifty50_heatmap.csv",
                label="Download Nifty 50 Heatmap CSV",
            )
        else:
            st.info("Nifty 50 constituent quotes unavailable right now.")

    with tab_sec:
        with st.spinner("Loading NSE Sectoral Indices..."):
            sec_rows, sec_stale, sec_ts = fetch_yfinance_quotes(
                SECTOR_INDICES, cache_key="nse_sector_indices", ttl_seconds=180
            )
        if sec_stale:
            st.warning(f"Showing cached sector indices from {sec_ts}.")
        if sec_rows:
            pal = get_theme_palette()
            ptheme = get_plotly_theme()
            sdf = pd.DataFrame(sec_rows).sort_values("pct_change", ascending=False)
            sdf["pct_abs"] = sdf["pct_change"].abs().clip(lower=0.25)
            fig_s = px.treemap(
                sdf,
                path=[px.Constant("NSE Sectors"), "name"],
                values="pct_abs",
                color="pct_change",
                color_continuous_scale=[pal["down"], pal["surface_alt"], pal["up"]],
                color_continuous_midpoint=0.0,
                range_color=[-3.5, 3.5],
                hover_data={"price": True, "pct_change": ":.2f", "pct_abs": False},
            )
            fig_s.update_traces(texttemplate="%{label}<br>%{customdata[1]:+.2f}%", textposition="middle center")
            fig_s.update_layout(
                template=ptheme["template"],
                paper_bgcolor=ptheme["paper_bgcolor"],
                font=dict(family="Inter, sans-serif", color=ptheme["font_color"]),
                height=420,
                margin=dict(l=8, r=8, t=20, b=8),
            )
            render_plotly(fig_s)

            disp = pd.DataFrame(
                [
                    {
                        "Sector Index": r["name"],
                        "Ticker": r["symbol"],
                        "Level": format_number(r["price"]),
                        "Chg": f"{r['change']:+.2f}",
                        "% Chg": format_pct(r["pct_change"]),
                    }
                    for r in sdf.to_dict(orient="records")
                ]
            )
            st.dataframe(style_change_dataframe(disp, ["Chg", "% Chg"]), width="stretch", hide_index=True)
            render_csv_download(disp, "nse_sector_indices.csv", label="Download Sector Indices CSV")
        else:
            st.info("Sectoral index data temporarily unavailable.")
