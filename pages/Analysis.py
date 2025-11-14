# pages/Analysis.py
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os

# --- SETUP ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import STOCK_LIST

st.set_page_config(layout="wide", page_title="Stock Analysis")

# --- FUNCTIONS ---

@st.cache_data(ttl=300)
def get_stock_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        # Fetch 2 years to ensure enough data for 200 SMA
        hist = stock.history(period="2y")
        info = stock.info
        
        if hist.empty: return None

        # --- INDICATOR CALCULATIONS ---
        # 1. SMA
        hist['SMA50'] = hist['Close'].rolling(window=50).mean()
        hist['SMA200'] = hist['Close'].rolling(window=200).mean()
        
        # 2. RSI (14)
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        hist['RSI'] = 100 - (100 / (1 + rs))
        
        # 3. MACD (12, 26, 9)
        exp12 = hist['Close'].ewm(span=12, adjust=False).mean()
        exp26 = hist['Close'].ewm(span=26, adjust=False).mean()
        hist['MACD'] = exp12 - exp26
        hist['Signal_Line'] = hist['MACD'].ewm(span=9, adjust=False).mean()
        
        # 4. Bollinger Bands (20, 2)
        hist['BB_Middle'] = hist['Close'].rolling(window=20).mean()
        hist['BB_Std'] = hist['Close'].rolling(window=20).std()
        hist['BB_Upper'] = hist['BB_Middle'] + (2 * hist['BB_Std'])
        hist['BB_Lower'] = hist['BB_Middle'] - (2 * hist['BB_Std'])

        return {"history": hist, "info": info}
    except Exception as e:
        st.error(f"Error analyzing {ticker}: {e}")
        return None

def calculate_verdict(latest):
    """Generates a simple Buy/Sell score based on technicals."""
    score = 0
    reasons = []
    
    # Trend
    if latest['Close'] > latest['SMA200']: 
        score += 1
        reasons.append("Price > 200 SMA (Long term Bullish)")
    else:
        score -= 1
        reasons.append("Price < 200 SMA (Long term Bearish)")
    
    # Momentum (RSI)
    if 30 < latest['RSI'] < 70:
        score += 0.5 # Neutral/Healthy
    elif latest['RSI'] <= 30:
        score += 2
        reasons.append("RSI Oversold (Potential bounce)")
    elif latest['RSI'] >= 70:
        score -= 1
        reasons.append("RSI Overbought (Caution)")
        
    # MACD
    if latest['MACD'] > latest['Signal_Line']:
        score += 1
        reasons.append("MACD Bullish Crossover")
    else:
        reasons.append("MACD Bearish")
        
    # Bollinger
    if latest['Close'] < latest['BB_Lower']:
        score += 1
        reasons.append("Price below Lower BB (Oversold)")
        
    verdict = "NEUTRAL"
    color = "blue"
    if score >= 3: 
        verdict = "STRONG BUY"
        color = "green"
    elif score >= 1:
        verdict = "BUY / ACCUMULATE"
        color = "lightgreen"
    elif score <= -1:
        verdict = "SELL / AVOID"
        color = "red"
        
    return verdict, color, reasons

# --- MAIN PAGE UI ---

st.title("🔍 Deep Dive Analysis")
st.markdown("Analyze any stock. Select from your watchlist or type a custom ticker (e.g., **AAPL**, **BTC-USD**).")

# --- NEW SEARCH INTERFACE ---
with st.container(border=True):
    c1, c2 = st.columns(2)
    
    with c1:
        selected_list_stock = st.selectbox(
            "Option A: Select from Swedish List", 
            options=STOCK_LIST, 
            index=None, 
            placeholder="Select a Swedish stock..."
        )
        
    with c2:
        custom_ticker = st.text_input(
            "Option B: Type ANY Ticker", 
            placeholder="e.g. AAPL, TSLA, NVDA, BTC-USD"
        )

