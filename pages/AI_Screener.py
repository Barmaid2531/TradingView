# pages/AI_Screener.py
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import sys
import os

# Import utils including the new send_notification
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import read_portfolio, save_portfolio, send_notification

OMXS30_TICKERS = [
    "ABB.ST", "ALFA.ST", "ALIV-SDB.ST", "ASSA-B.ST", "AZN.ST", "ATCO-A.ST", 
    "BOL.ST", "ERIC-B.ST", "ESSITY-B.ST", "EVO.ST", "GETI-B.ST", "HEXA-B.ST",
    "HM-B.ST", "INVE-B.ST", "KINV-B.ST", "NDA-SE.ST", "SAND.ST", "SCA-B.ST",
    "SEB-A.ST", "SHB-A.ST", "SINCH.ST", "SKF-B.ST", "SWED-A.ST", "SWMA.ST",
    "TELIA.ST", "TRUE-B.ST", "VOLV-B.ST", "EQT.ST", "NIBE-B.ST", "SBB-B.ST"
]

def add_to_portfolio(ticker, entry_price, quantity, notes):
    df = read_portfolio()
    if not df.empty and not df[(df['Ticker'] == ticker) & (df['Status'] == 'Open')].empty:
        st.toast(f"{ticker} is already in your portfolio.", icon="⚠️")
        return

    new_trade = pd.DataFrame([{
        'Ticker': ticker, 'EntryDate': datetime.now().strftime('%Y-%m-%d'), 
        'EntryPrice': entry_price, 'Quantity': quantity, 'Status': 'Open', 
        'Notes': notes
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
        
        hist['High-Low'] = hist['High'] - hist['Low']
        hist['High-PrevClose'] = abs(hist['High'] - hist['Close'].shift(1))
        hist['Low-PrevClose'] = abs(hist['Low'] - hist['Close'].shift(1))
        hist['TR'] = hist[['High-Low', 'High-PrevClose', 'Low-PrevClose']].max(axis=1)
        hist['ATR'] = hist['TR'].rolling(window=14).mean()

        latest = hist.iloc[-1]
        
        score = 0
        reasons = []
        if latest['Close'] > latest['SMA200']: score += 1; reasons.append("Bullish Trend")
        if 40 < latest['RSI'] < 70: score += 1; reasons.append("Healthy RSI")
        if latest['MACD'] > latest['Signal_Line']: score += 1; reasons.append("Positive MACD")
        if latest['Close'] < (latest['BB_Upper'] * 0.98): score += 1; reasons.append("Below Upper BB")
        if latest['Volume'] > latest['AvgVolume20']: score += 1; reasons.append("High Volume")

        stop_loss = latest['Close'] - (1.5 * latest['ATR'])
        take_profit = latest['Close'] + (2.0 * latest['ATR'])

        if score >= 3:
            return {
                "ticker": ticker, "name": info.get('shortName', 'N/A'), "price": latest['Close'], 
                "chart_data": hist.tail(60), "score": score, "reasons": reasons,
                "stop_loss": stop_loss, "take_profit": take_profit
            }
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
        
        sorted_signals = sorted(signals, key=lambda x: x['score'], reverse=True)
        st.session_state['screener_results'] = sorted_signals
        
        # --- NEW: Send Notification ---
        if sorted_signals:
            top_pick = sorted_signals[0]
            msg = f"Found {len(sorted_signals)} potential buys.\nTop Pick: {top_pick['ticker']} (Score {top_pick['score']}/5)"
            send_notification("Screener Results", msg)
            st.toast("Notification sent to phone!", icon="📱")

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
                st.caption(f"**Why?** {', '.join(sig['reasons'])}")
            with c2: st.metric("Price", f"{sig['price']:.2f} SEK")
            
            t1, t2 = st.columns(2)
            t1.metric("🎯 Target", f"{sig['take_profit']:.2f} SEK", delta=f"+{(sig['take_profit']/sig['price']-1)*100:.1f}%")
            t2.metric("🛑 Stop Loss", f"{sig['stop_loss']:.2f} SEK", delta=f"-{(1-sig['stop_loss']/sig['price'])*100:.1f}%", delta_color="inverse")

            chart_col, buy_col = st.columns([3, 1])
            with chart_col: st.plotly_chart(create_mini_chart(sig['chart_data']), use_container_width=True, config={'displayModeBar': False})
            with buy_col:
                with st.form(key=f"buy_{i}"):
                    qty = st.number_input("Qty", min_value=1, value=10)
                    auto_notes = f"Target: {sig['take_profit']:.2f} | Stop: {sig['stop_loss']:.2f}"
                    if st.form_submit_button("Simulate Buy"): 
                        add_to_portfolio(sig['ticker'], sig['price'], qty, auto_notes)
