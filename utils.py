# utils.py
import streamlit as st
import gspread
import pandas as pd
import requests

# --- STOCK UNIVERSE (Swedish Large & Mid Cap + Others) ---
# Format: "TICKER | Company Name"
STOCK_LIST = [
    "ABB.ST | ABB Ltd", "ALFA.ST | Alfa Laval", "ALIV-SDB.ST | Autoliv", 
    "ASSA-B.ST | Assa Abloy B", "ATCO-A.ST | Atlas Copco A", "ATCO-B.ST | Atlas Copco B",
    "AXFO.ST | Axfood", "AZN.ST | AstraZeneca", "BALD-B.ST | Fastighets AB Balder",
    "BEIJ-B.ST | Beijer Ref", "BILL.ST | Billerud", "BOL.ST | Boliden",
    "CAST.ST | Castellum", "ELUX-B.ST | Electrolux B", "EQT.ST | EQT",
    "ERIC-B.ST | Ericsson B", "ESSITY-B.ST | Essity B", "EVO.ST | Evolution",
    "FABG.ST | Fabege", "GETI-B.ST | Getinge B", "HEXA-B.ST | Hexagon B",
    "HM-B.ST | Hennes & Mauritz B", "HOLM-B.ST | Holmen B", "HPOL-B.ST | Hexpol B",
    "HUSQ-B.ST | Husqvarna B", "INDU-C.ST | Industrivärden C", "INVE-B.ST | Investor B",
    "JM.ST | JM", "KINV-B.ST | Kinnevik B", "LATO-B.ST | Latour B",
    "LIFCO-B.ST | Lifco B", "LUMI.ST | Lundin Mining", "NDA-SE.ST | Nordea Bank",
    "NIBE-B.ST | Nibe Industrier B", "NYF.ST | Nyfosa", "PEAB-B.ST | Peab B",
    "SAAB-B.ST | Saab B", "SAGA-B.ST | Sagax B", "SAND.ST | Sandvik",
    "SBB-B.ST | Samhällsbyggnadsbolaget B", "SCA-B.ST | SCA B", "SEB-A.ST | SEB A",
    "SECU-B.ST | Securitas B", "SHB-A.ST | Svenska Handelsbanken A", "SINCH.ST | Sinch",
    "SKA-B.ST | Skanska B", "SKF-B.ST | SKF B", "SSAB-A.ST | SSAB A",
    "SSAB-B.ST | SSAB B", "STE-R.ST | Stora Enso R", "SWED-A.ST | Swedbank A",
    "SWMA.ST | Swedish Match", "TEL2-B.ST | Tele2 B", "TELIA.ST | Telia Company",
    "THULE.ST | Thule Group", "TREL-B.ST | Trelleborg B", "TRUE-B.ST | Truecaller B",
    "VOLCAR-B.ST | Volvo Car B", "VOLV-A.ST | Volvo A", "VOLV-B.ST | Volvo B",
    "WALL-B.ST | Wallenstam B", "VITR.ST | Vitrolife", "VAR.OL | Vår Energi (Norway)",
    "EQNR.OL | Equinor (Norway)", "MAERSK-B.CO | Maersk B (Denmark)"
]

def get_google_sheet_data():
    try:
        # Ensure your secrets file has [gcp_service_account] section
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        sh = gc.open("Trading Portfolio")
        return sh.sheet1
    except Exception as e:
        st.error(f"Connection Error to Google Sheets: {e}")
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

def send_notification(title, message):
    """
    Sends a push notification to your phone using ntfy.sh.
    Requires 'NTFY_TOPIC' to be set in .streamlit/secrets.toml
    """
    topic = st.secrets.get("NTFY_TOPIC")
    
    # 1. Alert user if secret is missing (Debugging Step)
    if not topic:
        st.toast("⚠️ Notification skipped: 'NTFY_TOPIC' missing in secrets.", icon="🔕")
        return

    try:
        # 2. Send the request
        resp = requests.post(
            f"https://ntfy.sh/{topic}", 
            data=message.encode('utf-8'), 
            headers={"Title": title, "Priority": "high"}
        )
        
        # 3. Check for HTTP errors
        if resp.status_code == 200:
            # Success! (Silent or print to console log)
            print(f"Notification sent to {topic}")
        else:
            st.error(f"Ntfy Failed (Code {resp.status_code}): {resp.text}")
            
    except Exception as e:
        st.error(f"Notification System Error: {e}")
