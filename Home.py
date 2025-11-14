# Home.py
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from utils import STOCK_LIST # Import the list

@st.cache_data(ttl=3600)
def get_market_trend():
    try:
        hist = yf.Ticker("^OMXSPI").history(period="3mo")
        if hist.empty: return "Unknown", 0
        hist['SMA50'] = hist['Close'].rolling(window=50).mean()
        latest_price = hist['Close'].iloc[-1]
        sma50 = hist['SMA50'].iloc[-1]
        trend = "Bullish" if latest_price > sma50 else "Bearish"
        return trend, latest_price
    except Exception: return "Error", 0

def create_main_chart(ticker, data: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data['Close'], mode='lines', name='Price', line=dict(color='#007BFF')))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA50'], mode='lines', name='50-Day SMA', line=dict(color='orange', dash='dash')))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA200'], mode='lines', name='200-Day SMA', line=dict(color='purple', dash='dash')))
    fig.update_layout(title=f'{ticker} Price Chart', yaxis_title='Price', template='plotly_dark', height=500)
    return fig

def display_stock_details(ticker):
    try:
        with st.spinner(f"Loading data for {ticker}..."):
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            if hist.empty:
                st.error(f"No data found for '{ticker}'.")
                return

            company_name = stock.info.get('shortName', ticker)
            st.subheader(f"{company_name} ({ticker})")
            
            hist['SMA50'] = hist['Close'].rolling(window=50).mean()
            hist['SMA200'] = hist['Close'].rolling(window=200).mean()
            
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            hist['RSI'] = 100 - (100 / (1 + rs))
            latest = hist.iloc[-1]

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Price", f"{latest['Close']:.2f}")
            col2.metric("RSI", f"{latest['RSI']:.2f}")
            col3.metric("50-Day SMA", f"{latest['SMA50']:.2f}")
            col4.metric("200-Day SMA", f"{latest['SMA200']:.2f}")

            st.plotly_chart(create_main_chart(ticker, hist), use_container_width=True)
    except Exception as e:
        st.error(f"An error occurred: {e}")

st.set_page_config(layout="wide", page_title="Trading Dashboard")
st.sidebar.success("Select a page from the navigation above.")
st.title("📈 Trading Dashboard")

market_trend, market_price = get_market_trend()
trend_color = "green" if market_trend == "Bullish" else "red"
st.subheader("Overall Market Trend (OMXSPI)")
st.markdown(f"Trend: **<span style='color:{trend_color};'>{market_trend}</span>** | Level: {market_price:,.2f}", unsafe_allow_html=True)
st.markdown("---")

st.subheader("Search for a Stock")

# --- NEW: AUTO-COMPLETE SEARCH ---
selected_stock_string = st.selectbox(
    "Type to search...", 
    options=STOCK_LIST, 
    index=None, # Starts empty
    placeholder="e.g. Volvo, Ericsson, AZN..."
)

if selected_stock_string:
    # Extract the ticker from the string "VOLV-B.ST | Volvo AB"
    ticker_to_search = selected_stock_string.split("|")[0].strip()
    display_stock_details(ticker_to_search)
