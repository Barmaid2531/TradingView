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
    # Filter for open positions
    open_pos = portfolio_df[portfolio_df['Status'] == 'Open'].copy()
    
    if not open_pos.empty:
        active_positions = len(open_pos)
        
        # --- SAFETY FIX: Force columns to numeric to prevent crashes ---
        open_pos['EntryPrice'] = pd.to_numeric(open_pos['EntryPrice'], errors='coerce').fillna(0)
        open_pos['Quantity'] = pd.to_numeric(open_pos['Quantity'], errors='coerce').fillna(0)
        
        # Calculate Total Invested Capital (Entry Price * Qty)
        open_pos['Invested'] = open_pos['EntryPrice'] * open_pos['Quantity']
        total_value = open_pos['Invested'].sum()
        
        # Find largest holding
        if total_value > 0:
            top_holding = open_pos.sort_values('Invested', ascending=False).iloc[0]['Ticker']

# --- DASHBOARD UI ---

# Row 1: High Level Metrics
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🇸🇪 Market (OMXSPI)")
    if market_price:
        color = "green" if market_change >= 0 else "red"
        st.metric(
            label=f"Trend: {market_trend}",
            value=f"{market_price:,.2f}",
            delta=f"{market_change:.2f}%"
        )
    else:
        st.warning("Market data unavailable")

with col2:
    st.subheader("💼 Portfolio Equity")
    # Note: This is based on Entry Price (Invested Capital). 
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

# Row 2: Quick Actions / Navigation
st.subheader("🚀 Quick Actions")

c1, c2, c3 = st.columns(3)

with c1:
    with st.container(border=True):
        st.markdown("### 🔍 Deep Analysis")
        st.write("Analyze individual stocks with RSI, MACD, and AI scoring.")
        st.page_link("pages/Analysis.py", label="Go to Analysis", icon="🔍")

with c2:
    with st.container(border=True):
        st.markdown("### 🤖 AI Screener")
        st.write("Scan the entire OMXS30 index for buy/sell signals.")
        st.page_link("pages/AI_Screener.py", label="Go to Screener", icon="🤖")

with c3:
    with st.container(border=True):
        st.markdown("### 📝 Manage Portfolio")
        st.write("View live P/L, close positions, and add new trades.")
        st.page_link("pages/My_Portfolio.py", label="Go to Portfolio", icon="📝")

# Row 3: Recent Activity
if not portfolio_df.empty:
    closed_trades = portfolio_df[portfolio_df['Status'] != 'Open']
    if not closed_trades.empty:
        st.markdown("---")
        st.subheader("📜 Recently Closed Trades")
        st.dataframe(closed_trades.tail(3), use_container_width=True)
