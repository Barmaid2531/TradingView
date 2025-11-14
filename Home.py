# Home.py
import streamlit as st

st.set_page_config(page_title="Portfolio App", layout="wide")
st.title("Portfolio App — Home")
st.write(
    "This app reads your portfolio from a Google Sheet and fetches live prices. "
    "Use the **My Portfolio** page to connect a sheet and view totals. "
)
st.markdown("""
**Notes**
- If your Google Sheet is *public/published*, use the CSV export URL.
- For a *private* sheet use a Google Service Account JSON and the spreadsheet ID.
- The app uses `yfinance` as the price provider fallback.
""")
st.info("Navigate to **My Portfolio** in the left sidebar (or the Pages menu) to view your portfolio.")
