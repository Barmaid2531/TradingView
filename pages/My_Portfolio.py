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
