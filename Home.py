import streamlit as st
import yfinance as yf
import pandas as pd
from utils import read_portfolio, get_google_sheet_data

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
    open_pos = portfolio_df[portfolio_df['Status'] == 'Open']
    active_positions = len(open_pos)
    
    if active_positions > 0:
        # We need to fetch live prices to calculate true total value
        # (We do a quick fetch here, or just use Entry Price for speed if preferred)
        # Let's do a quick estimate using Entry Price to save API calls on Home load, 
        # or fetch live if you prefer accuracy. Let's use Entry Price for speed:
        total_value = (open_pos['EntryPrice'] * open_pos['Quantity']).sum()
        
        # Identify largest position by invested amount
        open_pos['Invested'] = open_pos['EntryPrice'] * open_pos['Quantity']
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
    # For Live Value, visit the Portfolio page.
    st.metric(
        label="Invested Capital", 
        value=f"{total_value:,.0f} SEK",
        delta=f"{active_positions} Active Positions",
        delta_color="off"
    )

with col3:
    st.subheader("🏆 Top Holding")
    st.metric
