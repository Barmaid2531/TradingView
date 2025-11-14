import streamlit as st
import yfinance as yf
import pandas as pd
from prophet import Prophet
from prophet.plot import plot_plotly
from datetime import date
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import STOCK_LIST

st.set_page_config(layout="wide", page_title="Price Forecasting")

@st.cache_data(ttl=3600)
def load_data(ticker):
    data = yf.Ticker(ticker).history(period="5y")
    data.reset_index(inplace=True)
    # Prophet needs columns named 'ds' (Date) and 'y' (Price)
    df_prophet = data[['Date', 'Close']].rename(columns={'Date': 'ds', 'Close': 'y'})
    # Ensure timezone is removed to avoid Prophet errors
    df_prophet['ds'] = df_prophet['ds'].dt.tz_localize(None)
    return df_prophet

st.title("🔮 Price Forecast (Prophet)")
st.markdown("Uses machine learning to predict future trends based on 5 years of historical data.")

ticker_sel = st.selectbox("Select Stock", options=STOCK_LIST)
days_to_predict = st.slider("Days to Predict", 30, 365, 90)

if st.button("Generate Forecast"):
    ticker = ticker_sel.split("|")[0].strip()
    
    with st.spinner("Training model..."):
        data = load_data(ticker)
        
        # Train Prophet
        m = Prophet(daily_seasonality=True)
        m.fit(data)
        
        # Create future dates
        future = m.make_future_dataframe(periods=days_to_predict)
        forecast = m.predict(future)
        
        # Show Plot
        st.subheader(f"Forecast for {ticker}")
        fig = plot_plotly(m, forecast)
        st.plotly_chart(fig, use_container_width=True)
        
        # Show trend components
        st.subheader("Trend Components")
        st.write("See how the stock performs on different days of the week or months of the year.")
        st.pyplot(m.plot_components(forecast))
