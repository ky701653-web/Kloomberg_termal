# IND TERMINAL — Free Bloomberg-Style Financial Terminal (India First)

A local, open-source, Bloomberg-inspired financial terminal built in **Python 3.11+ and Streamlit**, designed for Indian equities, derivatives, mutual funds, macro, news, and portfolio analytics (**NSE, BSE, Nifty, Sensex, INR**) using 100% free data sources.

---

## Implemented Modules (19 Live Panels + Command Bar)

1. **Home / Market Overview (`HOME`)** — Parallel-loaded Nifty 50, Sensex, Bank Nifty, India VIX, USD/INR, Gold, WTI & Brent Crude, Global Indices, IST Market Status clock (handles NSE hours & Indian holidays), **AI Daily Market Summary** (built-in VADER/NLP brief + optional Gemini/OpenAI enhancement), Nifty 50 Advance/Decline breadth, Top 5 Gainers & Losers, Auto-Refresh (30s/60s), and CSV exports.
2. **Watchlist (`WL`)** — Persistent NSE/BSE ticker watchlist stored in SQLite (`60s` TTL cache), showing LTP, change, % change, volume, 52-week range progress bar, and 25-day sparklines.
3. **Charting (`<TICKER> GP`)** — Interactive Plotly candlestick + volume charts, multi-timeframe selector (`5D` to `MAX`), toggles for **SMA 20/50/200**, **EMA 20**, **Bollinger Bands**, **Supertrend (10,3)**, **VWAP**, **RSI (14)**, **MACD (12,26,9)**, multi-ticker comparison, and **Rebased vs Nifty 50 (`^NSEI = 100`)**.
4. **Backtesting (`<TICKER> BT`)** — Long-only strategy backtester for **Moving-Average Crossover (SMA/EMA)** and **RSI Mean Reversion** with 1-bar lagged execution, transaction costs (bps), equity curve vs Buy & Hold, drawdown chart, CAGR, Sharpe, win rate, and trade log CSV export.
4. **Fundamentals (`<TICKER> FA`)** — Quarterly & annual income statements, balance sheet, cash flows, valuation & profitability ratios (P/E, P/B, ROE, D/E, Dividend Yield, Market Cap in ₹ Cr / lakh crore), and sector peer comparison.
5. **Screener (`SCREEN`)** — Scans the local **Nifty 500** universe ([data/nifty500.csv](data/nifty500.csv)) in cached batches of 50 tickers, with filters for Sector, Market Cap, P/E, P/B, ROE, Dividend Yield, RSI, 52W-high proximity, and Volume Spike, plus **3 prebuilt screens** and **custom saved screens**.
6. **Sector & Nifty Heatmap (`HEATMAP`)** — Interactive Plotly treemaps for Nifty 50 constituents (grouped by sector) and NSE Sectoral Indices.
7. **F&O / Options (`NIFTY OPT`)** — NSE option chain (via polite NSE session + `nselib` fallback), Call/Put Open Interest chart, PCR (OI & Volume), Max Pain strike & payout curve, and India VIX context.
8. **FII / DII Flows (`FII` / `DII`)** — Cash market institutional buy/sell/net flows in ₹ Crores.
9. **Macro Dashboard (`MACRO`)** — India & Global macro series via World Bank Open Data, Yahoo Finance (`INR=X`, `^TNX`, `DXY`, `Brent`, `Gold`), RBI/MOSPI policy benchmarks, and optional live **FRED API** series (`FRED_API_KEY`).
10. **News Feed (`NEWS <TICKER>`)** — Aggregates Economic Times, Moneycontrol, LiveMint, Business Standard, and Google News India RSS feeds with **VADER sentiment** scoring (`Bullish` / `Neutral` / `Bearish`).
11. **Corporate Actions & Filings (`<TICKER> CORP`)** — NSE corporate actions, exchange announcements, and Yahoo dividend/split history.
12. **IPO Tracker (`IPO`)** — NSE current & upcoming IPOs plus live Indian IPO news RSS fallback.
13. **Mutual Funds (`MF`)** — Searches Indian AMFI schemes via `mfapi.in`, plots historical NAVs, computes 1Y/3Y/5Y CAGR, and includes an INR **SIP Wealth Calculator**.
14. **Portfolio Tracker (`PORT`)** — Manual lot entry + CSV import/export, live valuation in ₹, P&L, **XIRR**, allocation donut chart, **Beta vs Nifty 50**, annualized volatility, Sharpe ratio, max drawdown, and **Indian Capital Gains Tax Estimate** (**STCG 20% u/s 111A** for ≤ 12 months; **LTCG 12.5% u/s 112A** above ₹1.25 lakh annual exemption for > 12 months).
15. **Crypto & FX (`FX` / `CRYPTO`)** — CoinGecko top cryptocurrencies in INR (with 7D sparklines) and Frankfurter ECB FX cross-rates vs INR + currency converter.
16. **Alerts (`ALERTS`)** — Price, Daily % Move, RSI, and SMA 20/50 Crossover rules with in-app trigger logs and optional **Telegram Bot** / **SMTP Email** delivery.
18. **Broker Feeds (Real-Time) (`BROKER`)** — Live REST quote integration for **Zerodha Kite Connect**, **Upstox v2**, and **Angel One SmartAPI** using `.env` / `st.secrets` credentials, plus full data/legal disclosures.
19. **Data Source Status (`STATUS`)** — Live health monitor, IST timestamps, delay disclosures, errors, and one-click SQLite cache reset.

