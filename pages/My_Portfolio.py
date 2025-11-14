import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import sys
import os
from pathlib import Path

# --- IMPORT UTILS FROM PARENT DIRECTORY ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import read_portfolio, save_portfolio, send_notification, STOCK_LIST

# --- PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="My Portfolio")

# --- CSS FIX ---
st.markdown("""
    <style>
    div[data-testid="stExpander"] summary > span:first-child { display: none !important; }
    div[data-testid="stExpander"] { border: 1px solid #333; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

st.title("💼 My Cloud Portfolio")

# --- DATA FETCHING & ANALYSIS FUNCTIONS ---

@st.cache_data(ttl=300) 
def get_position_details(ticker):
    """Fetches price, indicators, and chart data for a stock."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        
        if hist.empty: 
            st.error(f"⚠️ Data empty for {ticker}. Check ticker symbol.")
            return None

        # Calculate Moving Averages
        hist['SMA50'] = hist['Close'].rolling(window=50).mean()
        hist['SMA200'] = hist['Close'].rolling(window=200).mean()
        
        # Calculate RSI
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        hist['RSI'] = 100 - (100 / (1 + rs)) # Fix: Save RSI to dataframe
        
        latest = hist.iloc[-1]
        
        # --- NEW STRATEGY LOGIC ---
        signal = "HOLD"
        current_rsi = latest['RSI'] if 'RSI' in latest and pd.notna(latest['RSI']) else 50
        sma50 = latest['SMA50']
        sma200 = latest['SMA200']

        # Check conditions if SMAs are valid
        if pd.notna(sma50) and pd.notna(sma200):
            # SELL SIGNALS
            if current_rsi > 70:
                signal = "SELL: RSI Overbought (>70)"
            elif sma50 < sma200:
                signal = "SELL: Death Cross (50 < 200 SMA)"
            
            # BUY SIGNALS (Prioritize Buy if recent crossover)
            elif current_rsi < 30:
                signal = "BUY: RSI Oversold (<30)"
            elif sma50 > sma200:
                signal = "BUY: Golden Cross (Bullish Trend)"

        return {
            "price": latest['Close'],
            "rsi": current_rsi,
            "sma50": sma50,
            "sma200": sma200,
            "signal": signal,
            "chart_data": hist
        }
    except Exception as e:
        st.error(f"Error fetching {ticker}: {e}")
        return None

def get_position_details_with_retry(ticker, retries=3):
    for i in range(retries):
        res = get_position_details(ticker)
        if res: return res
        time.sleep(1) 
    return None

def create_portfolio_chart(data, entry_price):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data['Close'], mode='lines', name='Price', line=dict(color='#007BFF')))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA50'], mode='lines', name='50 SMA', line=dict(color='orange', dash='dot')))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA200'], mode='lines', name='200 SMA', line=dict(color='purple', dash='dot')))
    fig.add_hline(y=entry_price, line_width=2, line_dash="dash", line_color="green", annotation_text="Entry", annotation_position="bottom right")
    fig.update_layout(template='plotly_dark', height=400, margin=dict(l=20, r=20, t=40, b=20))
    return fig

# --- PORTFOLIO MANAGEMENT FUNCTIONS ---

def add_manual_holding(ticker, quantity, gav, notes):
    df = read_portfolio()
    new_trade = pd.DataFrame([{
        'Ticker': ticker.upper(), 
        'EntryDate': 'Existing', 
        'EntryPrice': gav, 
        'Quantity': quantity, 
        'Status': 'Open', 
        'Notes': notes
    }])
    
    if df.empty: df = new_trade
    else: df = pd.concat([df, new_trade], ignore_index=True)
        
    save_portfolio(df)
    st.toast(f"Added {ticker}", icon="➕")

def update_holding(index, qty, gav, notes):
    df = read_portfolio()
    df.loc[index, 'Quantity'] = qty
    df.loc[index, 'EntryPrice'] = gav
    df.loc[index, 'Notes'] = notes
    save_portfolio(df)
    st.toast("Holding updated!", icon="📝")

