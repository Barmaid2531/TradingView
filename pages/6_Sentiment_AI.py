import streamlit as st
import finnhub
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from datetime import datetime, timedelta
import sys
import os

# --- SETUP ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import STOCK_LIST

st.set_page_config(layout="wide", page_title="AI News Sentiment")

# --- API SETUP ---
# You need a FREE API key from https://finnhub.io/
# Add it to .streamlit/secrets.toml as: FINNHUB_KEY = "your_key_here"
try:
    finnhub_client = finnhub.Client(api_key=st.secrets["FINNHUB_KEY"])
except:
    st.warning("⚠️ Finnhub API Key not found. Please add `FINNHUB_KEY` to your secrets.")
    finnhub_client = None

analyzer = SentimentIntensityAnalyzer()

def get_news_sentiment(ticker):
    if not finnhub_client: return None
    
    # Get news for last 7 days
    end = datetime.now().strftime('%Y-%m-%d')
    start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    try:
        # Fetch news from Finnhub
        news = finnhub_client.company_news(ticker, _from=start, to=end)
        if not news: return None
        
        df = pd.DataFrame(news)
        
        # --- AI SCORING (VADER) ---
        # We score the 'headline' and 'summary'
        scores = []
        for index, row in df.iterrows():
            text = f"{row['headline']} {row['summary']}"
            score = analyzer.polarity_scores(text)
            scores.append(score['compound']) # Compound score is between -1 (Neg) and +1 (Pos)
            
        df['sentiment_score'] = scores
        return df
    except Exception as e:
        st.error(f"Error fetching news: {e}")
        return None

st.title("🤖 AI News Sentiment")
st.markdown("This tool reads the last **7 days of news** and uses AI to judge if the mood is Bullish or Bearish.")

ticker_input = st.selectbox("Select Stock", options=STOCK_LIST)
if ticker_input:
    ticker = ticker_input.split("|")[0].strip()
    
    if st.button(f"Analyze News for {ticker}"):
        with st.spinner("Reading news headlines..."):
            news_df = get_news_sentiment(ticker)
        
        if news_df is not None and not news_df.empty:
            # Calc Average Sentiment
            avg_score = news_df['sentiment_score'].mean()
            
            # Sentiment Meter
            if avg_score > 0.05:
                mood = "🟢 Bullish (Positive News)"
                color = "green"
            elif avg_score < -0.05:
                mood = "🔴 Bearish (Negative News)"
                color = "red"
            else:
                mood = "⚪ Neutral"
                color = "gray"
                
            st.markdown(f"### Market Mood: <span style='color:{color}'>{mood}</span>", unsafe_allow_html=True)
            st.metric("Sentiment Score", f"{avg_score:.2f}", help="-1 is Very Bad, +1 is Very Good")
            
            # Show Top Positive/Negative Stories
            st.subheader("📰 Key Headlines")
            for i, row in news_df.head(5).iterrows():
                emoji = "🟢" if row['sentiment_score'] > 0 else "🔴"
                with st.expander(f"{emoji} {row['headline']}"):
                    st.write(row['summary'])
                    st.caption(f"Source: {row['source']} | Score: {row['sentiment_score']:.2f}")
                    st.markdown(f"[Read Article]({row['url']})")
        else:
            st.info("No recent news found for this stock.")