> **UI Features:** Toggle between **Dark** (Bloomberg black/orange) and **Light** themes in the sidebar, and press **`/`** or **`Ctrl+K`** anywhere to focus the Command Bar.

---

## Local Setup (Windows / macOS / Linux)

### 1. Clone or open the project folder
```bash
cd india_terminal
```

### 2. Create and activate a virtual environment (Python 3.11+)
- **Windows (PowerShell):**
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  ```
- **Windows (Git Bash):**
  ```bash
  python -m venv .venv
  source .venv/Scripts/activate
  ```
- **macOS / Linux:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure optional environment variables
Copy `.env.example` to `.env` (never commit `.env` to Git):
```bash
cp .env.example .env
```
- `FRED_API_KEY` *(optional)* — Free key from [FRED](https://fred.stlouisfed.org/docs/api/api_key.html) for live Macro Dashboard series.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` *(optional)* — For Telegram alert notifications.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO` *(optional)* — For email alert notifications.

### 5. Run unit tests
```bash
python -m unittest discover -s tests -v
```

### 6. Launch the terminal
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

---

## Free Deployment on Streamlit Community Cloud

1. **Push your code to GitHub**
   - Verify `.gitignore` excludes `.env`, `.venv/`, and `cache/*.db*`.
   - Commit and push `app.py`, `requirements.txt`, `.streamlit/config.toml`, `data/`, `modules/`, `utils/`, and `tests/`.
2. **Create the app on Streamlit Community Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
   - Click **New app**, select your repository, branch, and set **Main file path** to `app.py`.
3. **Store secrets safely (`st.secrets`)**
   - Do **not** upload `.env` to GitHub.
   - In Streamlit Cloud → **App Settings → Secrets**, paste your optional keys in TOML format:
     ```toml
     FRED_API_KEY = "your_fred_key_here"
     TELEGRAM_BOT_TOKEN = "your_bot_token"
     TELEGRAM_CHAT_ID = "your_chat_id"
     SMTP_HOST = "smtp.gmail.com"
     SMTP_PORT = "587"
     SMTP_USER = "you@example.com"
     SMTP_PASSWORD = "your_app_password"
     ALERT_EMAIL_TO = "you@example.com"
     ```
   - `utils/secrets.py` automatically reads from `.env` locally and falls back to `st.secrets` in Streamlit Cloud.
4. **Deploy** — Click **Deploy**; Streamlit Community Cloud installs `requirements.txt` and serves your terminal over HTTPS for free.

> **Note on cloud hosting & NSE APIs:** NSE India public endpoints sometimes block datacenter IP ranges. All NSE panels automatically log the status in **Data Source Status** and fall back to `yfinance`, `nselib`, or cached SQLite snapshots where available.

---

## Data Limitations, Broker APIs & Legal Disclaimer

- **Delay:** `yfinance` and most free feeds are delayed (~15 minutes) or end-of-day. True real-time tick-by-tick data requires a paid or account-linked broker API.
- **Broker APIs (Optional Future Module):** If you hold an account with **Zerodha (Kite Connect)**, **Upstox**, **Angel One (SmartAPI)**, or **Fyers**, their APIs provide real-time quotes/WebSockets (some free with an account, others paid). See the **Broker Feeds (Real-Time)** panel (`BROKER`) inside the app.
- **Unofficial Sources:** `yfinance` and NSE public endpoints are unofficial and can change or rate-limit without notice; SQLite fallbacks keep cached snapshots available.
- **Fundamentals Coverage:** Yahoo Finance fundamentals for Indian stocks can be incomplete or inconsistent — always cross-check key numbers against official **BSE/NSE filings**.
- **What Is Not Available Free:** Bloomberg's proprietary analytics, IB messaging network, institutional fixed-income/derivatives pricing, and full historical tick data. Free sources cover roughly **70–80%** of what individual investors use.
- **Legality & Terms:** Respect each provider's Terms of Service and rate limits. Use this app strictly for **personal research** — do not redistribute or resell market data.
- **Not Investment Advice:** Indicators, screens, tax estimates, and VADER sentiment tags are for education and research only. Always verify before making decisions with real money.