def update_status(index, status):
    df = read_portfolio()
    df.loc[index, 'Status'] = status
    save_portfolio(df)

def remove_holding(index):
    df = read_portfolio()
    df = df.drop(index).reset_index(drop=True)
    save_portfolio(df)
    st.toast("Removed.", icon="🗑️")

# --- MAIN PAGE CONTENT ---

# 1. Manual Add Section
with st.expander("Manually Add Holding"):
    with st.form(key="manual"):
        stock_selection = st.selectbox("Select Stock", options=STOCK_LIST, index=None, placeholder="Search ticker (e.g. Volvo)...")
        c1, c2 = st.columns(2)
        q = c1.number_input("Shares", min_value=1, step=1)
        p = c2.number_input("Avg Price (GAV)")
        n = st.text_area("Notes")
        
        if st.form_submit_button("Add to Portfolio"):
            if stock_selection and q > 0:
                t = stock_selection.split("|")[0].strip()
                add_manual_holding(t, q, p, n)
                st.rerun()
            elif not stock_selection:
                st.error("Please select a stock from the list.")

# 2. Load Portfolio Data
portfolio_df = read_portfolio()

if portfolio_df.empty:
    st.info("Your portfolio is empty. Add stocks using the form above or the AI Screener.")
else:
    open_pos = portfolio_df[portfolio_df['Status'] == 'Open'].copy()
    total_val = 0

    if not open_pos.empty:
        st.markdown("### Open Positions")
        
        for i, row in open_pos.iterrows():
            # Fetch Live Data
            det = get_position_details_with_retry(row['Ticker'])
            
            st.markdown("---")
            st.subheader(f"{row['Ticker']} ({row['Quantity']} shares)")

            if det:
                val = det['price'] * row['Quantity']
                total_val += val
                pnl = ((det['price'] / row['EntryPrice']) - 1) * 100 if row['EntryPrice'] > 0 else 0
                
                # --- NEW VISUAL LOGIC ---
                if "SELL" in det['signal']:
                    st.warning(f"📉 {det['signal']}") # Orange box for Warning
                elif "BUY" in det['signal']:
                    st.success(f"🚀 {det['signal']}") # Green box for Opportunity
                else:
                    st.info(f"✋ {det['signal']}") # Blue box for Neutral
                
                # Metrics Row
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Value", f"{val:,.2f} SEK")
                c2.metric("Entry", f"{row['EntryPrice']:,.2f} SEK")
                c3.metric("Price", f"{det['price']:.2f} SEK")
                c4.markdown(f"**P/L:** <span style='color:{'green' if pnl>=0 else 'red'}'>{pnl:.2f}%</span>", unsafe_allow_html=True)
                
                chart_data = det['chart_data']
            else:
                st.warning("⚠️ Could not fetch live data. You can still manage this position below.")
                chart_data = None

            # Management Section
            with st.expander("Details & Actions"):
                if chart_data is not None:
                    st.plotly_chart(create_portfolio_chart(chart_data, row['EntryPrice']), use_container_width=True)
                
                st.markdown("**Edit Details**")
                with st.form(key=f"edit_{i}"):
                    nq = st.number_input("Qty", value=float(row['Quantity']))
                    np = st.number_input("Price", value=float(row['EntryPrice']))
                    nn = st.text_area("Notes", value=str(row['Notes']) if pd.notna(row['Notes']) else "")
                    if st.form_submit_button("Save Changes"): 
                        update_holding(i, nq, np, nn)
                        st.rerun()
                
                st.markdown("**Actions**")
                b1, b2 = st.columns(2)
                if b1.button("Close Position", key=f"cl_{i}"): 
                    update_status(i, f"Closed {datetime.now().date()}")
                    st.rerun()
                if b2.button("Remove Permanently", key=f"rm_{i}", type="primary"): 
                    remove_holding(i)
                    st.rerun()
        
        st.markdown("---")
        st.header(f"Total Portfolio Value: {total_val:,.2f} SEK")

    # 3. History Section
    st.markdown("### Position History")
    closed = portfolio_df[portfolio_df['Status'] != 'Open']
    if not closed.empty: 
        st.dataframe(closed)