# Logic: Custom ticker takes priority if typed
ticker = None
if custom_ticker:
    ticker = custom_ticker.strip().upper()
elif selected_list_stock:
    ticker = selected_list_stock.split("|")[0].strip()

# --- ANALYSIS OUTPUT ---
if ticker:
    with st.spinner(f"Analyzing {ticker}..."):
        data = get_stock_analysis(ticker)
    
    if data:
        hist = data['history']
        info = data['info']
        latest = hist.iloc[-1]
        
        # --- HEADER SECTION (Price & Fundamentals) ---
        st.markdown("---")
        h1, h2, h3, h4 = st.columns(4)
        
        currency = info.get('currency', '???')
        h1.metric("Current Price", f"{latest['Close']:,.2f} {currency}")
        h2.metric("Sector", info.get('sector', 'N/A'))
        
        # P/E Ratio formatting
        pe = info.get('trailingPE', None)
        h3.metric("P/E Ratio", f"{pe:.2f}" if pe else "N/A")
        
        # Market Cap formatting
        mcap = info.get('marketCap', 0)
        if mcap > 1_000_000_000_000: val_str = f"{mcap/1_000_000_000_000:.1f}T"
        elif mcap > 1_000_000_000: val_str = f"{mcap/1_000_000_000:.1f}B"
        elif mcap > 1_000_000: val_str = f"{mcap/1_000_000:.1f}M"
        else: val_str = f"{mcap:,.0f}"
        h4.metric("Market Cap", f"{val_str} {currency}")

        # --- VERDICT SECTION ---
        verdict, v_color, reasons = calculate_verdict(latest)
        
        st.markdown(f"""
        <div style="padding: 20px; border-radius: 10px; background-color: rgba(255,255,255,0.05); border: 1px solid #333; margin-bottom: 20px;">
            <h3 style="margin:0; color: {v_color};">{verdict}</h3>
            <p style="margin-top: 10px;"><strong>Signals:</strong> {', '.join(reasons) if reasons else 'No strong signals detected.'}</p>
        </div>
        """, unsafe_allow_html=True)

        # --- CHARTS SECTION ---
        tab1, tab2 = st.tabs(["📈 Technical Chart", "📊 Raw Data"])
        
        with tab1:
            # Create Subplots (Main Price + RSI + MACD)
            fig = make_subplots(
                rows=3, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.05, 
                row_heights=[0.6, 0.2, 0.2],
                subplot_titles=(f"{ticker} Price & Bollinger Bands", "RSI (14)", "MACD")
            )

            # 1. Candlestick & BB
            fig.add_trace(go.Candlestick(
                x=hist.index, open=hist['Open'], high=hist['High'], 
                low=hist['Low'], close=hist['Close'], name="OHLC"
            ), row=1, col=1)
            
            fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Upper'], line=dict(color='gray', width=1, dash='dash'), name="Upper BB"), row=1, col=1)
            fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Lower'], line=dict(color='gray', width=1, dash='dash'), fill='tonexty', fillcolor='rgba(128,128,128,0.1)', name="Lower BB"), row=1, col=1)
            fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA200'], line=dict(color='purple', width=2), name="200 SMA"), row=1, col=1)

            # 2. RSI
            fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], line=dict(color='#FFD700', width=2), name="RSI"), row=2, col=1)
            fig.add_hline(y=70, line_width=1, line_dash="dash", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_width=1, line_dash="dash", line_color="green", row=2, col=1)

            # 3. MACD
            fig.add_trace(go.Scatter(x=hist.index, y=hist['MACD'], line=dict(color='cyan', width=2), name="MACD"), row=3, col=1)
            fig.add_trace(go.Scatter(x=hist.index, y=hist['Signal_Line'], line=dict(color='orange', width=1), name="Signal"), row=3, col=1)
            
            # Layout updates
            fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.dataframe(hist.sort_index(ascending=False).head(30))
