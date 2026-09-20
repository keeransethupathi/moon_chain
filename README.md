# ⚡ Moon Chain - Real-Time Fyers Option Chain & Candlestick Terminal

A high-performance, real-time Indian Markets Option Chain and Candlestick Trading Dashboard built with **Streamlit**, **Fyers API v3**, and **TradingView Lightweight Charts** featuring an automated **5-second refresh interval**.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B.svg)
![Fyers API](https://img.shields.io/badge/Fyers%20API-v3-0284c7.svg)
![TradingView](https://img.shields.io/badge/TradingView-Lightweight%20Charts-2962ff.svg)
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/deploy?repository=keeransethupathi/moon_chain&branch=main&mainModule=app.py)

---

## 🌟 Key Features

- **⚡ Live 5-Second Interval Streaming**:
  - Powered by Streamlit's `@st.fragment(run_every="5s")` for non-blocking, flicker-free real-time market updates.
  - Live polling of active option chains directly from the Fyers API v3.

- **📊 Side-by-Side Option Chain Matrix**:
  - Classic institutional trading desk layout: **Calls (CE)** on the left, **Strike Price** in the middle, and **Puts (PE)** on the right.
  - Per-contract metrics: Open Interest (OI), Net OI Change, Volume, IV, LTP, and Day Change %.
  - Visual In-The-Money (ITM) amber tinting and At-The-Money (ATM) gold highlight.

- **🕯️ TradingView Lightweight Charts (Canvas-Based)**:
  - Ultra-fast 60 FPS canvas rendering powered by TradingView's official Lightweight Charts library.
  - **200 EMA (Exponential Moving Average)** plotted directly on 5-second candles.
  - Real-time crosshair price tracking and interactive contract specs.

- **🎯 Interactive Strike Selection**:
  - Click or select any strike price from the chain to instantly view its live 5-second candlestick chart.
  - Toggle between `🔵 Call (CE)` and `🔴 Put (PE)` options.

- **🔐 Fyers API v3 OAuth Authentication**:
  - Integrated Token Manager with direct access token paste and 1-click OAuth login generation.
  - Uses Fyers' official sample redirect URI (`https://trade.fyers.in/api-login/redirect-uri/index.html`) to display the authorization code on-screen.

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/keeransethupathi/moon_chain.git
cd moon_chain
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch the Terminal
```bash
streamlit run app.py
```
Open **`http://localhost:8501`** in your browser.

---

## ⚙️ Configuration & Fyers API Setup

1. Log in to your [Fyers API Dashboard](https://myapi.fyers.in/dashboard/).
2. Create or open your App and set the **Redirect URL** to:
   ```text
   https://trade.fyers.in/api-login/redirect-uri/index.html
   ```
3. In the application's sidebar or authentication card, click **Open Fyers Login Page ↗**.
4. Log in with your Fyers credentials, copy the authorization code from the redirected page, paste it into the dashboard, and click **Generate & Connect**.

---

## 📂 Project Structure

```
moon_chain/
├── app.py              # Main Streamlit application and UI layout
├── candle_service.py   # 5-second candlestick generator & TradingView charts
├── fyers_service.py    # Fyers API v3 client, OAuth flow, and data parser
├── requirements.txt    # Python dependencies
├── .gitignore          # Excludes logs, cache, and sensitive session tokens
└── README.md           # Project documentation
```

---

## 📜 License
MIT License
