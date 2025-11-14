# pages/Swing_Strategy.py
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sys
import os

# --- SETUP ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import STOCK_LIST

st.set_page_config(layout="wide", page_title="High Prob Swing Scanner")

# --- ADVANCED INDICATORS ---

def calculate_adx(df, period=14):
    """Calculates Average Directional Index (Trend Strength)"""
    try:
        plus_dm = df['High'].diff()
        minus_dm = df['Low'].diff()
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), -minus_dm, 0.0)
        
        tr1 = df['High'] - df['Low']
        tr2 = abs(df['High'] - df['Close'].shift(1))
        tr3 = abs(df['Low'] - df['Close'].shift(1))
        tr = pd.concat((tr1, tr2, tr3), axis=1).max(axis=1)
        
        atr = tr.rolling(period).mean()
        plus_di = 100 * (pd.Series(plus_dm).rolling(period).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()
        return adx
    except:
        return pd.Series(0, index=df.index)

def analyze_market_data(ticker, hist):
    """
    Analyzes a stock and generates a Probability Score (0-5).
    """
    try:
        if len(hist) < 50: return None
        hist = hist.dropna(subset=['Close', 'Open', 'Volume'])
        
        # --- 1. INDICATORS ---
        # EMAs
        hist['EMA20'] = hist['Close'].ewm(span=20, adjust=False).mean()
        hist['EMA50'] = hist['Close'].ewm(span=50, adjust=False).mean()
        
        # RSI
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        hist['RSI'] = 100 - (100 / (1 + rs))
        
        # ADX (Trend Strength)
        hist['ADX'] = calculate_adx(hist)
        
        # Relative Volume (RVOL)
        # Compares today's volume to the average of the last 20 days
        hist['AvgVol'] = hist['Volume'].rolling(20).mean()
        hist['RVOL'] = hist['Volume'] / hist['AvgVol']
        
        # Volatility (Weekly Range Potential)
        hist['Daily_Range_Pct'] = (hist['High'] - hist['Low']) / hist['Close']
        avg_volatility = hist['Daily_Range_Pct'].rolling(14).mean().iloc[-1]
        weekly_potential = avg_volatility * 100 * 2.2 

        latest = hist.iloc[-1]
        prev = hist.iloc[-2]

        # --- 2. SCORING SYSTEM (The "Probability" Engine) ---
        score = 0
        reasons = []
        
        # Factor 1: Trend Alignment (+1)
        if latest['Close'] > latest['EMA50']:
            score += 1
            reasons.append("Bullish Trend (>EMA50)")
            
        # Factor 2: Momentum Trigger (+1)
        # Buy if crossing EMA20 OR Oversold Bounce
        entry_signal = False
        if (prev['Close'] < prev['EMA20'] and latest['Close'] > latest['EMA20']):
            score += 1
            entry_signal = True
            reasons.append("Momentum Crossover")
        elif latest['RSI'] < 30:
            score += 1
            entry_signal = True
            reasons.append("Oversold Bounce")
            
        # Factor 3: Volume Conviction (+1)
        if latest['RVOL'] > 1.5:
            score += 1
            reasons.append(f"High Volume ({latest['RVOL']:.1f}x)")
            
        # Factor 4: Trend Strength (+1)
        if latest['ADX'] > 25:
            score += 1
            reasons.append(f"Strong Trend (ADX {latest['ADX']:.0f})")
            
        # Factor 5: Volatility (+1)
        if weekly_potential > 4.0:
            score += 1
        
        # --- RETURN RESULT IF ENTRY SIGNAL EXISTS ---
        # Only return if we actually have a reason to enter (Signal + Volatility)
        if entry_signal and weekly_potential > 3.0:
            return {
                "ticker": ticker,
                "price": latest['Close'],
                "score": score,
                "reasons": reasons,
                "weekly_potential": weekly_potential,
                "target": latest['Close'] * 1.05,
                "stop": latest['Close'] * 0.97,
                "rvol": latest['RVOL']
            }
        
        return None

    except Exception:
        return None

# --- UI LAYOUT ---

st.title("🎯 High-Probability Swing Scanner")
st.markdown("""
**Ranking System:** Sorts stocks by a **Probability Score (0-5)** based on Trend, Volume, and Momentum.
* **Score 5/5:** Perfect Setup (Trend + Volume + Momentum).
* **Score 3-4:** Good Setup.
* **Score < 3:** Risky / Weak.
""")

if st.button("Run Probability Scanner", type="primary"):
    status_text = st.empty()
    status_text.info("⏳ Fetching data for all stocks... (Batch Mode)")
    
    # 1. Prepare Tickers
    tickers_map = {s.split('|')[0].strip(): s.split('|')[1].strip() for s in STOCK_LIST}
    ticker_list = list(tickers_map.keys())
    
    # 2. Batch Download
    try:
        # Download 6 months to calculate EMA50 and ADX accurately
        batch_data = yf.download(ticker_list, period="6mo", group_by='ticker', threads=True)
        status_text.success("✅ Data downloaded. Calculating probabilities...")
    except Exception as e:
        st.error(f"Download failed: {e}")
        st.stop()

    results = []
    progress = st.progress(0)
    
    # 3. Iterate and Analyze
    for i, ticker in enumerate(ticker_list):
        try:
            if isinstance(batch_data.columns, pd.MultiIndex):
                try:
                    stock_hist = batch_data[ticker].copy()
                except KeyError:
                    continue 
            else:
                stock_hist = batch_data 
            
            res = analyze_market_data(ticker, stock_hist)
            if res:
                res['name'] = tickers_map.get(ticker, ticker)
                results.append(res)
        except Exception:
            continue
            
        progress.progress((i + 1) / len(ticker_list))
    
    status_text.empty()
    
    # 4. Sort & Display
    if not results:
        st.warning("No high-probability setups found today.")
    else:
        # SORT BY SCORE (Highest First), then by Volatility
        results.sort(key=lambda x: (x['score'], x['weekly_potential']), reverse=True)
        
        st.success(f"Found {len(results)} Opportunities (Sorted by Probability)")
        
        for res in results:
            # Color code the card based on score
            border_color = "green" if res['score'] >= 4 else "orange"
            
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                
                with c1:
                    st.subheader(f"{res['ticker']}  ⭐ {res['score']}/5")
                    st.caption(res['name'])
                    st.write(f"**Why?** {', '.join(res['reasons'])}")
                
                with c2:
                    st.metric("Price", f"{res['price']:.2f}")
                    if res['rvol'] > 1.2:
                        st.caption(f"🔥 Vol: {res['rvol']:.1f}x Avg")

                with c3:
                    st.metric("Target (5%)", f"{res['target']:.2f}")
                    st.caption(f"Stop: {res['stop']:.2f}")
                
                with c4:
                    vol_color = "green" if res['weekly_potential'] > 5 else "orange"
                    st.markdown(f"**Vol:** <span style='color:{vol_color}'>{res['weekly_potential']:.1f}%</span>", unsafe_allow_html=True)
                    if st.button(f"Track {res['ticker']}", key=res['ticker']):
                        st.toast(f"Tracking {res['ticker']}", icon="📈")
