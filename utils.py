# utils.py
import streamlit as st
import gspread
import pandas as pd
import requests

# --- EXPANDED STOCK UNIVERSE (~100 Liquid Tickers) ---
# Format: "TICKER | Company Name"
STOCK_LIST = [
    # --- 🇸🇪 OMXS30 (Blue Chips) ---
    "ABB.ST | ABB Ltd", "ALFA.ST | Alfa Laval", "ASSA-B.ST | Assa Abloy B",
    "ATCO-A.ST | Atlas Copco A", "ATCO-B.ST | Atlas Copco B", "AZN.ST | AstraZeneca",
    "BOL.ST | Boliden", "ELUX-B.ST | Electrolux B", "ERIC-B.ST | Ericsson B",
    "ESSITY-B.ST | Essity B", "EVO.ST | Evolution", "GETI-B.ST | Getinge B",
    "HEXA-B.ST | Hexagon B", "HM-B.ST | H&M B", "INVE-B.ST | Investor B",
    "KINV-B.ST | Kinnevik B", "NDA-SE.ST | Nordea Bank", "NIBE-B.ST | Nibe Industrier",
    "SAAB-B.ST | Saab B", "SAND.ST | Sandvik", "SCA-B.ST | SCA B",
    "SCIB-B.ST | Scibase", "SEB-A.ST | SEB A", "SECU-B.ST | Securitas B",
    "SHB-A.ST | Handelsbanken A", "SINCH.ST | Sinch", "SKA-B.ST | Skanska B",
    "SKF-B.ST | SKF B", "SSAB-A.ST | SSAB A", "SSAB-B.ST | SSAB B",
    "SWED-A.ST | Swedbank A", "TEL2-B.ST | Tele2 B", "TELIA.ST | Telia Company",
    "VOLV-B.ST | Volvo B", "VOLCAR-B.ST | Volvo Cars",

    # --- 🇸🇪 LARGE & MID CAP (Liquid) ---
    "AAK.ST | AAK", "AFRY.ST | AFRY", "ALIV-SDB.ST | Autoliv",
    "AXFO.ST | Axfood", "BALD-B.ST | Balder", "BEIJ-B.ST | Beijer Ref",
    "BETCO.ST | Betsson B", "BILL.ST | Billerud", "BRAV.ST | Bravida",
    "CAST.ST | Castellum", "DOM.ST | Dometic", "FABG.ST | Fabege",
    "HEM.ST | Hemnet", "HPOL-B.ST | Hexpol", "HUSQ-B.ST | Husqvarna",
    "INDU-C.ST | Indutrade", "JM.ST | JM AB", "LATO-B.ST | Latour",
    "LIFCO-B.ST | Lifco", "LOOMIS.ST | Loomis", "MTRS.ST | Munters",
    "MYCR.ST | Mycronic", "NCC-B.ST | NCC B", "NYF.ST | Nyfosa",
    "PEAB-B.ST | Peab", "SAGA-B.ST | Sagax B", "SBB-B.ST | SBB",
    "SWE-A.ST | Sweco A", "THULE.ST | Thule", "TREL-B.ST | Trelleborg",
    "VITR.ST | Vitrolife", "WALL-B.ST | Wallenstam", "WIHL.ST | Wihlborgs",

    # --- 🚀 GROWTH & FIRST NORTH PREMIER ---
    "EMBRAC-B.ST | Embracer Group", "FNOX.ST | Fortnox", "STORY-B.ST | Storytel",
    "VIMIAN.ST | Vimian", "AVANZ.ST | Avanza Bank", "SAVE.ST | Nordnet",
    "TRUE-B.ST | Truecaller", "NOTE.ST | Note",

    # --- 🇩🇰 🇳🇴 NORDIC GIANTS ---
    "NOVO-B.CO | Novo Nordisk (DK)", "MAERSK-B.CO | Maersk (DK)", 
    "DANSKE.CO | Danske Bank (DK)", "EQNR.OL | Equinor (NO)", 
    "MOWI.OL | Mowi (NO)", "YAR.OL | Yara (NO)",

    # --- 🇺🇸 US & CRYPTO (Reference) ---
    "AAPL | Apple", "TSLA | Tesla", "NVDA | Nvidia", "MSFT | Microsoft",
    "AMD | AMD", "COIN | Coinbase", "BTC-USD | Bitcoin", "ETH-USD | Ethereum"
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
            print(f"Notification sent to {topic}")
        else:
            st.error(f"Ntfy Failed (Code {resp.status_code}): {resp.text}")
            
    except Exception as e:
        st.error(f"Notification System Error: {e}")
