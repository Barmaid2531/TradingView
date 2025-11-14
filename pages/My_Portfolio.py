# pages/My_Portfolio.py
import os
import json
import time
import streamlit as st
import pandas as pd
from utils import (
    read_sheet_public_csv,
    read_sheet_private,
    normalize_holdings_df,
    fetch_prices,
    compute_portfolio,
    GS_ENABLED,
)

st.set_page_config(page_title="My Portfolio", layout="wide")
st.title("My Portfolio")

with st.sidebar.expander("Google Sheet settings", expanded=True):
    st.markdown("**Select how the Google Sheet is provided**")
    mode = st.selectbox("Sheet mode", options=["public_csv", "service_account"], help="public_csv: published sheet CSV URL. service_account: private sheet using service account JSON.")
    if mode == "public_csv":
        csv_url = st.text_input("Published CSV Export URL", value=os.getenv("SHEET_CSV_URL", ""))
        st.caption("Example: https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=<GID>")
    else:
        if not GS_ENABLED:
            st.error("gspread/google-auth not installed or unavailable. Install gspread and google-auth.")
        service_json = st.text_area("Service Account JSON (paste entire JSON)", value=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", ""))
        spreadsheet_id = st.text_input("Spreadsheet ID (from sheet URL)", value=os.getenv("GOOGLE_SPREADSHEET_ID", ""))
        worksheet = st.text_input("Worksheet name or index (0)", value=os.getenv("GOOGLE_WORKSHEET", "0"))

st.write("### Controls")
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("Fetch portfolio now"):
        st.session_state.get_now = time.time()
        st.experimental_rerun()
with col2:
    st.write("Last fetch:", st.session_state.get("last_fetch_time", "Never"))

# Load holdings
holdings_df = None
error = None
if 'get_now' not in st.session_state:
    st.session_state.get_now = None

if mode == "public_csv" and csv_url:
    with st.spinner("Reading published CSV..."):
        try:
            df_raw = read_sheet_public_csv(csv_url)
            holdings_df = normalize_holdings_df(df_raw)
        except Exception as e:
            error = f"Failed to read public CSV: {e}"
elif mode == "service_account" and service_json and spreadsheet_id:
    try:
        svc = json.loads(service_json)
    except Exception as e:
        svc = None
        error = f"Invalid service account JSON: {e}"

    if svc and not error:
        try:
            with st.spinner("Reading private sheet..."):
                df_raw = read_sheet_private(svc, spreadsheet_id, int(worksheet) if worksheet.isdigit() else worksheet)
                holdings_df = normalize_holdings_df(df_raw)
        except Exception as e:
            error = f"Failed to read private sheet: {e}"
elif mode == "service_account":
    if not GS_ENABLED:
        st.warning("Service account reading disabled (missing gspread). Use public CSV mode or install gspread.")
    else:
        st.info("Provide service account JSON and spreadsheet ID.")

if error:
    st.error(error)

if holdings_df is None:
    st.info("No holdings loaded yet. Please configure sheet settings and click 'Fetch portfolio now'.")
    st.stop()

# Show holdings preview
st.subheader("Holdings preview")
st.dataframe(holdings_df)

# Fetch prices with caching - we use st.cache_data so repeated clicks are cheap
@st.cache_data(ttl=30)  # cache for 30 seconds
def _fetch_and_compute(symbols: list, qty_df: pd.DataFrame):
    prices = fetch_prices(symbols)
    portfolio_df, total = compute_portfolio(qty_df, prices)
    return prices, portfolio_df, total

with st.spinner("Fetching prices..."):
    symbols = holdings_df["symbol"].tolist()
    prices, portfolio_df, total = _fetch_and_compute(symbols, holdings_df)

st.session_state['last_fetch_time'] = time.strftime("%Y-%m-%d %H:%M:%S")

# UX: show summary and table with statuses
st.subheader("Portfolio summary")
colA, colB = st.columns([1, 2])
with colA:
    st.metric("Total value (approx)", f"${total:,.2f}")
    st.write(f"Last updated: {st.session_state.get('last_fetch_time')}")
with colB:
    # small bar chart of top positions by value
    topn = portfolio_df.dropna(subset=["value"]).sort_values("value", ascending=False).head(10)
    if not topn.empty:
        st.bar_chart(topn.set_index("symbol")["value"])

# Detailed table with status & retry
st.subheader("Positions")
def status_text(row):
    if pd.isna(row["price"]):
        return "Error: price not found"
    return "OK"

display_df = portfolio_df.copy()
display_df["price"] = display_df["price"].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "—")
display_df["value"] = display_df["value"].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "—")
display_df["status"] = portfolio_df.apply(status_text, axis=1)
st.table(display_df)

# Retry failed
failed_syms = portfolio_df[portfolio_df["price"].isna()]["symbol"].tolist()
if failed_syms:
    st.warning(f"Failed to fetch prices for: {', '.join(failed_syms)}")
    if st.button("Retry failed symbols"):
        # force a cache clear and re-fetch only failed symbols
        st.cache_data.clear()
        # re-run
        st.experimental_rerun()
else:
    st.success("All prices fetched successfully.")
