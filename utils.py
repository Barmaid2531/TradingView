# utils.py
import streamlit as st
import gspread
import pandas as pd
import requests # Import requests

def get_google_sheet_data():
    try:
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        sh = gc.open("Trading Portfolio")
        return sh.sheet1
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

def read_portfolio():
    sheet = get_google_sheet_data()
    if not sheet: return pd.DataFrame()
    data = sheet.get_all_records()
    if not data:
        return pd.DataFrame(columns=['Ticker', 'EntryDate', 'EntryPrice', 'Quantity', 'Status', 'Notes'])
    return pd.DataFrame(data)

def save_portfolio(df):
    sheet = get_google_sheet_data()
    if sheet:
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())

# --- NEW: Notification Function ---
def send_notification(title, message):
    """Sends a push notification via ntfy.sh"""
    topic = st.secrets.get("NTFY_TOPIC")
    if not topic:
        return # Fail silently if no topic configured
    
    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode(encoding='utf-8'),
            headers={
                "Title": title,
                "Priority": "high",
                "Tags": "chart_with_upwards_trend" if "Buy" in title else "warning"
            }
        )
    except Exception as e:
        print(f"Failed to send notification: {e}")
