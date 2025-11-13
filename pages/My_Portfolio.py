# pages/My_Portfolio.py
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import sys
import os
from pathlib import Path

# Add parent directory to path to import utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import read_portfolio, save_portfolio, send_notification

# --- PAGE CONFIG ---
st.set_page_config(layout="wide", page_title="My Portfolio")

# --- CSS FIX ---
st.markdown("""
    <style>
    div[data-testid="stExpander"] summary > span:first-child { display: none !important; }
    div[data-testid="stExpander"] { border: 1px solid #333; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

st.title("💼 My Cloud Portfolio")

# --- HELPER FUNCTIONS ---

@st.cache_data(ttl=43200)
def get_position_details(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if hist.empty: return None
        hist['SMA50'] = hist['Close'].rolling(window=50).mean()
        hist['SMA200'] = hist['Close'].rolling(window=200).mean()
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        latest = hist.iloc[-1]
        
        signal = "HOLD"
        if latest['RSI'] > 75: signal = "SELL: RSI Overbought"
        elif latest['SMA50'] < latest['SMA200']: signal = "SELL: Death Cross"

        return {"price": latest['Close'], "rsi": latest['RSI'], "sma50": latest['SMA50'], "sma200": latest['SMA200'], "signal": signal, "chart_data": hist}
    except Exception: return None

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
    fig.add_hline(y=entry_price, line_width=2, line_dash="dash", line_color="green")
    fig.update_layout(template='plotly_dark', height=400, margin=dict(l=20, r=20, t=40, b=20))
    return fig

def add_manual_holding(ticker, quantity, gav, notes):
    df = read_portfolio()
    new_trade = pd.DataFrame([{'Ticker': ticker.upper(), 'EntryDate': 'Existing', 'EntryPrice': gav, 'Quantity': quantity, 'Status': 'Open', 'Notes': notes}])
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
    st.toast("Updated!", icon="📝")

def update_status(index, status):
    df = read_portfolio()
    df.loc[index, 'Status'] = status
    save_portfolio(df)

def remove_holding(index):
    df = read_portfolio()
    df = df.drop(index).reset_index(drop=True)
    save_portfolio(df)
    st.toast("Removed.", icon="🗑️")

# --- MAIN CONTENT ---

with st.expander("Manually Add Holding"):
    with st.form(key="manual"):
        t = st.text_input("Ticker (e.g. VOLV-B.ST)")
        q = st.number_input("Shares", min_value=1)
        p = st.number_input("Avg Price")
        n = st.text_area("Notes")
        if st.form_submit_button("Add"):
            if t and q > 0: add_manual_holding(t, q, p, n); st.rerun()

portfolio_df = read_portfolio()

if portfolio_df.empty:
    st.info("Portfolio is empty.")
else:
    open_pos = portfolio_df[portfolio_df['Status'] == 'Open'].copy()
    total_val = 0
    if not open_pos.empty:
        st.markdown("### Open Positions")
        for i, row in open_pos.iterrows():
            st.markdown("---")
            
            # Fetch data
            det = get_position_details_with_retry(row['Ticker'])
            
            # Show header regardless of data success
            st.subheader(f"{row['Ticker']} ({row['Quantity']} shares)")

            if det:
                # --- HAPPY PATH: Data Found ---
                val = det['price'] * row['Quantity']
                total_val += val
                pnl = ((det['price'] / row['EntryPrice']) - 1) * 100 if row['EntryPrice'] > 0 else 0
                
                if "SELL" in det['signal']:
                    st.error(det['signal'])
                    send_notification(f"SELL: {row['Ticker']}", f"{det['signal']}")
                else: 
                    st.success(det['signal'])
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Value", f"{val:,.2f}")
                c2.metric("Entry", f"{row['EntryPrice']:,.2f}")
                c3.metric("Price", f"{det['price']:.2f}")
                c4.markdown(f"**P/L:** <span style='color:{'green' if pnl>=0 else 'red'}'>{pnl:.2f}%</span>", unsafe_allow_html=True)
                
                chart_data = det['chart_data']
            else:
                # --- ERROR PATH: Data Not Found ---
                st.warning("⚠️ Could not fetch live data. You can still edit or remove this holding below.")
                chart_data = None

            # --- MANAGEMENT SECTION (Always Visible) ---
            with st.expander("Manage Position"):
                if chart_data is not None:
                    st.plotly_chart(create_portfolio_chart(chart_data, row['EntryPrice']), use_container_width=True)
                
                st.markdown("#### Edit Details")
                with st.form(key=f"edit_{i}"):
                    nq = st.number_input("Qty", value=float(row['Quantity']))
                    np = st.number_input("Price", value=float(row['EntryPrice']))
                    nn = st.text_area("Notes", value=str(row['Notes']))
                    if st.form_submit_button("Save Changes"): 
                        update_holding(i, nq, np, nn)
                        st.rerun()
                
                st.markdown("#### Actions")
                b1, b2 = st.columns(2)
                if b1.button("Close Position", key=f"cl_{i}"): 
                    update_status(i, f"Closed {datetime.now().date()}")
                    st.rerun()
                if b2.button("Remove Permanently", key=f"rm_{i}", type="primary"): 
                    remove_holding(i)
                    st.rerun()
        
        st.markdown("---")
        st.header(f"Total Value: {total_val:,.2f} SEK")

    st.markdown("### Position History")
    closed = portfolio_df[portfolio_df['Status'] != 'Open']
    if not closed.empty: st.dataframe(closed)
