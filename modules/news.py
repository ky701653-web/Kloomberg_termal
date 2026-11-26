"""Module 10: Indian & Global Financial News Feed with VADER Sentiment."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from data.macro_news_mf import fetch_news_feed
from utils.ui import (
    get_theme_palette,
    render_csv_download,
    render_metric_card,
    render_section_header,
    sanitize_http_url,
)


def render_news() -> None:
    """Render aggregated financial RSS feed with ticker filter and VADER sentiment."""
    render_section_header("Market News Feed & VADER Sentiment (ET • Moneycontrol • Mint • BS • Google News)")
    pal = get_theme_palette()

    default_q = st.session_state.get("active_query") or ""
    c1, c2, c3 = st.columns([3, 1.5, 1])
    with c1:
        query = st.text_input(
            "Filter by ticker or keyword (leave blank for broad Indian market news)",
            value=default_q,
            placeholder="e.g. HDFCBANK, RBI, Nifty, Reliance",
            key="news_query_input",
        )
    with c2:
        sent_filter = st.selectbox("Sentiment", options=["All", "Bullish", "Neutral", "Bearish"], key="news_sent_filter")
    with c3:
        if st.button("Fetch News", width="stretch", type="primary"):
            st.rerun()

    with st.spinner("Aggregating RSS feeds and scoring sentiment..."):
        articles, is_stale, ts_ist = fetch_news_feed(query=query, ttl_seconds=600)

    if is_stale:
        st.warning(f"Showing cached news from {ts_ist}.")
    else:
        st.caption(f"Updated: {ts_ist} | Articles loaded: {len(articles)}")

    if not articles:
        st.info("No matching headlines found. Try clearing the keyword filter or retrying.")
        return

    df = pd.DataFrame(articles)
    bull_cnt = int((df["sentiment"] == "Bullish").sum())
    neut_cnt = int((df["sentiment"] == "Neutral").sum())
    bear_cnt = int((df["sentiment"] == "Bearish").sum())
    avg_score = float(df["sentiment_score"].mean())

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_metric_card("Avg VADER Score", f"{avg_score:+.3f}", change=avg_score)
    with m2:
        render_metric_card("Bullish Headlines", str(bull_cnt))
    with m3:
        render_metric_card("Neutral Headlines", str(neut_cnt))
    with m4:
        render_metric_card("Bearish Headlines", str(bear_cnt))

    if sent_filter != "All":
        df = df[df["sentiment"] == sent_filter]

    for _, row in df.iterrows():
        s_label = str(row["sentiment"])
        color = pal["up"] if s_label == "Bullish" else (pal["down"] if s_label == "Bearish" else pal["muted"])
        safe_src = html.escape(str(row["source"]))
        safe_pub = html.escape(str(row["published"]))
        safe_title = html.escape(str(row["title"]))
        safe_link = sanitize_http_url(str(row["link"]))
        st.markdown(
            f"""
            <div class="it-feed-card" style="border-left: 3px solid {color};">
                <div class="it-feed-meta">
                    <span><strong style="color:{pal['accent']};">{safe_src}</strong> &bull; {safe_pub}</span>
                    <span class="it-mono" style="color:{color}; font-weight:600;">{s_label.upper()} ({row['sentiment_score']:+.2f})</span>
                </div>
                <div class="it-feed-title">
                    <a href="{safe_link}" target="_blank" rel="noopener noreferrer">{safe_title}</a>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_csv_download(df, "india_market_news.csv", label="Download News & Sentiment CSV")
