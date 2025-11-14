# pages/Swing_Strategy.py
import streamlit as st
import yfinance as yf
import pandas as pd
import sys
import os
import time

# --- SETUP ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import STOCK_LIST

st.set_page_config(layout="wide", page_title="5% Swing Strategy")

# --- BATCH ANALYSIS FUNCTION ---
# Updated to process a whole DataFrame of tickers at once for speed
def analyze_market_data(ticker, hist):
    """
    Analyzes a single stock's history for swing signals.
    """
    try:
        if len(hist) < 20: return None

        # Drop rows where Open/Close are NaN (common in batch downloads)
        hist = hist.dropna(subset=['Close', 'Open'])
        if hist.empty: return None

        # 1. Volatility Check
        hist['Daily_Range_Pct'] = (hist['High'] - hist['Low']) / hist['Close']
        avg_daily_volatility = hist['Daily_Range_Pct'].rolling(14).mean().iloc[-1]
        weekly_potential = avg_daily_volatility * 100 * 2.2 

        # 2. Indicators
        hist['EMA20'] = hist['Close'].ewm(span=20, adjust=False).mean()
        
        # RSI
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        hist['RSI'] = 100 - (100 / (1 + rs))

        latest = hist.iloc[-1]
        prev = hist.iloc[-2]

        # 3. SIGNAL LOGIC
        signal = "WAIT"
        reason = ""
        
        # Entry A: Price crosses OVER EMA20
        if prev['Close'] < prev['EMA20'] and latest['Close'] > latest['EMA20']:
            signal = "BUY"
            reason = "Price crossed above 20 EMA"
            
        # Entry B: Oversold Bounce
        elif latest['RSI'] < 30:
            signal = "BUY"
            reason = "RSI Oversold (Dip Buy)"

        return {
            "ticker": ticker,
            "price": latest['Close'],
            "weekly_potential": weekly_potential,
            "signal": signal,
            "reason": reason,
            "stop_loss": latest['Close'] * 0.97, 
            "target": latest['Close'] * 1.05    
        }
    except Exception:
        return None

# --- UI LAYOUT ---

st.title("🚀 5% Weekly Swing Scanner")
st.markdown(f"""
**Universe:** Scanning **{len(STOCK_LIST)}** liquid stocks (Large Cap, Growth, Nordic & US Giants).
**Strategy:** Target a **4-5% return** within **1 week**.
""")

if st.button("Run High-Speed Scanner"):
    status_text = st.empty()
    status_text.info("⏳ Downloading market data for all stocks... (This is fast!)")
    
    # 1. Prepare Tickers
    tickers_map = {s.split('|')[0].strip(): s.split('|')[1].strip() for s in STOCK_LIST}
    ticker_list = list(tickers_map.keys())
    
    # 2. Batch Download (The Speed Boost)
    # We download 3 months of data for ALL tickers in one go
    try:
        batch_data = yf.download(ticker_list, period="3mo", group_by='ticker', threads=True)
        status_text.success("✅ Data downloaded. Analyzing charts...")
    except Exception as e:
        st.error(f"Download failed: {e}")
        st.stop()

    results = []
    progress = st.progress(0)
    
    # 3. Iterate and Analyze
    for i, ticker in enumerate(ticker_list):
        try:
            # Extract single stock dataframe from the batch
            # Note: yf.download structure varies slightly by version, handling both:
            if isinstance(batch_data.columns, pd.MultiIndex):
                try:
                    stock_hist = batch_data[ticker].copy()
                except KeyError:
                    continue # Ticker not found in download
            else:
                # Fallback for single ticker result
                stock_hist = batch_data 
            
            # Analyze
            res = analyze_market_data(ticker, stock_hist)
            
            if res:
                # Apply Filters
                if res['weekly_potential'] > 3.5 and res['signal'] == "BUY":
                    # Add readable name
                    res['name'] = tickers_map.get(ticker, ticker)
                    results.append(res)
        except Exception:
            continue # Skip if data is bad
            
        progress.progress((i + 1) / len(ticker_list))
    
    status_text.empty()
    
    # 4. Display Results
    if not results:
        st.warning("No stocks match the Buy criteria right now.")
    else:
        st.success(f"Found {len(results)} Opportunities!")
        
        for res in results:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.subheader(res['ticker'])
                c1.caption(res['name'])
                c1.write(f"**Signal:** {res['reason']}")
                
                c2.metric("Price", f"{res['price']:.2f}")
                
                vol_color = "green" if res['weekly_potential'] > 5.0 else "orange"
                c3.markdown(f"**Volatility:** <span style='color:{vol_color}'>{res['weekly_potential']:.1f}% / week</span>", unsafe_allow_html=True)
                
                c4.metric("🎯 Target", f"{res['target']:.2f}")
                c4.caption(f"🛑 Stop: {res['stop_loss']:.2f}")
                
                if st.button(f"Track {res['ticker']}", key=f"btn_{res['ticker']}"):
                    st.toast(f"Added {res['ticker']} to watchlist notes!", icon="📝")

st.info("💡 **Note:** This scanner now uses batch downloading, so it scans 100+ stocks in seconds instead of minutes.")
