# pages/AI_Screener.py
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path

# --- ROBUST FILE PATH ---
PORTFOLIO_FILE = Path(__file__).parent.parent / "portfolio.csv"

# Default Index List
OMXS30_TICKERS = [
    "ABB.ST", "ALFA.ST", "ALIV-SDB.ST", "ASSA-B.ST", "AZN.ST", "ATCO-A.ST", 
    "BOL.ST", "ERIC-B.ST", "ESSITY-B.ST", "EVO.ST", "GETI-B.ST", "HEXA-B.ST",
    "HM-B.ST", "INVE-B.ST", "KINV-B.ST", "NDA-SE.ST", "SAND.ST", "SCA-B.ST",
    "SEB-A.ST", "SHB-A.ST", "SINCH.ST", "SKF-B.ST", "SWED-A.ST", "SWMA.ST",
    "TELIA.ST", "TRUE-B.ST", "VOLV-B.ST", "EQT.ST", "NIBE-B.ST", "SBB-B.ST"
]

def add_to_portfolio(ticker, entry_price, quantity):
    try:
        df = pd.read_csv(PORTFOLIO_FILE)
    except FileNotFoundError:
        df = pd.DataFrame(columns=['Ticker', 'EntryDate', 'EntryPrice', 'Quantity', 'Status', 'Notes'])

    # Check if already open
    if not df[(df['Ticker'] == ticker) & (df['Status'] == 'Open')].empty:
        st.toast(f"{ticker} is already in your portfolio as an open position.", icon="⚠️")
        return

    new_trade = pd.DataFrame([{
        'Ticker': ticker, 
        'EntryDate': datetime.now().strftime('%Y-%m-%d'), 
        'EntryPrice': entry_price, 
        'Quantity': quantity, 
        'Status': 'Open', 
        'Notes': 'Added from Screener'
    }])
    df = pd.concat([df, new_trade], ignore_index=True)
    df.to_csv(PORTFOLIO_FILE, index=False)
    st.toast(f"Added {quantity} shares of {ticker} to portfolio!", icon="✅")

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
        
        # --- CALCULATE INDICATORS ---
        hist['SMA50'] = hist['Close'].rolling(window=50).mean()
        hist['SMA200'] = hist['Close'].rolling(window=200).mean()
        
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        hist['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp12 = hist['Close'].ewm(span=12, adjust=False).mean()
        exp26 = hist['Close'].ewm(span=26, adjust=False).mean()
        hist['MACD'] = exp12 - exp26
        hist['Signal_Line'] = hist['MACD'].ewm(span=9, adjust=False).mean()
        
        # Bollinger Bands
        hist['BB_Middle'] = hist['Close'].rolling(window=20).mean()
        hist['BB_Std'] = hist['Close'].rolling(window=20).std()
        hist['BB_Upper'] = hist['BB_Middle'] + (2 * hist['BB_Std'])
        
        hist['AvgVolume20'] = hist['Volume'].rolling(window=20).mean()

        latest = hist.iloc[-1]
        
        # --- SCORING (Max 5) ---
        score = 0
        reasons = []

        if latest['Close'] > latest['SMA200']:
            score += 1
            reasons.append("Bullish Trend (>SMA200)")
        
        if 40 < latest['RSI'] < 70:
            score += 1
            reasons.append("Healthy RSI")
            
        if latest['MACD'] > latest['Signal_Line']:
            score += 1
            reasons.append("Positive MACD")
            
        if latest['Close'] < (latest['BB_Upper'] * 0.98): 
            score += 1
            reasons.append("Below Upper BB")

        if latest['Volume'] > latest['AvgVolume20']:
            score += 1
            reasons.append("High Volume")

        # Return result if it has at least a moderate score (3/5)
        if score >= 3:
            return {
                "ticker": ticker, 
                "name": info.get('shortName', ticker), 
                "price": latest['Close'], 
                "chart_data": hist.tail(60), 
                "score": score,
                "reasons": reasons
            }
        return None
    except Exception:
        return None

# --- LAYOUT ---
st.set_page_config(layout="wide", page_title="Market Screener")
st.title("🤖 Advanced AI Market Screener")

# 1. Select Scan Target
st.markdown("### 1. Select Scan Target")
scan_mode = st.radio("Choose what to scan:", ["Custom Watchlist", "Full OMXS30 Index"], horizontal=True)

tickers_to_scan = []

if scan_mode == "Custom Watchlist":
    default_tickers = "VOLV-B.ST, ERIC-B.ST, AZN.ST, SBB-B.ST, HM-B.ST"
    user_input = st.text_area("Enter tickers separated by commas:", value=default_tickers)
    if user_input:
        tickers_to_scan = [t.strip().upper() for t in user_input.split(',') if t.strip()]
else:
    tickers_to_scan = OMXS30_TICKERS

# 2. Run Analysis
st.markdown("### 2. Run Analysis")
if st.button("🚀 Run Scan", type="primary"):
    if not tickers_to_scan:
        st.error("Please enter at least one ticker.")
    else:
        with st.spinner(f"Analyzing {len(tickers_to_scan)} stocks..."):
            signals = []
            progress_bar = st.progress(0, text="Starting scan...")
            
            for i, ticker in enumerate(tickers_to_scan):
                result = analyze_stock_for_signal(ticker)
                if result:
                    signals.append(result)
                progress_bar.progress((i + 1) / len(tickers_to_scan), text=f"Scanning {ticker}...")
        
        # Sort by score
        sorted_signals = sorted(signals, key=lambda x: x['score'], reverse=True)
        st.session_state['screener_results'] = sorted_signals

if 'screener_results' in st.session_state:
    if not st.session_state['screener_results']:
        st.warning("No stocks met the 'Strong Buy' criteria (Score >= 3).")
    else:
        st.success(f"Scan complete! Found {len(st.session_state['screener_results'])} potential candidates.")
        
        for i, signal in enumerate(st.session_state['screener_results']):
            score = signal['score']
            if score >= 4: signal_type, color = "Strong Buy", "green"
            elif score == 3: signal_type, color = "Moderate Buy", "orange"
            else: signal_type, color = "Weak Signal", "gray"
            
            st.markdown("---")
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(f"{signal['name']} ({signal['ticker']})")
                st.markdown(f"Signal: **<span style='color:{color};'>{signal_type}</span>** (Score: {score}/5)", unsafe_allow_html=True)
                st.caption(f"**Why?** {', '.join(signal['reasons'])}")
                
            with c2:
                st.metric("Current Price", f"{signal['price']:.2f} SEK")
                
            col_chart, col_buy = st.columns([3, 1])
            with col_chart:
                chart_fig = create_mini_chart(signal['chart_data'])
                st.plotly_chart(chart_fig, use_container_width=True, config={'displayModeBar': False})
            with col_buy:
                st.markdown("<br>", unsafe_allow_html=True) 
                with st.form(key=f"buy_form_{i}"):
                    quantity = st.number_input("Quantity", min_value=1, step=1, value=10)
                    submitted = st.form_submit_button("Simulate Buy")
                    if submitted:
                        add_to_portfolio(signal['ticker'], signal['price'], quantity)