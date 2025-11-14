import streamlit as st
import yfinance as yf
import pandas as pd
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import sys
import os

# --- SETUP ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import STOCK_LIST

st.set_page_config(layout="wide", page_title="Strategy Backtester")

# --- DEFINE STRATEGIES ---
class RsiOscillator(Strategy):
    upper_bound = 70
    lower_bound = 30
    
    def init(self):
        # Calculate RSI manually to avoid 'talib' dependency issues
        close = pd.Series(self.data.Close)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        self.rsi = 100 - (100 / (1 + rs))

    def next(self):
        if self.rsi[-1] < self.lower_bound:
            self.buy()
        elif self.rsi[-1] > self.upper_bound:
            self.position.close()

class SmaCross(Strategy):
    n1 = 50
    n2 = 200
    
    def init(self):
        # Calculate SMA using standard Pandas
        price = pd.Series(self.data.Close)
        self.sma1 = price.rolling(self.n1).mean()
        self.sma2 = price.rolling(self.n2).mean()

    def next(self):
        if crossover(self.sma1, self.sma2): # Golden Cross
            self.buy()
        elif crossover(self.sma2, self.sma1): # Death Cross
            self.position.close()

# --- UI LAYOUT ---
st.title("🛠️ Strategy Backtester")
st.markdown("Simulate how a strategy would have performed over the last 3 years.")

c1, c2, c3 = st.columns(3)
# Defaults
ticker_sel = c1.selectbox("Stock", options=STOCK_LIST, index=0)
strat_sel = c2.selectbox("Strategy", ["RSI Dip Buyer (Buy < 30)", "Golden Cross (SMA 50/200)"])
cash = c3.number_input("Starting Cash", value=10000)

if st.button("Run Backtest"):
    try:
        ticker = ticker_sel.split("|")[0].strip()
        
        # 1. Get Data
        with st.spinner(f"Downloading 3 years of data for {ticker}..."):
            data = yf.download(ticker, period="3y", progress=False)
        
        # Fix for new YFinance multi-level columns (prevent KeyError)
        if isinstance(data.columns, pd.MultiIndex):
            try:
                data = data.xs(ticker, axis=1, level=0)
            except:
                # Fallback if xs fails or structure is different
                data.columns = data.columns.droplevel(0)

        # Ensure we have data
        if data.empty:
            st.error("No data found. Try a different stock.")
            st.stop()
        
        # 2. Choose Strategy Class
        strat_class = RsiOscillator if "RSI" in strat_sel else SmaCross
        
        # 3. Run Backtest
        bt = Backtest(data, strat_class, cash=cash, commission=.002)
        stats = bt.run()
        
        # 4. Display Results
        st.markdown("### 📊 Performance Report")
        
        res1, res2, res3, res4 = st.columns(4)
        res1.metric("Return", f"{stats['Return [%]']:.2f}%")
        res2.metric("Win Rate", f"{stats['Win Rate [%]']:.2f}%")
        res3.metric("Max Drawdown", f"{stats['Max. Drawdown [%]']:.2f}%")
        res4.metric("Total Trades", f"{stats['# Trades']:.0f}")
        
        st.markdown("### 📈 Equity Curve")
        st.line_chart(stats['_equity_curve']['Equity'])
        
        with st.expander("View Full Stats"):
            st.write(stats)
            
    except Exception as e:
        st.error(f"Backtest failed: {e}")
