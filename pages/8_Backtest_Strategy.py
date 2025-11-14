import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta  # Optional, but we will define helpers manually below to be safe
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import sys
import os

# --- SETUP ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import STOCK_LIST

st.set_page_config(layout="wide", page_title="Strategy Backtester")

# --- HELPER FUNCTIONS (Must be outside the class for self.I to work pickle-wise) ---
def SMA(values, n):
    """
    Return simple moving average of `values`, at
    each step taking into account `n` previous values.
    """
    return pd.Series(values).rolling(n).mean()

def RSI(values, n=14):
    """
    Return RSI of `values`.
    """
    delta = pd.Series(values).diff()
    gain = delta.where(delta > 0, 0).rolling(n).mean()
    loss = -delta.where(delta < 0, 0).rolling(n).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- STRATEGIES ---
class RsiOscillator(Strategy):
    upper_bound = 70
    lower_bound = 30
    
    def init(self):
        # FIX: Use self.I() to register the indicator
        # This ensures backtesting.py handles the array slicing correctly
        self.rsi = self.I(RSI, self.data.Close, 14)

    def next(self):
        if self.rsi[-1] < self.lower_bound:
            self.buy()
        elif self.rsi[-1] > self.upper_bound:
            self.position.close()

class SmaCross(Strategy):
    n1 = 50
    n2 = 200
    
    def init(self):
        # FIX: Use self.I() to register indicators
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)

    def next(self):
        if crossover(self.sma1, self.sma2):
            self.buy()
        elif crossover(self.sma2, self.sma1):
            self.position.close()

# --- UI LAYOUT ---
st.title("🛠️ Strategy Backtester")
st.markdown("Simulate how a strategy would have performed over the last 3 years.")

c1, c2, c3 = st.columns(3)
ticker_sel = c1.selectbox("Stock", options=STOCK_LIST, index=0)
strat_sel = c2.selectbox("Strategy", ["RSI Dip Buyer (Buy < 30)", "Golden Cross (SMA 50/200)"])
cash = c3.number_input("Starting Cash", value=10000)

if st.button("Run Backtest"):
    try:
        ticker = ticker_sel.split("|")[0].strip()
        
        # 1. Get Data (Cleaner Method)
        with st.spinner(f"Downloading data for {ticker}..."):
            # Using Ticker().history is safer than download() for single stocks
            # It avoids MultiIndex columns issues entirely
            data = yf.Ticker(ticker).history(period="3y")
        
        # 2. Data Cleaning
        if data.empty:
            st.error("No data found. Try another stock.")
            st.stop()
            
        # Drop timezone (Critical for backtesting.py)
        data.index = data.index.tz_localize(None)
        
        # Ensure columns are correct
        data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        # Drop NaNs (e.g. from recent splits or partial data)
        data = data.dropna()

        # 3. Choose Strategy
        strat_class = RsiOscillator if "RSI" in strat_sel else SmaCross
        
        # 4. Run Backtest
        bt = Backtest(data, strat_class, cash=cash, commission=.002)
        stats = bt.run()
        
        # 5. Display Results
        st.markdown("### 📊 Performance Report")
        
        res1, res2, res3, res4 = st.columns(4)
        # Helper to safe format
        def safe_fmt(val): return f"{val:.2f}%" if isinstance(val, (int, float)) else str(val)
        
        res1.metric("Return", safe_fmt(stats['Return [%]']))
        res2.metric("Win Rate", safe_fmt(stats['Win Rate [%]']))
        res3.metric("Max Drawdown", safe_fmt(stats['Max. Drawdown [%]']))
        res4.metric("Total Trades", f"{stats['# Trades']}")
        
        st.markdown("### 📈 Equity Curve")
        st.line_chart(stats['_equity_curve']['Equity'])
        
        with st.expander("View Full Stats"):
            st.dataframe(stats.astype(str))
            
    except Exception as e:
        st.error(f"Backtest failed: {e}")
