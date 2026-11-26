"""Unified secret/env loader supporting local .env and Streamlit Community Cloud secrets."""

from __future__ import annotations

import os


def get_secret(key: str, default: str = "") -> str:
    """Read a config secret from environment variables (.env) or st.secrets."""
    env_val = os.getenv(key)
    if env_val:
        return env_val.strip()

    try:
        import streamlit as st

        if key in st.secrets:
            val = str(st.secrets[key]).strip()
            if val:
                return val
    except Exception:  # noqa: BLE001
        pass

    return default
