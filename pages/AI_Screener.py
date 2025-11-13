# pages/AI_Screener.py
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import sys
import os

# Fix import path for cloud
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import read_portfolio, save_portfolio

OMXS30_TICKERS = [
    "ABB.ST", "ALFA.ST", "ALIV-SDB.ST", "ASSA-B.ST", "AZN.ST", "ATCO-A.ST", 
    "BOL.ST", "ERIC-B.ST", "ESSITY-B.ST", "EVO.ST", "GETI-B.ST", "HEXA-B.ST",
    "HM-B.ST", "INVE-B.ST", "KINV-B.ST", "NDA-SE.ST", "SAND.ST", "SCA-B.ST",
    "SEB-A.ST", "SHB-A.ST", "SINCH.ST", "SKF-B.ST", "SWED-A.ST", "SWMA.ST",
    "TELIA.ST", "TRUE-B.ST", "VOLV-B.ST", "EQT.ST", "NIBE-B.ST", "SBB-B.ST"
]

def add_to_portfolio(ticker, entry_price, quantity):
    df = read_portfolio()
    
    if not df.empty and not df[(df['Ticker'] == ticker) & (df['Status'] == 'Open')].empty:
        st.toast(f"{ticker} is already in your portfolio.", icon="⚠️")
        return

    new_trade = pd.DataFrame([{
        'Ticker': ticker, 'EntryDate': datetime.now().strftime('%Y-%m-%d'), 
        'EntryPrice': entry_price, 'Quantity': quantity, 'Status': 'Open', 
        'Notes': 'Added from Screener'
    }])
    
    if df.empty: df = new_trade
    else: df = pd.concat([df, new_trade], ignore_index=True)
        
    save_portfolio(df)
    st.toast(f"Added {quantity} shares of {ticker}!", icon="✅")

def create_mini_chart(data: pd.DataFrame):
    fig = go.Figure()
    line_color = '#28a745' if data['Close'].iloc[-1] >= data['Close'].iloc[0] else '#dc3545'
    fig.add_trace(go.Scatter(x=data.index, y=data['Close'], mode='lines', line=dict(color=line_color, width=2)))
    fig.update_layout(height=80, margin=dict(l=0, r=0, t=0, b=0), showlegend=False, xaxis_visible=False, yaxis_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

@st.cache_data(ttl=3600)
def analyze_stock_for_signal(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if len(hist) < 200: return None
        info = stock.info
        
        hist['SMA50'] = hist['Close'].rolling(window=50).mean()
        hist['SMA200'] = hist['Close'].rolling(window=200).mean()
        
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        hist['RSI'] = 100 - (100 / (1 + rs))
        
        exp12 = hist['Close'].ewm(span=12, adjust=False).mean()
        exp26 = hist['Close'].ewm(span=26, adjust=False).mean()
        hist['MACD'] = exp12 - exp26
        hist['Signal_Line'] = hist['MACD'].ewm(span=9, adjust=False).mean()
        
        hist['BB_Middle'] = hist['Close'].rolling(window=20).mean()
        hist['BB_Std'] = hist['Close'].rolling(window=20).std()
        hist['BB_Upper'] = hist['BB_Middle'] + (2 * hist['BB_Std'])
        hist['AvgVolume20'] = hist['Volume'].rolling(window=20).mean()
        latest = hist.iloc[-1]
        
        score = 0
        reasons = []
        if latest['Close'] > latest['SMA200']: score += 1; reasons.append("Bullish Trend")
        if 40 < latest['RSI'] < 70: score += 1; reasons.append("Healthy RSI")
        if latest['MACD'] > latest['Signal_Line']: score += 1; reasons.append("Positive MACD")
        if latest['Close'] < (latest['BB_Upper'] * 0.98): score += 1; reasons.append("Below Upper BB")
        if latest['Volume'] > latest['AvgVolume20']: score += 1; reasons.append("High Volume")

        if score >= 3:
            return {"ticker": ticker, "name": info.get('shortName', 'N/A'), "price": latest['Close'], "chart_data": hist.tail(60), "score": score, "reasons": reasons}
        return None
    except Exception: return None

st.set_page_config(layout="wide", page_title="Market Screener")
st.title("🤖 Advanced AI Market Screener")

scan_mode = st.radio("Choose what to scan:", ["Custom Watchlist", "Full OMXS30 Index"], horizontal=True)
tickers_to_scan = []
if scan_mode == "Custom Watchlist":
    default_tickers = "VOLV-B.ST, ERIC-B.ST, AZN.ST, SBB-B.ST"
    user_input = st.text_area("Enter tickers:", value=default_tickers)
    if user_input: tickers_to_scan = [t.strip().upper() for t in user_input.split(',') if t.strip()]
else: tickers_to_scan = OMXS30_TICKERS

if st.button("🚀 Run Scan", type="primary"):
    if not tickers_to_scan: st.error("Enter at least one ticker.")
    else:
        with st.spinner(f"Analyzing {len(tickers_to_scan)} stocks..."):
            signals = []
            progress = st.progress(0)
            for i, ticker in enumerate(tickers_to_scan):
                res = analyze_stock_for_signal(ticker)
                if res: signals.append(res)
                progress.progress((i + 1) / len(tickers_to_scan))
        st.session_state['screener_results'] = sorted(signals, key=lambda x: x['score'], reverse=True)

if 'screener_results' in st.session_state:
    if not st.session_state['screener_results']: st.warning("No stocks met criteria.")
    else:
        st.success(f"Found {len(st.session_state['screener_results'])} candidates.")
        for i, sig in enumerate(st.session_state['screener_results']):
            score = sig['score']
            color = "green" if score >= 4 else "orange" if score == 3 else "gray"
            st.markdown("---")
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(f"{sig['name']} ({sig['ticker']})")
                st.markdown(f"Signal: **<span style='color:{color};'>Score {score}/5</span>**", unsafe_allow_html=True)
                st.caption(f"Why? {', '.join(sig['reasons'])}")
            with c2: st.metric("Price", f"{sig['price']:.2f} SEK")
            
            chart_col, buy_col = st.columns([3, 1])
            with chart_col: st.plotly_chart(create_mini_chart(sig['chart_data']), use_container_width=True, config={'displayModeBar': False})
            with buy_col:
                with st.form(key=f"buy_{i}"):
                    qty = st.number_input("Qty", min_value=1, value=10)
                    if st.form_submit_button("Simulate Buy"): add_to_portfolio(sig['ticker'], sig['price'], qty)
