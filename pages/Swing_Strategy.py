import streamlit as st
import yfinance as yf
import pandas as pd
import sys
import os
from datetime import timedelta

# --- SETUP ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import STOCK_LIST

st.set_page_config(layout="wide", page_title="5% Swing Strategy")

# --- STRATEGY FUNCTIONS ---

@st.cache_data(ttl=3600)
def get_swing_signals(ticker):
    """
    Analyzes if a stock is good for a 4-5% weekly swing.
    Returns: Signal (BUY/WAIT), Volatility, and Recent Data
    """
    try:
        # Get 3 months of data to calculate trends
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")
        
        if len(hist) < 20: return None

        # 1. Calculate Volatility (Can it move 5% in a week?)
        # We measure the average "High - Low" range relative to price
        hist['Daily_Range_Pct'] = (hist['High'] - hist['Low']) / hist['Close']
        avg_daily_volatility = hist['Daily_Range_Pct'].rolling(14).mean().iloc[-1]
        # Weekly approx volatility = Daily * sqrt(5) approx 2.2x
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
        
        # Entry A: Price crosses OVER EMA20 (Momentum Start)
        if prev['Close'] < prev['EMA20'] and latest['Close'] > latest['EMA20']:
            signal = "BUY"
            reason = "Price crossed above 20 EMA"
            
        # Entry B: Oversold Bounce (RSI < 30)
        elif latest['RSI'] < 30:
            signal = "BUY"
            reason = "RSI Oversold (Dip Buy)"

        return {
            "ticker": ticker,
            "price": latest['Close'],
            "weekly_potential": weekly_potential, # The critical "Can it hit 5%?" metric
            "signal": signal,
            "reason": reason,
            "stop_loss": latest['Close'] * 0.97, # 3% Stop
            "target": latest['Close'] * 1.05    # 5% Target
        }

    except Exception:
        return None

# --- UI LAYOUT ---

st.title("🚀 5% Weekly Swing Scanner")
st.markdown("""
**Strategy:** Target a **4-5% return** within **1 week (5 days)**. 
* **Filter:** Only shows stocks with enough volatility to actually hit the target.
* **Exit Rule:** Sell at +5% profit OR sell after 5 days (Time Stop).
""")

if st.button("Run Scanner on Watchlist"):
    results = []
    progress = st.progress(0)
    
    status_text = st.empty()
    
    for i, stock_str in enumerate(STOCK_LIST):
        ticker = stock_str.split("|")[0].strip()
        status_text.text(f"Scanning {ticker}...")
        
        data = get_swing_signals(ticker)
        
        if data:
            # FILTER: Ignore stocks that are too stable (can't move 5%)
            if data['weekly_potential'] > 3.5: # Minimum 3.5% weekly range to be worth it
                if data['signal'] == "BUY":
                    results.append(data)
        
        progress.progress((i + 1) / len(STOCK_LIST))
    
    status_text.empty()
    
    if not results:
        st.warning("No stocks match the strategy right now.")
    else:
        st.success(f"Found {len(results)} Potential Swings!")
        
        for res in results:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.subheader(res['ticker'])
                c1.caption(res['reason'])
                
                c2.metric("Entry Price", f"{res['price']:.2f}")
                
                # Color code the volatility potential
                vol_color = "green" if res['weekly_potential'] > 5.0 else "orange"
                c3.markdown(f"**Volatility:** <span style='color:{vol_color}'>{res['weekly_potential']:.1f}% / week</span>", unsafe_allow_html=True)
                
                c4.metric("🎯 Target (+5%)", f"{res['target']:.2f}")
                c4.caption(f"🛑 Stop: {res['stop_loss']:.2f}")
                
                # Quick add button (Optional integration with your portfolio)
                if st.button(f"Track {res['ticker']}", key=res['ticker']):
                    st.toast(f"Remember to sell {res['ticker']} in 5 days if target not hit!", icon="⏰")

st.info("💡 **Tip:** If Volatility is low (< 3.5%), the stock moves too slowly to hit 5% in a week. Avoid those for this specific strategy.")
