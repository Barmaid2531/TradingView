import streamlit as st
import yfinance as yf
import pandas as pd
from utils import read_portfolio

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Trading Dashboard",
    layout="wide",
    page_icon="📈"
)

st.title("📈 Trading Command Center")

# --- 1. MARKET PULSE SECTION ---
@st.cache_data(ttl=3600)
def get_market_status():
    try:
        # Stockholm All Share Index
        ticker = "^OMXSPI" 
        data = yf.Ticker(ticker).history(period="3mo")
        
        if data.empty: return None, None, None
        
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        # Calculate Trend
        sma50 = data['Close'].rolling(window=50).mean().iloc[-1]
        trend = "Bullish 🐂" if latest['Close'] > sma50 else "Bearish 🐻"
        
        # Calculate Daily Change
        change = ((latest['Close'] - prev['Close']) / prev['Close']) * 100
        
        return latest['Close'], change, trend
    except Exception:
        return None, None, None

market_price, market_change, market_trend = get_market_status()

# --- 2. PORTFOLIO SUMMARY SECTION ---
portfolio_df = read_portfolio()
total_value = 0.0
active_positions = 0
top_holding = "None"

if not portfolio_df.empty:
    open_pos = portfolio_df[portfolio_df['Status'] == 'Open'].copy()
    
    if not open_pos.empty:
        active_positions = len(open_pos)
        
        # Safety: Force columns to numeric
        open_pos['EntryPrice'] = pd.to_numeric(open_pos['EntryPrice'], errors='coerce').fillna(0)
        open_pos['Quantity'] = pd.to_numeric(open_pos['Quantity'], errors='coerce').fillna(0)
        
        # Calculate Invested Capital
        open_pos['Invested'] = open_pos['EntryPrice'] * open_pos['Quantity']
        total_value = open_pos['Invested'].sum()
        
        if total_value > 0:
            top_holding = open_pos.sort_values('Invested', ascending=False).iloc[0]['Ticker']

# --- DASHBOARD UI ---

# Row 1: High Level Metrics
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🇸🇪 Market (OMXSPI)")
    if market_price:
        st.metric(
            label=f"Trend: {market_trend}",
            value=f"{market_price:,.2f}",
            delta=f"{market_change:.2f}%"
        )
    else:
        st.warning("Market data unavailable")

with col2:
    st.subheader("💼 Portfolio Equity")
    st.metric(
        label="Invested Capital", 
        value=f"{total_value:,.0f} SEK",
        delta=f"{active_positions} Active Positions",
        delta_color="off"
    )

with col3:
    st.subheader("🏆 Top Holding")
    st.metric(label="Largest Position", value=top_holding)

st.markdown("---")

# --- 3. QUICK ACTIONS GRID (Manually Updated) ---
st.subheader("🚀 Trading Tools")

# Row 2: Core Tools
c1, c2, c3, c4 = st.columns(4)

with c1:
    with st.container(border=True):
        st.markdown("### 📝 Portfolio")
        st.write("Manage your active positions.")
        st.page_link("pages/My_Portfolio.py", label="Open Portfolio", icon="💼")

with c2:
    with st.container(border=True):
        st.markdown("### 🤖 Screener")
        st.write("Scan OMXS30 for signals.")
        st.page_link("pages/AI_Screener.py", label="Open Screener", icon="📡")

with c3:
    with st.container(border=True):
        st.markdown("### 🔍 Analysis")
        st.write("Deep dive charts & EMA.")
        st.page_link("pages/Analysis.py", label="Open Analysis", icon="📈")

with c4:
    with st.container(border=True):
        st.markdown("### ⚡ Swing Strat")
        st.write("Find 5% weekly plays.")
        st.page_link("pages/Swing_Strategy.py", label="Run Scanner", icon="🚀")

# Row 3: Advanced Research (The New Stuff)
st.subheader("🧠 Advanced Research")
r1, r2, r3, r4 = st.columns(4)

with r1:
    with st.container(border=True):
        st.markdown("### 📰 Sentiment")
        st.write("AI News Analysis.")
        st.page_link("pages/6_Sentiment_AI.py", label="Check Mood", icon="🗞️")

with r2:
    with st.container(border=True):
        st.markdown("### 🔮 Forecast")
        st.write("AI Price Prediction.")
        st.page_link("pages/7_Forecast_Prophet.py", label="See Future", icon="🔮")

with r3:
    with st.container(border=True):
        st.markdown("### 🛠️ Backtest")
        st.write("Test your strategies.")
        st.page_link("pages/8_Backtest_Strategy.py", label="Run Test", icon="⚙️")

with r4:
    # Placeholder for future tools or external links
    with st.container(border=True):
        st.markdown("### 🔗 News")
        st.write("External Market News.")
        st.link_button("Dagens Industri", "https://www.di.se")

# Row 4: Recent Activity
if not portfolio_df.empty:
    closed_trades = portfolio_df[portfolio_df['Status'] != 'Open']
    if not closed_trades.empty:
        st.markdown("---")
        st.subheader("📜 Recently Closed Trades")
        st.dataframe(closed_trades.tail(3), use_container_width=True)
