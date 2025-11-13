# pages/My_Portfolio.py
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
from pathlib import Path

# --- ROBUST FILE PATH ---
PORTFOLIO_FILE = Path(__file__).parent.parent / "portfolio.csv"

# --- HELPER FUNCTIONS ---

@st.cache_data(ttl=43200)  # Cache for 12 hours for resilience
def get_position_details(ticker):
    """Fetches details for a stock: price, indicators, and chart."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if hist.empty: return None

        # Indicators
        hist['SMA50'] = hist['Close'].rolling(window=50).mean()
        hist['SMA200'] = hist['Close'].rolling(window=200).mean()
        
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        latest = hist.iloc[-1]
        
        # Exit Signal Logic
        signal = "HOLD"
        if latest['RSI'] > 75:
            signal = "SELL SIGNAL: RSI is overbought (> 75)"
        elif latest['SMA50'] < latest['SMA200']:
            signal = "SELL SIGNAL: Death Cross"

        return {
            "price": latest['Close'],
            "rsi": latest['RSI'],
            "sma50": latest['SMA50'],
            "sma200": latest['SMA200'],
            "signal": signal,
            "chart_data": hist
        }
    except Exception:
        return None

def get_position_details_with_retry(ticker, retries=3, delay=2):
    """Retry mechanism for fetching data."""
    for i in range(retries):
        try:
            details = get_position_details(ticker)
            if details: return details
        except Exception:
            time.sleep(delay)
    return None

def create_portfolio_chart(data, entry_price):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data['Close'], mode='lines', name='Price', line=dict(color='#007BFF')))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA50'], mode='lines', name='50-Day SMA', line=dict(color='orange', dash='dot')))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA200'], mode='lines', name='200-Day SMA', line=dict(color='purple', dash='dot')))
    fig.add_hline(y=entry_price, line_width=2, line_dash="dash", line_color="green", annotation_text="Entry Price", annotation_position="bottom right")
    fig.update_layout(template='plotly_dark', height=400, margin=dict(l=20, r=20, t=40, b=20))
    return fig

def read_portfolio():
    if not PORTFOLIO_FILE.is_file():
        return pd.DataFrame(columns=['Ticker', 'EntryDate', 'EntryPrice', 'Quantity', 'Status', 'Notes'])
    return pd.read_csv(PORTFOLIO_FILE, encoding='utf-8', encoding_errors='replace')

def save_portfolio(df):
    df.to_csv(PORTFOLIO_FILE, index=False)

def add_manual_holding(ticker, quantity, gav, notes):
    df = read_portfolio()
    new_trade = pd.DataFrame([{'Ticker': ticker.upper(), 'EntryDate': 'Existing', 'EntryPrice': gav, 'Quantity': quantity, 'Status': 'Open', 'Notes': notes}])
    df = pd.concat([df, new_trade], ignore_index=True)
    save_portfolio(df)
    st.toast(f"Added: {ticker}", icon="➕")

def update_holding(index, new_quantity, new_gav, new_notes):
    df = read_portfolio()
    df.loc[index, 'Quantity'] = new_quantity
    df.loc[index, 'EntryPrice'] = new_gav
    df.loc[index, 'Notes'] = new_notes
    save_portfolio(df)
    st.toast("Holding updated!", icon="📝")

def update_holding_status(index, new_status):
    df = read_portfolio()
    df.loc[index, 'Status'] = new_status
    save_portfolio(df)

def remove_holding(index_to_remove):
    df = read_portfolio()
    df = df.drop(index_to_remove).reset_index(drop=True)
    save_portfolio(df)
    st.toast("Removed holding.", icon="🗑️")

# --- LAYOUT ---
st.set_page_config(layout="wide", page_title="My Portfolio")
st.title("💼 My Simulated Portfolio")

with st.expander("Manually Add Existing Holding"):
    with st.form(key="manual_add_form", clear_on_submit=True):
        manual_ticker = st.text_input("Ticker Symbol (e.g., VOLV-B.ST)")
        manual_quantity = st.number_input("Shares", min_value=1, step=1)
        manual_gav = st.number_input("Avg Buy Price (GAV)")
        manual_notes = st.text_area("Notes")
        if st.form_submit_button("Add to Portfolio"):
            if manual_ticker and manual_quantity > 0:
                add_manual_holding(manual_ticker, manual_quantity, manual_gav, manual_notes)
                st.rerun()

portfolio_df = read_portfolio()

if portfolio_df.empty:
    st.info("Your portfolio is empty.")
else:
    open_positions = portfolio_df[portfolio_df['Status'] == 'Open'].copy()
    total_value = 0

    if not open_positions.empty:
        st.markdown("### Open Positions")
        for index, row in open_positions.iterrows():
            details = get_position_details_with_retry(row['Ticker'])
            
            if not details:
                st.warning(f"Could not fetch data for {row['Ticker']}. API may be busy.")
                continue

            current_val = details['price'] * row['Quantity']
            total_value += current_val
            pnl = ((details['price'] / row['EntryPrice']) - 1) * 100 if row['EntryPrice'] > 0 else 0
            
            st.markdown("---")
            st.subheader(f"{row['Ticker']} ({int(row['Quantity'])} shares)")

            if "SELL" in details['signal']: st.error(details['signal'])
            else: st.success(details['signal'])

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Value", f"{current_val:,.2f} SEK")
            c2.metric("Entry", f"{row['EntryPrice']:,.2f} SEK")
            c3.metric("Price", f"{details['price']:.2f} SEK")
            
            pnl_color = "green" if pnl >= 0 else "red"
            c4.markdown(f"**P/L:** <span style='color:{pnl_color}; font-size:1.2em;'>{pnl:.2f}%</span>", unsafe_allow_html=True)
            
            with st.expander("Show Chart & Actions"):
                st.plotly_chart(create_portfolio_chart(details['chart_data'], row['EntryPrice']), use_container_width=True)
                
                st.markdown("**Edit**")
                with st.form(key=f"edit_{index}"):
                    new_q = st.number_input("Qty", value=float(row['Quantity']))
                    new_p = st.number_input("Price", value=float(row['EntryPrice']))
                    new_n = st.text_area("Notes", value=str(row['Notes']) if pd.notna(row['Notes']) else "")
                    if st.form_submit_button("Save"):
                        update_holding(index, new_q, new_p, new_n)
                        st.rerun()
                
                b1, b2 = st.columns(2)
                if b1.button("Close Position", key=f"close_{index}"):
                    update_holding_status(index, f"Closed {datetime.now().date()}")
                    st.rerun()
                if b2.button("Remove", key=f"rm_{index}"):
                    remove_holding(index)
                    st.rerun()
        
        st.markdown("---")
        st.header(f"Total Portfolio Value: {total_value:,.2f} SEK")

    st.markdown("### Position History")
    closed = portfolio_df[portfolio_df['Status'] != 'Open']
    if not closed.empty: st.dataframe(closed)